// ── State ───────────────────────────────────────────────
let selectedOptionIds  = [];      // array for multiple choice
let selectedOptionText = "";      // for modal display

// ── Initialize ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
    startTimer();
});

// ── Generate UUID (submission_id) ───────────────────────
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
        .replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
}

// ── Select / Deselect an option ─────────────────────────
function selectOption(element, optionId, optionText, pollType) {

    if (pollType === 'single') {
        // ── Single choice ──────────────────────────────
        // Remove selected from ALL options
        document.querySelectorAll(".pp-option")
                .forEach(opt => opt.classList.remove("selected"));

        // Select this one
        element.classList.add("selected");
        selectedOptionIds  = [optionId];
        selectedOptionText = optionText;

    } else {
        // ── Multiple choice ────────────────────────────
        const index = selectedOptionIds.indexOf(optionId);

        if (index === -1) {
            // Not selected → ADD it
            element.classList.add("selected");
            selectedOptionIds.push(optionId);

            // Update checkbox icon
            const checkbox = element.querySelector(
                ".pp-option-checkbox i"
            );
            if (checkbox) {
                checkbox.className = "bi bi-check-square-fill";
            }
        } else {
            // Already selected → REMOVE it
            element.classList.remove("selected");
            selectedOptionIds.splice(index, 1);

            // Reset checkbox icon
            const checkbox = element.querySelector(
                ".pp-option-checkbox i"
            );
            if (checkbox) {
                checkbox.className = "bi bi-square";
            }
        }

        // Update selectedOptionText for modal
        selectedOptionText = selectedOptionIds.length > 0
            ? `${selectedOptionIds.length} option(s) selected`
            : "";
    }

    // Hide error
    document.getElementById("voteError")
            .classList.add("d-none");
}

// ── Show confirmation modal ─────────────────────────────
function confirmVote() {
    if (selectedOptionIds.length === 0) {
        document.getElementById("voteError")
                .classList.remove("d-none");
        return;
    }

    document.getElementById("confirmOptionText")
            .textContent = selectedOptionText;

    const modal = new bootstrap.Modal(
        document.getElementById("confirmModal")
    );
    modal.show();
}

// ── Submit vote ─────────────────────────────────────────
async function submitVote() {
    const btn = document.getElementById("submitVoteBtn");

    // Close modal
    bootstrap.Modal.getInstance(
        document.getElementById("confirmModal")
    ).hide();

    // Disable button
    btn.disabled  = true;
    btn.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2">
        </span>Submitting...`;

    // Generate unique submission_id
    const submissionId = generateUUID();

    try {
        const response = await fetch(`/poll/${POLL_ID}/vote`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({
                option_ids:    selectedOptionIds,  // ← array
                submission_id: submissionId        // ← UUID
            })
        });

        const data = await response.json();

        if (response.ok) {
            btn.innerHTML = `
                <i class="bi bi-check-circle-fill me-2"></i>
                Vote Submitted!`;
            setTimeout(() => {
                window.location.href =
                    `/poll/${POLL_ID}/results`;
            }, 1000);

        } else {
            if (data.is_expired) {
                window.location.href = data.results_link;
                return;
            }
            alert(data.error);
            btn.disabled  = false;
            btn.innerHTML = `
                <i class="bi bi-send-fill me-2"></i>
                Submit Vote`;
        }

    } catch (error) {
        alert("Network error. Please try again.");
        btn.disabled  = false;
        btn.innerHTML = `
            <i class="bi bi-send-fill me-2"></i>
            Submit Vote`;
    }
}

// ── Countdown Timer ─────────────────────────────────────
function startTimer() {
    const timerText = document.getElementById("timerText");
    if (!timerText) return;

    function updateTimer() {
        const diff = new Date(END_TIME) - new Date();
        if (diff <= 0) {
            timerText.textContent = "Poll Ended";
            setTimeout(() => location.reload(), 2000);
            return;
        }
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000)   / 1000);
        timerText.textContent =
            `${pad(h)}h ${pad(m)}m ${pad(s)}s`;
    }

    function pad(n) { return String(n).padStart(2, "0"); }
    updateTimer();
    setInterval(updateTimer, 1000);
}

// ── Copy share link ─────────────────────────────────────
function copyLink() {
    const link = document.getElementById("shareLink").value;
    navigator.clipboard.writeText(link).then(() => {
        const msg = document.getElementById("copyMsg");
        msg.classList.remove("d-none");
        setTimeout(() => msg.classList.add("d-none"), 2000);
    });
}