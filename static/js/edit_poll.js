// ── Poll type tracker ───────────────────────────────────
let currentPollType = CURRENT_TYPE;

// ── Option counter ──────────────────────────────────────
let optionCount = 0;

// const IS_STARTED = "{{ is_started }}" === "True";
// ── Initialize page with existing options ───────────────
document.addEventListener("DOMContentLoaded", function () {

    // Load existing options from Flask
    EXISTING_OPTIONS.forEach(function(option) {
        addOption(option);   // pass existing data
    });

    setMinDateTime();
});

// ── Set poll type ────────────────────────────────────────
function setPollType(type) {
    currentPollType = type;
}

// ── Set minimum end date ─────────────────────────────────
function setMinDateTime() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById("pollEndDate").min = today;
}

// ── Add option row ───────────────────────────────────────
// existingOption = null for new options
// existingOption = {id, text, file_path, ...} for existing
function addOption(existingOption = null) {
    optionCount++;
    const container = document.getElementById("optionsContainer");
    const rowId     = `optionRow${optionCount}`;
    const fileId    = `fileInput${optionCount}`;
    const previewId = `filePreview${optionCount}`;

    const row = document.createElement("div");
    row.classList.add("cp-option-row");
    row.id = rowId;

    // Store option id and media_id as data attributes
    // so JS can send them when saving
    if (existingOption) {
        row.dataset.optionId = existingOption.id || '';
        row.dataset.mediaId  = existingOption.media_id || '';
    }

    // Check if existing option has a file
    const hasFile = existingOption &&
                    existingOption.file_path;

    row.innerHTML = `
        <!-- Text input + remove button -->
        <div class="cp-option-top">
            <input type="text"
                   class="cp-option-text"
                   placeholder="Option ${optionCount}"
                   value="${existingOption
                            ? existingOption.text : ''}"
                            ${IS_STARTED ? 'disabled' : ''}
                   maxlength="200">
                   ${!IS_STARTED ? `
            <button class="cp-remove-btn"
                    type="button"
                    onclick="removeOption('${rowId}')"
                    title="Remove">
                <i class="bi bi-x"></i>
            </button> ` : ''}
        </div>

        <div class="cp-option-divider"></div>

        <!-- File row -->
        <div class="cp-file-row">

            <input type="file"
                   id="${fileId}"
                   class="cp-file-input"
                   onchange="handleFileSelect(
                       '${fileId}', '${previewId}',
                       '${rowId}')">

            <button class="cp-file-btn"
                    type="button"
                    ${IS_STARTED ? 'disabled style="opacity:0.5;cursor:not-allowed;"' : ''}
                    onclick="${IS_STARTED ? '' : `document.getElementById('${fileId}').click()`}">
                <i class="bi bi-paperclip"></i>
                ${hasFile ? 'Change file' : 'Attach file'}
            </button>

            <!-- File preview -->
            <div class="cp-file-preview ${hasFile ? 'visible' : ''}"
                 id="${previewId}">
                <i class="bi bi-file-earmark me-1"></i>
                <span class="cp-file-name">
                    ${hasFile
                      ? existingOption.original_name
                      : ''}
                </span>
                <button class="cp-file-clear"
                        type="button"
                        onclick="clearFile(
                            '${fileId}',
                            '${previewId}',
                            '${rowId}')">
                    <i class="bi bi-x-circle"></i>
                </button>
            </div>

        </div>
    `;

    container.appendChild(row);
}

// ── Remove option row ────────────────────────────────────
function removeOption(rowId) {
    const allRows = document.querySelectorAll(".cp-option-row");
    if (allRows.length <= 2) {
        alert("A poll must have at least 2 options.");
        return;
    }
    document.getElementById(rowId).remove();
}

// ── Handle file selection ────────────────────────────────
function handleFileSelect(fileInputId, previewId, rowId) {
    const fileInput = document.getElementById(fileInputId);
    const preview   = document.getElementById(previewId);
    const file      = fileInput.files[0];

    if (!file) return;

    preview.querySelector(".cp-file-name").textContent =
        file.name;
    preview.classList.add("visible");

    // Mark that old file should be replaced
    // (remove_file = false because new file is coming)
    const row = document.getElementById(rowId);
    row.dataset.replaceFile = "true";
}

// ── Clear file ───────────────────────────────────────────
function clearFile(fileInputId, previewId, rowId) {
    const fileInput = document.getElementById(fileInputId);
    const preview   = document.getElementById(previewId);
    const row       = document.getElementById(rowId);

    fileInput.value = "";
    preview.querySelector(".cp-file-name").textContent = "";
    preview.classList.remove("visible");

    // Mark that existing file should be removed
    row.dataset.removeFile = "true";
    row.dataset.mediaId    = "";
}

