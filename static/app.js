// static/app.js

// Show toast notifications
function showToast(msg, type = "info") {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.className =
    "fixed bottom-6 right-6 px-4 py-2 rounded-lg shadow text-white font-medium";
  if (type === "error") {
    toast.classList.add("bg-red-600");
  } else if (type === "success") {
    toast.classList.add("bg-green-600");
  } else {
    toast.classList.add("bg-gray-800");
  }
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 4000);
}

// Update drop-zone label with filename(s)
function updateDropLabel(inputId, dropId) {
  const input = document.getElementById(inputId);
  const zone = document.getElementById(dropId);
  const label = zone.querySelector(".pointer-events-none");

  if (input.files.length > 0) {
    let names = Array.from(input.files).map(f => f.name).join(", ");
    label.textContent = "Selected: " + names;
    label.classList.remove("text-gray-400");
    label.classList.add("text-green-400");
  } else {
    // reset back to placeholder
    label.textContent = dropId === "carrier_drop"
      ? "Drop an image here or click to select."
      : "Drop the stego file here or click to select.";
    label.classList.remove("text-green-400");
    label.classList.add("text-gray-400");
  }
}

// Tab switching
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.remove("hidden");
  });
});

// Enable/disable password input
const encryptCb = document.getElementById("encrypt_cb");
const passwordInput = document.getElementById("password_input");
encryptCb.addEventListener("change", () => {
  passwordInput.disabled = !encryptCb.checked;
});

// Update capacity estimate
async function updateEstimate() {
  const carrierInput = document.getElementById("carrier_input");
  if (!carrierInput.files.length) return;
  const formData = new FormData();
  formData.append("carrier", carrierInput.files[0]);
  formData.append("secret_text", document.getElementById("secret_text").value);
  for (let f of document.getElementById("secret_files_input").files) {
    formData.append("secret_files", f);
  }
  try {
    const res = await fetch("/estimate", { method: "POST", body: formData });
    const data = await res.json();
    if (data.error) return;
    document.getElementById("capacity_label").textContent =
      `Capacity: carrier — ${data.carrier_human}, payload — ${data.payload_human}`;
  } catch (e) { }
}

// Carrier file change
document.getElementById("carrier_input").addEventListener("change", () => {
  updateDropLabel("carrier_input", "carrier_drop"); // update label
  updateEstimate();
  const mode = document.getElementById("embed_mode").value;
  const carrierInput = document.getElementById("carrier_input");
  if (mode === "lsb" && carrierInput.files.length) {
    const name = carrierInput.files[0].name.toLowerCase();
    if (!name.endsWith(".png") && !name.endsWith(".bmp")) {
      showToast("Warning: LSB works best with PNG/BMP. Lossy formats (e.g. JPG) may corrupt data.", "error");
    }
  }
});

// Stego file change
document.getElementById("stego_input").addEventListener("change", () => {
  updateDropLabel("stego_input", "stego_drop"); // update label
});

// Drag-and-drop setup
function setupDropZone(inputId, dropId) {
  const input = document.getElementById(inputId);
  const zone = document.getElementById(dropId);

  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("ring-2", "ring-cyan-500");
  });
  zone.addEventListener("dragleave", () => {
    zone.classList.remove("ring-2", "ring-cyan-500");
  });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("ring-2", "ring-cyan-500");
    const files = e.dataTransfer.files;
    if (files && files.length) {
      input.files = files;
      input.dispatchEvent(new Event('change')); // triggers updateDropLabel
      updateDropLabel(inputId, dropId);
    }
  });
}
setupDropZone("carrier_input", "carrier_drop");
setupDropZone("stego_input", "stego_drop");

