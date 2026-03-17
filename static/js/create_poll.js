// ── Initialize page with 2 default options ─────────────
document.addEventListener("DOMContentLoaded", function () {
    addOption();
    addOption();
    setMinDateTime();
});

// ── Set minimum date/time to now ────────────────────────
function setMinDateTime() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById("pollStartDate").min = today;
    document.getElementById("pollEndDate").min = today;
}

// ── Add a new option input row ──────────────────────────
let optionCount = 0;

function addOption() {
    optionCount++;
    const container = document.getElementById("optionsContainer");

    const row = document.createElement("div");
    row.classList.add("option-row");
    row.id = `optionRow${optionCount}`;

    row.innerHTML = `
        <input
            type="text"
            class="option-input"
            placeholder="Option ${optionCount}"
            maxlength="100">
        <button
            class="btn-remove-option"
            onclick="removeOption('optionRow${optionCount}')"
            title="Remove option">
            <i class="bi bi-x"></i>
        </button>
    `;

    container.appendChild(row);
}

// ── Remove an option input row ──────────────────────────
function removeOption(rowId) {
    const allRows = document.querySelectorAll(".option-row");

    // Always keep at least 2 options
    if (allRows.length <= 2) {
        alert("A poll must have at least 2 options.");
        return;
    }

    const row = document.getElementById(rowId);
    if (row) row.remove();
}

// ── Collect all option values ───────────────────────────
function getOptions() {
    const inputs = document.querySelectorAll(".option-input");
    const options = [];
    inputs.forEach(input => {
        const val = input.value.trim();
        if (val) options.push(val);
    });
    return options;
}

// ── Validate the form ───────────────────────────────────

function validateForm(question, options, startDateTime, endDateTime) {
    let isValid = true;

    // Validate question
    const questionInput = document.getElementById("pollQuestion");
    if (!question) {
        questionInput.classList.add("is-invalid");
        isValid = false;
    } else {
        questionInput.classList.remove("is-invalid");
    }

    // Validate options
    const optionsError = document.getElementById("optionsError");
    if (options.length < 2) {
        optionsError.classList.remove("d-none");
        isValid = false;
    } else {
        optionsError.classList.add("d-none");
    }

    // Validate start time
    const startError = document.getElementById("startError");
    if (!startDateTime) {
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
// ── Submit the poll to the API ──────────────────────────
async function submitPoll() {
    const question   = document.getElementById("pollQuestion")
                                .value.trim();
    const options    = getOptions();

    // ── Combine date + time into one string ───────────────
    const startDate  = document.getElementById("pollStartDate").value;
    const startTime  = document.getElementById("pollStartTime").value;
    const endDate    = document.getElementById("pollEndDate").value;
    const endTime    = document.getElementById("pollEndTime").value;

    // Format: "2026-03-16T10:00" ← what Flask expects
    const startDateTime = (startDate && startTime)
                          ? `${startDate}T${startTime}`
                          : "";
    const endDateTime   = (endDate && endTime)
                          ? `${endDate}T${endTime}`
                          : "";

    const btn     = document.getElementById("createPollBtn");
    const message = document.getElementById("formMessage");

    // Run validation
    if (!validateForm(question, options,
                      startDateTime, endDateTime)) return;

    // Disable button
    btn.disabled = true;
    btn.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2">
        </span>Creating...`;

    try {
        const response = await fetch("/poll/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question:   question,
                options:    options,
                start_time: startDateTime,   // ← sending start
                end_time:   endDateTime      // ← sending end
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
            btn.disabled = false;
            btn.innerHTML = `
                <i class="bi bi-send-fill me-2"></i>
                Create Poll`;
        }

    } catch (error) {
        message.className = "mt-3 pp-error";
        message.innerHTML = `
            <i class="bi bi-wifi-off me-2"></i>
            Network error. Please try again.`;
        message.classList.remove("d-none");
        btn.disabled = false;
        btn.innerHTML = `
            <i class="bi bi-send-fill me-2"></i>
            Create Poll`;
    }
}
