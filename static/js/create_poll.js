// ── State ───────────────────────────────────────────────
let optionCount = 0;
let selectedPollType = 'single';

// ── Initialize on page load ─────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
    addOption();
    addOption();
    setMinDateTime();
});

// ── Set poll type ───────────────────────────────────────
function setPollType(type) {
    selectedPollType = type;
}

// ── Set minimum date to today ───────────────────────────
function setMinDateTime() {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    const minVal = now.toISOString().slice(0, 16);
    document.getElementById("pollStartDate").min = minVal;
    document.getElementById("pollEndDate").min   = minVal;
}

// ── Add a new option row ────────────────────────────────
function addOption() {
    optionCount++;
    const container = document.getElementById("optionsContainer");
    const row       = document.createElement("div");

    row.classList.add("cp-option-row");
    row.id = `optionRow${optionCount}`;

    row.innerHTML = `
        <!-- Text input + remove button -->
        <div class="cp-option-top">
            <input type="text"
                   class="cp-option-text"
                   id="optionText${optionCount}"
                   placeholder="Option ${optionCount}">
            <button class="cp-remove-btn"
                    type="button"
                    onclick="removeOption('optionRow${optionCount}')"
                    title="Remove option">
                <i class="bi bi-x"></i>
            </button>
        </div>

        <!-- Divider -->
        <div class="cp-option-divider"></div>

        <!-- File attach row -->
        <div class="cp-file-row">

            <!-- Hidden real file input -->
            <input type="file"
                   class="cp-file-input"
                   id="optionFile${optionCount}"
                   onchange="handleFileSelect(this, ${optionCount})">

            <!-- Custom styled button -->
            <button class="cp-file-btn"
                    type="button"
                    onclick="document.getElementById('optionFile${optionCount}').click()">
                <i class="bi bi-paperclip"></i>
                Attach file
            </button>

            <!-- File preview (hidden until file chosen) -->
            <div class="cp-file-preview"
                 id="filePreview${optionCount}">
                <i class="bi bi-file-earmark me-1"></i>
                <span class="cp-file-name"
                      id="fileName${optionCount}">
                </span>
                <button class="cp-file-clear"
                        type="button"
                        onclick="clearFile(${optionCount})"
                        title="Remove file">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
            </div>

        </div>
    `;

    container.appendChild(row);
}

// ── Remove an option row ────────────────────────────────
function removeOption(rowId) {
    const allRows = document.querySelectorAll(".cp-option-row");
    if (allRows.length <= 2) {
        alert("A poll must have at least 2 options.");
        return;
    }
    const row = document.getElementById(rowId);
    if (row) row.remove();
}

// ── Handle file selection ───────────────────────────────
function handleFileSelect(input, count) {
    const file    = input.files[0];
    const preview = document.getElementById(`filePreview${count}`);
    const nameEl  = document.getElementById(`fileName${count}`);

    if (file) {
        // Show preview with filename
        nameEl.textContent = file.name;
        preview.classList.add("visible");
    } else {
        clearFile(count);
    }
}

// ── Clear file selection ────────────────────────────────
function clearFile(count) {
    const input   = document.getElementById(`optionFile${count}`);
    const preview = document.getElementById(`filePreview${count}`);
    const nameEl  = document.getElementById(`fileName${count}`);

    input.value      = "";          // clear file input
    nameEl.textContent = "";
    preview.classList.remove("visible");
}

// ── Read file as base64 ─────────────────────────────────
function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload  = () => {
            // result is "data:image/jpeg;base64,/9j/4AAQ..."
            // we only want the part after the comma
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };

        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

