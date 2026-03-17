// ── Selected option trackers ────────────────────────────
let selectedOptionId   = null;   // ← was: let selectedOption = ""
let selectedOptionText = "";     // ← new: track text separately

// ── Start countdown timer on page load ─────────────────
document.addEventListener("DOMContentLoaded", function () {
    startTimer();
});

// ── Select an option ────────────────────────────────────
function selectOption(element, optionId, optionText) {  // ← added optionId, optionText params
    // Remove selected from all options
    document.querySelectorAll(".pp-option")
            .forEach(opt => opt.classList.remove("selected"));

    // Mark this one as selected
    element.classList.add("selected");
    selectedOptionId   = optionId;    // ← was: selectedOption = optionValue
    selectedOptionText = optionText;  // ← new

    // Hide any previous error
    document.getElementById("voteError").classList.add("d-none");
}

// ── Show confirmation modal ─────────────────────────────
function confirmVote() {
    if (!selectedOptionId) {    // ← was: if (!selectedOption)
        document.getElementById("voteError")
                .classList.remove("d-none");
        return;
    }

    // Show selected option TEXT in modal
    document.getElementById("confirmOptionText")
            .textContent = selectedOptionText;  // ← was: selectedOption

    // Show Bootstrap modal
    const modal = new bootstrap.Modal(
        document.getElementById("confirmModal")
    );
    modal.show();
}

// ── Submit vote to API ──────────────────────────────────
async function submitVote() {
    const btn = document.getElementById("submitVoteBtn");

    // Close the modal
    bootstrap.Modal.getInstance(
        document.getElementById("confirmModal")
    ).hide();

    // Disable button
    btn.disabled = true;
    btn.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2"></span>
        Submitting...`;

    try {
        const response = await fetch(`/poll/${POLL_ID}/vote`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ option_id: selectedOptionId })  // ← was: option: selectedOption
        });

        const data = await response.json();

        if (response.ok) {
            btn.innerHTML = `
                <i class="bi bi-check-circle-fill me-2"></i>
                Vote Submitted!`;
            setTimeout(() => {
                window.location.href = `/poll/${POLL_ID}/results`;
            }, 1000);

        } else {
            if (data.is_expired) {
                window.location.href = data.results_link;
                return;
            }
            alert(data.error);
            btn.disabled = false;
            btn.innerHTML = `
                <i class="bi bi-send-fill me-2"></i>
                Submit Vote`;
        }

    } catch (error) {
        alert("Network error. Please try again.");
        btn.disabled = false;
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
        const now  = new Date();
        const end  = new Date(END_TIME);
        const diff = end - now;

        if (diff <= 0) {
            timerText.textContent = "Poll Ended";
            setTimeout(() => location.reload(), 2000);
            return;
        }

        const hours   = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);

        timerText.textContent =
            `${pad(hours)}h ${pad(minutes)}m ${pad(seconds)}s`;
    }

    function pad(num) {
        return String(num).padStart(2, "0");
    }

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