// Embed action
document.getElementById("embed_btn").addEventListener("click", async () => {
  const carrierInput = document.getElementById("carrier_input");
  if (!carrierInput.files.length) {
    showToast("Carrier file required", "error");
    return;
  }
  const formData = new FormData();
  formData.append("carrier", carrierInput.files[0]);
  formData.append("secret_text", document.getElementById("secret_text").value);
  for (let f of document.getElementById("secret_files_input").files) {
    formData.append("secret_files", f);
  }
  if (encryptCb.checked) {
    formData.append("encrypt", "on");
    formData.append("password", passwordInput.value);
  }
  formData.append("mode", document.getElementById("embed_mode").value);
  try {
    const res = await fetch("/embed", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      showToast(err.error || "Embed failed", "error");
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "stego_output" + carrierInput.files[0].name.split(".").pop();
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast("Stego file saved", "success");
  } catch (e) {
    showToast("Embed error: " + e.message, "error");
  }
});

// Reset embed form
document.getElementById("reset_btn").addEventListener("click", () => {
  document.getElementById("embed_form").reset();
  updateDropLabel("carrier_input", "carrier_drop");
  document.getElementById("capacity_label").textContent = "Capacity: carrier — ?, payload — ?";
});

// Extract action
document.getElementById("extract_btn").addEventListener("click", async () => {
  const stegoInput = document.getElementById("stego_input");
  if (!stegoInput.files.length) {
    showToast("Stego file required", "error");
    return;
  }
  const formData = new FormData();
  formData.append("stego", stegoInput.files[0]);
  formData.append("password", document.getElementById("extract_password").value);
  try {
    const res = await fetch("/extract_info", { method: "POST", body: formData });
    const data = await res.json();
    if (data.error) {
      showToast(data.error, "error");
      return;
    }
    // populate file list
    const fileList = document.getElementById("file_list");
    fileList.innerHTML = "";
    data.files.forEach(f => {
      const div = document.createElement("div");
      div.className = "flex items-center gap-2 mb-1";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = f.name;
      div.appendChild(cb);
      const span = document.createElement("span");
      span.textContent = `${f.name} (${f.size} bytes)`;
      span.className = "cursor-pointer hover:text-cyan-400";
      span.addEventListener("click", () => {
         // Clear previous selections
         document.querySelectorAll("#file_list span").forEach(s => {
             s.classList.remove("text-cyan-400", "selected");
             delete s.dataset.fn;
           });

           // Mark this one
           span.classList.add("text-cyan-400", "selected");
           span.dataset.fn = f.name;  // 👈 important for saveSelected()
         });
      div.appendChild(span);
      fileList.appendChild(div);
    });
    document.getElementById("preview_box").value = data.preview || "";
    showToast("Extracted info preview ready", "success");
  } catch (e) {
    showToast("Extract error: " + e.message, "error");
  }
});

// Reset extract form
document.getElementById("extract_reset_btn").addEventListener("click", () => {
  document.getElementById("stego_input").value = "";
  document.getElementById("file_list").innerHTML = "";
  document.getElementById("preview_box").value = "";
  updateDropLabel("stego_input", "stego_drop");
});

// Save actions

// ---------- download handlers ----------

// helper to trigger download
function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

// Save Selected File
async function saveSelected() {
  const stego = document.getElementById("stego_input").files[0];
  if (!stego) return showToast("Stego file required", "error");

  const selectedEl = document.querySelector("#file_list .selected");
  if (!selectedEl) return showToast("No file selected", "error");

  const fd = new FormData();
  fd.append("stego", stego);
  fd.append("password", document.getElementById("extract_password").value || "");
  fd.append("selected[]", selectedEl.dataset.fn);
  fd.append("action", "selected");

  const res = await fetch("/download_selected_raw", { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json();
    return showToast("Error: " + err.error, "error");
  }
  const blob = await res.blob();
  triggerDownload(blob, "selected.zip");
}

// Save Checked Files
async function saveChecked() {
  const stego = document.getElementById("stego_input").files[0];
  if (!stego) return showToast("Stego file required", "error");

  const checked = [...document.querySelectorAll("#file_list input[type=checkbox]:checked")];
  if (checked.length === 0) return showToast("No files checked", "error");

  const fd = new FormData();
  fd.append("stego", stego);
  fd.append("password", document.getElementById("extract_password").value || "");
  checked.forEach(cb => fd.append("selected[]", cb.value));
  fd.append("action", "checked");

  const res = await fetch("/download_selected_raw", { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json();
    return showToast("Error: " + err.error, "error");
  }
  const blob = await res.blob();
  triggerDownload(blob, "checked.zip");
}

// Save Whole Zip
async function saveWholeZip() {
  const stego = document.getElementById("stego_input").files[0];
  if (!stego) return showToast("Stego file required", "error");

  const fd = new FormData();
  fd.append("stego", stego);
  fd.append("password", document.getElementById("extract_password").value || "");

  const res = await fetch("/download_payload", { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json();
    return showToast("Error: " + err.error, "error");
  }
  const blob = await res.blob();
  triggerDownload(blob, "extracted_payload.zip");
}



// History
document.getElementById("clear_history_btn").addEventListener("click", async () => {
  await fetch("/history_clear", { method: "POST" });
  document.getElementById("history_box").textContent = "";
  showToast("History cleared", "success");
});

// attach download button handlers
document.getElementById("save_selected_btn")?.addEventListener("click", saveSelected);
document.getElementById("save_checked_btn")?.addEventListener("click", saveChecked);
document.getElementById("save_zip_btn")?.addEventListener("click", saveWholeZip);