// ── Read file as base64 ──────────────────────────────────
function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader  = new FileReader();
        reader.onload = () => {
            resolve(reader.result.split(',')[1]);
        };
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

// ── Collect all options ──────────────────────────────────
async function collectOptions() {
    const rows    = document.querySelectorAll(".cp-option-row");
    const options = [];

    for (const row of rows) {
        const textInput  = row.querySelector(".cp-option-text");
        const fileInput  = row.querySelector(".cp-file-input");
        const text       = textInput.value.trim();
        const file       = fileInput.files[0];

        // Read data attributes
        const optionId   = row.dataset.optionId  || null;
        const mediaId    = row.dataset.mediaId   || null;
        const removeFile = row.dataset.removeFile === "true";

        const option = {
            id:          optionId ? parseInt(optionId) : null,
            text:        text,
            media_id:    mediaId ? parseInt(mediaId) : null,
            remove_file: removeFile
        };

        // If new file chosen → read as base64
        if (file) {
            option.file_data  = await readFileAsBase64(file);
            option.file_name  = file.name;
            option.file_type  = file.type;
            option.file_size  = file.size;
        }

        options.push(option);
    }

    return options;
}

// ── Submit edit ──────────────────────────────────────────
async function submitEdit() {
    const question = document.getElementById("pollQuestion")
                             .value.trim();
    const endDateTime = document.getElementById("pollEndDate").value;
    const btn      = document.getElementById("savePollBtn");
    const message  = document.getElementById("formMessage");

    

    // Collect options
    const options = await collectOptions();

    const optionTexts = options
    .map(o => o.text.toLowerCase().trim())
    .filter(t => t.length > 0);

const uniqueTexts = new Set(optionTexts);
if (uniqueTexts.size !== optionTexts.length) {
    const optionsError = document.getElementById("optionsError");
    optionsError.textContent = "Options must be unique!";
    optionsError.classList.remove("d-none");
    return;
}
    // ── Validate ──────────────────────────────────────────
    let valid = true;

    const questionError = document.getElementById("questionError");
    if (!question) {
        questionError.classList.remove("d-none");
        valid = false;
    } else {
        questionError.classList.add("d-none");
    }

    const validOptions = options.filter(o =>
    (o.text && o.text.trim().length > 0) ||
    o.file_data ||
    (o.media_id !== null && o.media_id !== undefined)
);
    const optionsError = document.getElementById("optionsError");
    if (validOptions.length < 2) {
        optionsError.classList.remove("d-none");
        valid = false;
    } else {
        optionsError.classList.add("d-none");
    }

    const timeError = document.getElementById("timeError");
    if (!endDateTime) {
        timeError.classList.remove("d-none");
        valid = false;
    } else {
        timeError.classList.add("d-none");
    }

    if (!valid) return;

    // ── Disable button ────────────────────────────────────
    btn.disabled  = true;
    btn.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2">
        </span>Saving...`;

    const submitUrl = (typeof SUBMIT_URL !== "undefined" && SUBMIT_URL)
        ? SUBMIT_URL
        : `/dashboard/poll/${POLL_TOKEN}/edit`;

    const afterSaveUrl = submitUrl.startsWith("/admin/")
        ? "/admin/polls"
        : "/dashboard/polls";

    try {
        const response = await fetch(
            submitUrl, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({
                question:  question,
                poll_type: currentPollType,
                end_time:  endDateTime,
                options:   options
            })
        });

        const data = await response.json();

        if (response.ok) {
            message.className = "mt-3 pp-success";
            message.innerHTML = `
                <i class="bi bi-check-circle-fill me-2"></i>
                Poll updated! Redirecting...`;
            message.classList.remove("d-none");

            setTimeout(() => {
                window.location.href = afterSaveUrl;
            }, 1500);

        } else {
            message.className = "mt-3 pp-error";
            message.innerHTML = `
                <i class="bi bi-exclamation-circle-fill me-2">
                </i>${data.error}`;
            message.classList.remove("d-none");
            btn.disabled  = false;
            btn.innerHTML = `
                <i class="bi bi-check-circle me-2"></i>
                Save Changes`;
        }

    } catch (error) {
        message.className = "mt-3 pp-error";
        message.innerHTML = `
            <i class="bi bi-wifi-off me-2"></i>
            Network error. Please try again.`;
        message.classList.remove("d-none");
        btn.disabled  = false;
        btn.innerHTML = `
            <i class="bi bi-check-circle me-2"></i>
            Save Changes`;
    }
}
