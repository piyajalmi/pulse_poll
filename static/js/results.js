// ── Chart instance ────────────────────────────────────────
let resultsChart = null;
let firebaseDB   = null;
let hasPollingStarted = false;

// ── Initialize on page load ───────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
    if (!SHOW_RESULTS) return;

    if (IS_CREATOR || IS_ADMIN) {
    fetchResults();

    if (!IS_EXPIRED) {
        initFirebase();
        startTimer();
    }
}
else{
    if (!IS_EXPIRED) {
        startTimer();
    }
}
});

// ── Initialize Firebase realtime listener ─────────────────
function initFirebase() {
    try {
        if (!firebase.apps.length) {
            firebase.initializeApp(firebaseConfig);
        }

        firebaseDB = firebase.database();

        const pollRef = firebaseDB.ref(
            `polls/${POLL_ID}/results`
        );

        pollRef.on(
            "value",
            function (snapshot) {
                const data = snapshot.val();
                if (!data) return;

                console.log("Firebase update received!", data);

                document.getElementById("loadingState")
                        .classList.add("d-none");
                document.getElementById("resultsContent")
                        .classList.remove("d-none");

                updateChart(data.results);
                updateBreakdown(data.results);
                updateTotalVotes(data.total_votes);
            },
            function (error) {
                console.error(
                    "Firebase listener read error:",
                    error
                );
                startPolling();
            }
        );

        console.log("Firebase listener active ✅");

    } catch(e) {
        console.error("Firebase error:", e);
        startPolling();
    }
}

// ── Fallback: Poll API every 5 seconds ────────────────────
function startPolling() {
    if (hasPollingStarted) return;
    hasPollingStarted = true;
    console.log("Falling back to API polling...");
    setInterval(fetchResults, 5000);
}

// ── Fetch initial results from API ────────────────────────
async function fetchResults() {
    try {
        const response = await fetch(
            `/api/poll/${POLL_TOKEN}/results`
        );
        const data = await response.json();

        if (!response.ok) {
            console.error("Error:", data.error);
            return;
        }

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

// ── Create or update Chart.js ─────────────────────────────
function updateChart(results) {
    if (!results || results.length === 0) return;

    const labels     = results.map(r => r.option);
    const voteCounts = results.map(r => r.votes);
    const colors     = generateColors(results.length);

    if (!resultsChart) {
        const ctx = document.getElementById("resultsChart")
                             .getContext("2d");
        resultsChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels:   labels,
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
                            label: function(context) {
                                const r = results[
                                    context.dataIndex
                                ];
                                return ` ${r.votes} votes `+
                                       `(${r.percentage}%)`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1,
                            color: "#64748b"
                        },
                        grid: { color: "#f1f5f9" }
                    },
                    x: {
                        ticks: {
                            color: "#1e1b4b",
                            font: { weight: "600" }
                        },
                        grid: { display: false }
                    }
                }
            }
        });
    } else {
        resultsChart.data.labels               = labels;
        resultsChart.data.datasets[0].data     = voteCounts;
        resultsChart.data.datasets[0].backgroundColor =
            colors.bg;
        resultsChart.update("active");
    }
}

// ── Update breakdown bars ─────────────────────────────────
function updateBreakdown(results) {
    if (!results) return;

    const container = document.getElementById(
        "optionBreakdown"
    );
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
                     style="width:${result.percentage}%">
                </div>
            </div>
        `;
        container.appendChild(row);
    });
}

// ── Update total votes number ─────────────────────────────
function updateTotalVotes(total) {
    document.getElementById("totalVotes")
            .textContent = total;
}

// ── Generate color palette ────────────────────────────────
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

// ── Countdown Timer ───────────────────────────────────────
function startTimer() {
    const timerText = document.getElementById("timerText");
    if (!timerText) return;

    function pad(n) {
        return String(n).padStart(2, "0");
    }

    function updateTimer() {
        const diff = new Date(END_TIME) - new Date();

        if (diff <= 0) {
            timerText.textContent = "Poll Ended";
            if (firebaseDB) {
                firebaseDB.ref(
                    `polls/${POLL_ID}/results`
                ).off();
            }
            setTimeout(() => location.reload(), 2000);
            return;
        }

        const days    = Math.floor(diff / 86400000);
        const hours   = Math.floor((diff % 86400000) / 3600000);
        const minutes = Math.floor((diff % 3600000) / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);

        let timeStr = '';

        if (days > 0) {
            timeStr = `${days}d ${hours}h ${minutes}m`;
        } else if (hours > 0) {
            timeStr = `${hours}h ${minutes}m ${pad(seconds)}s`;
        } else if (minutes > 0) {
            timeStr = `${minutes}m ${pad(seconds)}s`;
        } else {
            timeStr = `${seconds}s`;
        }

        timerText.textContent = timeStr;
    }

    updateTimer();
    setInterval(updateTimer, 1000);
}

// ── Copy link ─────────────────────────────────────────────
function copyLink() {
    const link = document.getElementById("shareLink").value;
    navigator.clipboard.writeText(link).then(() => {
        const msg = document.getElementById("copyMsg");
        msg.classList.remove("d-none");
        setTimeout(() => msg.classList.add("d-none"), 2000);
    });
}
