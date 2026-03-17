// ── Chart instance (kept outside so we can update it) ──
let pollChart = null;

// ── Run when page loads ────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {

    // Only draw chart if there are votes
    if (OPTIONS.length > 0) {
        drawChart(OPTIONS);
    }

    // Only connect WebSocket if poll is still active
    if (!IS_EXPIRED) {
        initWebSocket();
    }
});

// ── Draw or update the pie chart ───────────────────────
function drawChart(optionsData) {

    const ctx = document.getElementById("pollChart");
    if (!ctx) return;   // canvas not found (0 votes state)

    // Extract labels and data from options
    const labels = optionsData.map(o => o.text);
    const votes  = optionsData.map(o => o.votes);
    const colors = generateColors(optionsData.length);

    if (!pollChart) {
        // ── First time → create chart ──────────────────
        pollChart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data:                 votes,
                    backgroundColor:      colors.bg,
                    borderColor:          colors.border,
                    borderWidth:          2,
                    hoverOffset:          8,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            padding:   20,
                            font:      { size: 13 },
                            color:     "#1e1b4b",
                        }
                    },
                    tooltip: {
                        callbacks: {
                            // Show % in tooltip
                            label: function(context) {
                                const total = context.dataset
                                    .data.reduce((a, b) => a + b, 0);
                                const pct = total > 0
                                    ? Math.round(
                                        context.parsed / total * 100
                                      )
                                    : 0;
                                return ` ${context.parsed} votes (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });

    } else {
        // ── Chart exists → just update data ───────────
        pollChart.data.datasets[0].data = votes;
        pollChart.update("active");  // smooth animation
    }
}

// ── WebSocket for live updates ─────────────────────────
function initWebSocket() {

    const socket = io();

    // When connected → join this poll's room
    socket.on("connect", function () {
        socket.emit("join_poll", { poll_id: POLL_ID });
        console.log("Connected to poll room:", POLL_ID);
    });

    // When vote comes in → update chart
    socket.on("vote_update", function (data) {
        if (data.poll_id === POLL_ID) {
            console.log("Live vote received!", data);
            drawChart(data.results);
            updateDetails(data.results);
        }
    });

    socket.on("disconnect", function () {
        console.log("Disconnected from poll room");
    });

    // Leave room when user leaves page
    window.addEventListener("beforeunload", function () {
        socket.emit("leave_poll", { poll_id: POLL_ID });
    });
}

// ── Update Details tab progress bars live ─────────────
function updateDetails(results) {
    results.forEach(function(result) {
        // Find option row by matching text
        const rows = document.querySelectorAll(".pd-option-row");
        rows.forEach(function(row) {
            const textEl = row.querySelector(".pd-option-text");
            if (textEl && textEl.textContent.trim() === result.option) {

                // Update stat text
                row.querySelector(".pd-option-stat")
                   .textContent =
                   `${result.votes} votes (${result.percentage}%)`;

                // Update progress bar width
                row.querySelector(".pd-progress-fill")
                   .style.width = `${result.percentage}%`;
            }
        });
    });
}

// ── Generate purple color palette ─────────────────────
function generateColors(count) {
    const palette = [
        { bg: "rgba(79,70,229,0.8)",   border: "#4f46e5" },
        { bg: "rgba(139,92,246,0.8)",  border: "#8b5cf6" },
        { bg: "rgba(6,182,212,0.8)",   border: "#06b6d4" },
        { bg: "rgba(16,185,129,0.8)",  border: "#10b981" },
        { bg: "rgba(245,158,11,0.8)",  border: "#f59e0b" },
        { bg: "rgba(239,68,68,0.8)",   border: "#ef4444" },
    ];

    const bg     = [];
    const border = [];

    for (let i = 0; i < count; i++) {
        bg.push(palette[i % palette.length].bg);
        border.push(palette[i % palette.length].border);
    }

    return { bg, border };
}
// ── Copy share link ────────────────────────────────────
function copyLink() {
    const link = document.getElementById("shareLink").value;
    navigator.clipboard.writeText(link).then(() => {
        // Change icon to checkmark
        document.getElementById("copyIcon")
                .className = "bi bi-check2";

        // Show copied message
        const msg = document.getElementById("copyMsg");
        msg.classList.remove("d-none");

        // Reset after 2 seconds
        setTimeout(() => {
            document.getElementById("copyIcon")
                    .className = "bi bi-clipboard";
            msg.classList.add("d-none");
        }, 2000);
    });
}