// ── Collect all options with text + file data ───────────
async function collectOptions() {
    const rows    = document.querySelectorAll(".cp-option-row");
    const options = [];

    for (const row of rows) {
        const textInput = row.querySelector(".cp-option-text");
        const fileInput = row.querySelector(".cp-file-input");
        const text      = textInput ? textInput.value.trim() : "";
        const file      = fileInput && fileInput.files[0]
                          ? fileInput.files[0] : null;

        // Skip completely empty rows
        if (!text && !file) continue;

        const optionData = {
            text:          text,
            file_base64:   null,
            file_name:     null,
            file_type:     null,
            file_size:     null
        };

        if (file) {
            // Convert file to base64
            optionData.file_base64 = await readFileAsBase64(file);
            optionData.file_name   = file.name;
            optionData.file_type   = file.type;
            optionData.file_size   = file.size;
        }

        options.push(optionData);
    }

    return options;
}

// ── Validate form ───────────────────────────────────────
function validateForm(question, options, startDateTime, endDateTime) {
    let isValid = true;

    // Validate question
    const questionError = document.getElementById("questionError");
    if (!question) {
        questionError.classList.remove("d-none");
        isValid = false;
    } else {
        questionError.classList.add("d-none");
    }

    // Validate options — need at least 2 with text
    const optionsError  = document.getElementById("optionsError");
    const validOptions  = options.filter(o => 
        o.text || o.file_base64
    );
    if (validOptions.length < 2) {
        optionsError.classList.remove("d-none");
        isValid = false;
    } else {
        optionsError.classList.add("d-none");
    }

    // Validate start time
    const startError = document.getElementById("startError");
    if (!startDateTime || new Date(startDateTime) <= new Date()) {
        startError.classList.remove("d-none");
        isValid = false;
    } else {
        startError.classList.add("d-none");
    }

    // Validate end time
    const timeError = document.getElementById("timeError");
    if (!endDateTime || new Date(endDateTime) <= new Date(startDateTime)) {
        timeError.classList.remove("d-none");
        isValid = false;
    } else {
        timeError.classList.add("d-none");
    }

    return isValid;
}

// ── Submit poll ─────────────────────────────────────────
async function submitPoll() {
    const question      = document.getElementById("pollQuestion")
                                  .value.trim();
    const startRaw      = document.getElementById("pollStartDate")
                              .value;
    const endRaw        = document.getElementById("pollEndDate")
                              .value;
    const btn           = document.getElementById("createPollBtn");
    const message       = document.getElementById("formMessage");

    const startDateTime = startRaw || null;
    const endDateTime   = endRaw || null;
    // Collect options (async because of file reading)
    const options = await collectOptions();

        // Checking duplicate options
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
    // Validate
    if (!validateForm(question, options, startDateTime, endDateTime)) {
        return;
    }

    // Disable button + show spinner
    btn.disabled  = true;
    btn.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2"></span>
        Creating...`;

    try {
        const response = await fetch("/poll/create", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({
                question:   question,
                poll_type:  selectedPollType,
                options:    options,
                start_time: startDateTime,
                end_time:   endDateTime
            })
        });

        const data = await response.json();

        if (response.ok) {
            message.className = "mt-3 pp-success";
            message.innerHTML = `
                <i class="bi bi-check-circle-fill me-2"></i>
                Poll created! Redirecting...`;
            message.classList.remove("d-none");

            setTimeout(() => {
                window.location.href = `/dashboard/polls`;
            }, 1500);

        } else {
            message.className = "mt-3 pp-error";
            message.innerHTML = `
                <i class="bi bi-exclamation-circle-fill me-2"></i>
                ${data.error}`;
            message.classList.remove("d-none");
            btn.disabled  = false;
            btn.innerHTML = `
                <i class="bi bi-send-fill me-2"></i>Create Poll`;
        }

    } catch (error) {
        message.className = "mt-3 pp-error";
        message.innerHTML = `
            <i class="bi bi-wifi-off me-2"></i>
            Network error. Please try again.`;
        message.classList.remove("d-none");
        btn.disabled  = false;
        btn.innerHTML = `
            <i class="bi bi-send-fill me-2"></i>Create Poll`;
    }
}
