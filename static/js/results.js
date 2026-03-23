// ── Chart instance ──────────────────────────────────────
let resultsChart = null;
let socket       = null;

// ── Initialize on page load ─────────────────────────────
document.addEventListener("DOMContentLoaded", function () {

    // Always fetch results once on load
    fetchResults();

    // Only connect WebSocket if poll is still active
    if (!IS_EXPIRED) {
        initWebSocket();
        startTimer();
    }
});

// ── Initialize WebSocket connection ─────────────────────
function initWebSocket() {

    // Connect to the server
    socket = io({
    transports: ['websocket'],
    upgrade: false
});

    // ── When connected → join this poll's room ──────────
    socket.on("connect", function () {
        console.log("WebSocket connected!");
        socket.emit("join_poll", { poll_id: POLL_ID });
    });

    // ── When server emits vote_update → update UI ───────
    socket.on("vote_update", function (data) {
        console.log("Live update received!", data);

        if (String(data.poll_id) === String(POLL_ID)) {
            updateChart(data.results);
            updateBreakdown(data.results);
            updateTotalVotes(data.total_votes);
        }
    });

    // ── Handle disconnection ─────────────────────────────
    socket.on("disconnect", function () {
        console.log("WebSocket disconnected.");
    });

    // ── Leave room when user leaves page ─────────────────
    window.addEventListener("beforeunload", function () {
        if (socket) {
            socket.emit("leave_poll", { poll_id: POLL_ID });
        }
    });
}

// ── Fetch initial results from API ──────────────────────
async function fetchResults() {
    try {
        const response = await fetch(
            `/api/poll/${POLL_ID}/results`
        );
        const data = await response.json();

        if (!response.ok) {
            console.error("Error:", data.error);
            return;
        }

        // Show results, hide loader
        document.getElementById("loadingState")
                .classList.add("d-none");
        document.getElementById("resultsContent")
                .classList.remove("d-none");

        updateChart(data.results);
        updateBreakdown(data.results);
        updateTotalVotes(data.total_votes);

    } catch (error) {
        console.error("Network error:", error);
    }
}

// ── Create or update Chart.js ────────────────────────────
function updateChart(results) {
    const labels     = results.map(r => r.option);
    const voteCounts = results.map(r => r.votes);
    const colors     = generateColors(results.length);

    if (!resultsChart) {
        const ctx = document.getElementById("resultsChart")
                             .getContext("2d");
        resultsChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label:           "Votes",
                    data:            voteCounts,
                    backgroundColor: colors.bg,
                    borderColor:     colors.border,
                    borderWidth:     2,
                    borderRadius:    8,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const r = results[context.dataIndex];
                                return ` ${r.votes} votes (${r.percentage}%)`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, color: "#64748b" },
                        grid:  { color: "#f1f5f9" }
                    },
                    x: {
                        ticks: { color: "#1e1b4b",
                                 font: { weight: "600" } },
                        grid:  { display: false }
                    }
                }
            }
        });
    } else {
        resultsChart.data.datasets[0].data = voteCounts;
        resultsChart.update("active");
    }
}

// ── Update breakdown bars ────────────────────────────────
function updateBreakdown(results) {
    const container = document.getElementById("optionBreakdown");
    container.innerHTML = "";

    results.forEach(result => {
        const row = document.createElement("div");
        row.classList.add("pp-result-row");
        row.innerHTML = `
            <div class="pp-result-label">
                <span>${result.option}</span>
                <span>${result.votes} votes
                      (${result.percentage}%)</span>
            </div>
            <div class="pp-result-bar-bg">
                <div class="pp-result-bar-fill"
                     style="width: ${result.percentage}%">
                </div>
            </div>
        `;
        container.appendChild(row);
    });
}

// ── Update total votes ───────────────────────────────────
function updateTotalVotes(total) {
    document.getElementById("totalVotes").textContent = total;
}

// ── Generate colors ──────────────────────────────────────
function generateColors(count) {
    const baseColors = [
        { bg: "rgba(79,70,229,0.8)",   border: "#4f46e5" },
        { bg: "rgba(129,140,248,0.8)", border: "#818cf8" },
        { bg: "rgba(167,139,250,0.8)", border: "#a78bfa" },
        { bg: "rgba(196,181,253,0.8)", border: "#c4b5fd" },
        { bg: "rgba(99,102,241,0.8)",  border: "#6366f1" },
    ];
    const bg = [], border = [];
    for (let i = 0; i < count; i++) {
        bg.push(baseColors[i % baseColors.length].bg);
        border.push(baseColors[i % baseColors.length].border);
    }
    return { bg, border };
}

// ── Countdown Timer ──────────────────────────────────────
function startTimer() {
    const timerText = document.getElementById("timerText");
    if (!timerText) return;

    function updateTimer() {
        const diff = new Date(END_TIME) - new Date();
        if (diff <= 0) {
            timerText.textContent = "Poll Ended";
            if (socket) socket.disconnect();
            setTimeout(() => location.reload(), 2000);
            return;
        }
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        timerText.textContent =
            `${pad(h)}h ${pad(m)}m ${pad(s)}s`;
    }

    function pad(n) { return String(n).padStart(2, "0"); }
    updateTimer();
    setInterval(updateTimer, 1000);
}

// ── Copy link ────────────────────────────────────────────
function copyLink() {
    const link = document.getElementById("shareLink").value;
    navigator.clipboard.writeText(link).then(() => {
        const msg = document.getElementById("copyMsg");
        msg.classList.remove("d-none");
        setTimeout(() => msg.classList.add("d-none"), 2000);
    });
}