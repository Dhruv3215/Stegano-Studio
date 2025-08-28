# stegano_core.py
import os, io, zipfile, secrets, hashlib, re, traceback, random
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image
import numpy as np

# ------------------ Constants ------------------ #
MARKER = b"STEG0"
LENGTH_LEN = 8
PBKDF2_ITERS = 200_000
SALT_LEN = 16
NONCE_LEN = 12

HISTORY_DIR = Path.home() / ".stegano_studio"
HISTORY_FILE = HISTORY_DIR / "history.log"
SETTINGS_FILE = HISTORY_DIR / "settings.json"

# ------------------ Utilities ------------------ #
def bytes_to_human(n: int) -> str:
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024.0:
            return f"{n:3.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def sha256_hex_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def is_strong_password(pwd: str) -> bool:
    return (
        len(pwd) >= 10 and
        re.search(r"[A-Z]", pwd) and
        re.search(r"[a-z]", pwd) and
        re.search(r"[0-9]", pwd) and
        re.search(r"[^A-Za-z0-9]", pwd)
    )

# Safe zip extraction to bytes dict (prevents zip slip)
def safe_extract_to_bytes(zf: zipfile.ZipFile, members=None):
    out = {}
    base = Path.cwd().resolve()
    names = members if members is not None else zf.namelist()
    for member in names:
        target_path = (base / member).resolve()
        if not str(target_path).startswith(str(base)):
            raise Exception(f"Blocked Zip Slip attempt: {member}")
        out[member] = zf.read(member)
    return out

# Create payload zip from file-like objects (Werkzeug FileStorage)
def create_payload_zip_from_files(secret_text: str, secret_files):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        if secret_text and secret_text.strip():
            zf.writestr("secret_text.txt", secret_text)
        seen = set()
        for f in secret_files:
            # f is FileStorage-like
            if not hasattr(f, "filename") or not f.filename:
                continue
            name = os.path.basename(f.filename)
            target = name
            i = 1
            while target in seen:
                root, ext = os.path.splitext(name)
                target = f"{root}_{i}{ext}"
                i += 1
            seen.add(target)
            content = f.read()
            if isinstance(content, str):
                content = content.encode()
            zf.writestr(target, content)
    return bio.getvalue()

def create_payload_zip_from_bytes(secret_text: str, files_dict: dict):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        if secret_text and secret_text.strip():
            zf.writestr("secret_text.txt", secret_text)
        seen = set()
        for name, data in files_dict.items():
            if not name: continue
            n = os.path.basename(name)
            target = n
            i = 1
            while target in seen:
                root, ext = os.path.splitext(n)
                target = f"{root}_{i}{ext}"
                i += 1
            seen.add(target)
            zf.writestr(target, data)
    return bio.getvalue()

# ------------------ Key derivation + encryption/decryption ------------------ #
def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERS)
    return kdf.derive(password.encode())

def encrypt_payload(payload: bytes, password: str) -> bytes:
    salt = secrets.token_bytes(SALT_LEN)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(NONCE_LEN)
    ct = aesgcm.encrypt(nonce, payload, None)
    return b"ENCR" + salt + nonce + ct

def decrypt_payload(enc_bytes: bytes, password: str) -> bytes:
    if not enc_bytes.startswith(b"ENCR"):
        raise ValueError("Payload not encrypted or invalid header.")
    off = 4
    salt = enc_bytes[off:off+SALT_LEN]; off += SALT_LEN
    nonce = enc_bytes[off:off+NONCE_LEN]; off += NONCE_LEN
    ct = enc_bytes[off:]
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)

# ------------------ EOF Mode (append) ------------------ #
def pack_stego(carrier_bytes: bytes, payload: bytes) -> bytes:
    ln = len(payload).to_bytes(LENGTH_LEN, "big")
    return carrier_bytes + MARKER + ln + payload

def unpack_stego(full: bytes) -> bytes:
    idx = full.rfind(MARKER)
    if idx == -1 or idx + len(MARKER) + LENGTH_LEN > len(full):
        raise ValueError("Marker not found or truncated.")
    ln_off = idx + len(MARKER)
    ln = int.from_bytes(full[ln_off:ln_off+LENGTH_LEN], "big")
    start = ln_off + LENGTH_LEN
    end = start + ln
    if end > len(full):
        raise ValueError("Invalid embedded length (corrupted container).")
    return full[start:end]

