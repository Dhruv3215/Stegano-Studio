# app.py
import io, zipfile, traceback, os
from flask import Flask, render_template, request, send_file, jsonify
from stegano_core import (
    create_payload_zip_from_files,
    create_payload_zip_from_bytes,
    encrypt_payload,
    decrypt_payload,
    pack_stego,
    unpack_stego,
    sha256_hex_bytes,
    bytes_to_human,
    append_history,
    read_history_html,
    clear_history,
    is_strong_password,
    lsb_capacity_bytes,
    embed_lsb,
    extract_lsb,
)
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024  # 300MB uploads allowed

@app.route("/")
def index():
    history_html = read_history_html()
    return render_template("index.html", history_html=history_html)

# Estimate endpoint to compute payload size vs carrier (supports LSB)
@app.route("/estimate", methods=["POST"])
def estimate():
    try:
        carrier = request.files.get("carrier")
        carrier_size = 0
        carrier_bytes = b""
        if carrier:
            carrier_bytes = carrier.read()
            carrier_size = len(carrier_bytes)
        secret_text = request.form.get("secret_text", "")
        secret_files = request.files.getlist("secret_files")
        payload_zip = create_payload_zip_from_files(secret_text, secret_files)
        # payload that will be stored (with header)
        plnd = b"PLND" + payload_zip
        payload_len = len(plnd)
        # LSB capacity (bytes)
        lsb_cap = lsb_capacity_bytes(carrier_bytes) if carrier_bytes else 0
        return jsonify({
            "carrier_size": carrier_size,
            "payload_size": payload_len,
            "carrier_human": bytes_to_human(carrier_size),
            "payload_human": bytes_to_human(payload_len),
            "lsb_capacity_bytes": lsb_cap,
            "lsb_capacity_human": bytes_to_human(lsb_cap)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400

@app.route("/embed", methods=["POST"])
def embed():
    try:
        carrier = request.files.get("carrier")
        if not carrier or carrier.filename == "":
            return jsonify({"error": "Carrier file required"}), 400

        # Read carrier and keep its original extension
        carrier_bytes = carrier.read()
        carrier_name = carrier.filename
        carrier_ext = os.path.splitext(carrier_name)[1]  # e.g. ".png", ".jpg", ".mp4"
        if not carrier_ext:
            carrier_ext = ".bin"  # fallback if no extension

        secret_text = request.form.get("secret_text", "")
        secret_files = request.files.getlist("secret_files")

        # Build payload zip
        payload_zip = create_payload_zip_from_files(secret_text, secret_files)

        if request.form.get("encrypt") == "on":
            pwd = request.form.get("password", "")
            if not pwd:
                return jsonify({"error": "Password required for encryption"}), 400
            if not is_strong_password(pwd):
                return jsonify({"error": "Password too weak. Use min 10 chars including uppercase, lowercase, digits, symbol."}), 400
            payload = encrypt_payload(payload_zip, pwd)
        else:
            payload = b"PLND" + payload_zip

        # Choose mode: 'eof' or 'lsb'
        mode = request.form.get("mode", "eof")
        if mode == "lsb":
            # embed header + payload into image LSB using optional password-based PRNG
            headered = payload
            from stegano_core import MARKER, LENGTH_LEN
            payload_for_lsb = MARKER + len(headered).to_bytes(LENGTH_LEN, "big") + headered
            # check capacity
            cap = lsb_capacity_bytes(carrier_bytes)
            if cap < len(payload_for_lsb):
                return jsonify({"error": f"Image capacity too small for LSB embedding. Needs {len(payload_for_lsb)} bytes, capacity {cap} bytes."}), 400
            pwd = request.form.get("password", "")  # use same password as provided for encryption optionally
            stego = embed_lsb(carrier_bytes, payload_for_lsb, pwd)
            sha = sha256_hex_bytes(stego)
            append_history(f"LSB-embedded and saved stego (in-memory) SHA-256: {sha}")
            # always return .png for LSB output
            return send_file(io.BytesIO(stego), as_attachment=True, download_name=f"stego_output.png")
        else:
            # EOF append
            stego = pack_stego(carrier_bytes, payload)
            sha = sha256_hex_bytes(stego)
            append_history(f"EOF-embedded and saved stego (in-memory) SHA-256: {sha}")
            # Save with original extension instead of .bin
            return send_file(io.BytesIO(stego), as_attachment=True,
                             download_name=f"stego_output{carrier_ext}")
    except Exception as e:
        traceback.print_exc()
        append_history(f"Embed Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Get info about stego (preview file list & secret text)
@app.route("/extract_info", methods=["POST"])
def extract_info():
    try:
        stego = request.files.get("stego")
        if not stego:
            return jsonify({"error":"Stego file required"}), 400
        full = stego.read()

        # Try EOF first; if that fails, try LSB
        payload = None
        prefix = None
        try:
            payload = unpack_stego(full)
            prefix = "eof"
        except Exception:
            # try LSB (pass provided password for PRNG ordering)
            try:
                pwd = request.form.get("password", "")
                payload_with_header = extract_lsb(full, pwd)  # returns MARKER+LENGTH+payload
                from stegano_core import MARKER, LENGTH_LEN
                if not payload_with_header.startswith(MARKER):
                    raise ValueError("LSB payload missing marker")
                ln = int.from_bytes(payload_with_header[len(MARKER):len(MARKER)+LENGTH_LEN], "big")
                payload = payload_with_header[len(MARKER)+LENGTH_LEN:len(MARKER)+LENGTH_LEN+ln]
                prefix = "lsb"
            except Exception as e:
                raise ValueError(f"Unable to find embedded payload (neither EOF nor LSB). Details: {str(e)}")

        if payload.startswith(b"ENCR"):
            pwd = request.form.get("password", "")
            if not pwd:
                return jsonify({"error":"Password required for encrypted payload"}), 400
            data = decrypt_payload(payload, pwd)
        elif payload.startswith(b"PLND"):
            data = payload[4:]
        else:
            return jsonify({"error":"Unknown payload type"}), 400

        zf = zipfile.ZipFile(io.BytesIO(data), "r")
        names = zf.namelist()
        preview = ""
        if "secret_text.txt" in names:
            try:
                preview = zf.read("secret_text.txt").decode(errors="ignore")
            except Exception:
                preview = ""
        files_info = []
        for name in names:
            b = zf.read(name)
            files_info.append({"name": name, "size": len(b)})
        append_history(f"Extracted {len(files_info)} files from stego (preview). Mode guessed: {prefix}")
        return jsonify({"files": files_info, "preview": preview})
    except Exception as e:
        traceback.print_exc()
        append_history(f"Extract Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Download whole payload.zip  (always ZIP)
@app.route("/download_payload", methods=["POST"])
def download_payload():
    try:
        stego = request.files.get("stego")
        if not stego:
            return jsonify({"error":"Stego file required"}), 400
        full = stego.read()

        # attempt EOF then LSB (use provided password)
        payload = None
        try:
            payload = unpack_stego(full)
        except Exception:
            # LSB
            pwd = request.form.get("password", "")
            payload_with_header = extract_lsb(full, pwd)
            from stegano_core import MARKER, LENGTH_LEN
            if not payload_with_header.startswith(MARKER):
                raise ValueError("LSB payload missing marker")
            ln = int.from_bytes(payload_with_header[len(MARKER):len(MARKER)+LENGTH_LEN], "big")
            payload = payload_with_header[len(MARKER)+LENGTH_LEN:len(MARKER)+LENGTH_LEN+ln]

        if payload.startswith(b"ENCR"):
            pwd = request.form.get("password", "")
            if not pwd:
                return jsonify({"error":"Password required for encrypted payload"}), 400
            data = decrypt_payload(payload, pwd)
        elif payload.startswith(b"PLND"):
            data = payload[4:]
        else:
            return jsonify({"error":"Unknown payload type"}), 400

        append_history("Saved whole extracted zip.")
        return send_file(io.BytesIO(data), as_attachment=True, download_name="extracted_payload.zip")
    except Exception as e:
        traceback.print_exc()
        append_history(f"Download Payload Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Download selected files raw when possible:
# - single file  -> original format
# - multiple     -> zipped (browser limitation)
@app.route("/download_selected_raw", methods=["POST"])
def download_selected_raw():
    try:
        f = request.files["stego"]
        full = f.read()
        password = request.form.get("password","")
        payload_with_header = extract_lsb(full, password) if full.startswith(b"\x89PNG") else unpack_stego(full)
        if payload_with_header.startswith(b"ENCR"):
            payload = decrypt_payload(payload_with_header, password)
        else:
            payload = payload_with_header
        zf = zipfile.ZipFile(io.BytesIO(payload))
        selected = request.form.getlist("selected[]")

        if len(selected) == 1:
            # Return raw file in original format
            fname = selected[0]
            data = zf.read(fname)
            return send_file(io.BytesIO(data), as_attachment=True,
                             download_name=fname, mimetype="application/octet-stream")

        # Multiple → return zip
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in selected:
                zout.writestr(name, zf.read(name))
        out.seek(0)
        return send_file(out, as_attachment=True,
                         download_name="selected_files.zip",
                         mimetype="application/zip")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# (Deprecated) legacy zip-forced route; kept for backward compatibility but unused by frontend.
@app.route("/download_selected", methods=["POST"])
def download_selected():
    try:
        return jsonify({"error": "Legacy route not supported by UI. Use /download_selected_raw."}), 410
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# History endpoints
@app.route("/history_content", methods=["GET"])
def history_content():
    return read_history_html()

@app.route("/history_clear", methods=["POST"])
def history_clear():
    clear_history()
    append_history("History cleared by user.")
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)