# ------------------ LSB Mode (pixel LSB) ------------------ #
def _to_bitstring(b: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in b)

def _from_bitstring(bits: str) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("Bitstring length not multiple of 8")
    out = bytearray()
    for i in range(0, len(bits), 8):
        out.append(int(bits[i:i+8], 2))
    return bytes(out)

def _seed_from_password(password: str):
    """Return deterministic integer seed derived from password or None if empty."""
    if not password:
        return None
    h = hashlib.sha256(password.encode()).digest()
    # use 64 bits to seed PRNG deterministically
    return int.from_bytes(h[:8], "big")

def lsb_capacity_bytes(carrier_bytes: bytes) -> int:
    """
    Return how many bytes can be embedded using LSB in this image (RGB).
    """
    try:
        img = Image.open(io.BytesIO(carrier_bytes)).convert("RGB")
    except Exception:
        return 0
    w, h = img.size
    total_bits = w * h * 3  # RGB channels
    return total_bits // 8

def embed_lsb(carrier_bytes: bytes, payload: bytes, password: str = "") -> bytes:
    """
    Embed payload bytes into the LSBs of an image (carrier). Output PNG bytes.
    Uses PRNG-based bit ordering if password provided (seed derived from password).
    Payload should include header (marker + length + actual bytes) like EOF mode.
    """
    img = Image.open(io.BytesIO(carrier_bytes)).convert("RGB")
    data = np.array(img)
    flat = data.flatten()  # dtype = uint8

    bits = _to_bitstring(payload)
    if len(bits) > flat.size:
        raise ValueError("Payload too large for image capacity.")

    indices = list(range(flat.size))
    seed = _seed_from_password(password)
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(indices)

    # modify LSBs per index order (PRNG or sequential)
    for i, bit in enumerate(bits):
        idx = indices[i]
        flat[idx] = (flat[idx] & 0xFE) | int(bit)

    new_data = flat.reshape(data.shape).astype(np.uint8)
    stego_img = Image.fromarray(new_data, mode="RGB")
    out = io.BytesIO()
    # Save as PNG to be lossless and predictable
    stego_img.save(out, format="PNG")
    return out.getvalue()

def extract_lsb(stego_bytes: bytes, password: str = "") -> bytes:
    """
    Extract the payload by:
    1) Reading header (MARKER + LENGTH_LEN bytes) first by reading their bits
       in PRNG order if password provided, otherwise sequentially.
    2) Reading the rest of payload based on length
    Returns the raw embedded bytes including marker+length+payload.
    """
    img = Image.open(io.BytesIO(stego_bytes)).convert("RGB")
    data = np.array(img).flatten()

    indices = list(range(data.size))
    seed = _seed_from_password(password)
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(indices)

    # Read header
    header_bytes_len = len(MARKER) + LENGTH_LEN
    header_bits_len = header_bytes_len * 8
    if header_bits_len > len(indices):
        raise ValueError("Image too small or corrupted (can't read header).")

    header_bits = "".join(str(int(data[indices[i]] & 1)) for i in range(header_bits_len))
    header_bytes = _from_bitstring(header_bits)
    if not header_bytes.startswith(MARKER):
        raise ValueError("Marker not found in LSB data.")

    ln = int.from_bytes(header_bytes[len(MARKER):len(MARKER)+LENGTH_LEN], "big")
    payload_total_bytes = header_bytes_len + ln
    total_bits_needed = payload_total_bytes * 8
    if total_bits_needed > len(indices):
        raise ValueError("Declared payload length exceeds image capacity or is corrupted.")

    bits = "".join(str(int(data[indices[i]] & 1)) for i in range(total_bits_needed))
    all_bytes = _from_bitstring(bits)
    return all_bytes  # includes marker + length + payload

# ------------------ History management ------------------ #
def ensure_history_dir():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

def append_history(text: str):
    ensure_history_dir()
    stamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {text}"
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        traceback.print_exc()

def read_history_html():
    ensure_history_dir()
    if HISTORY_FILE.exists():
        try:
            return HISTORY_FILE.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""

def clear_history():
    ensure_history_dir()
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
    except Exception:
        pass
