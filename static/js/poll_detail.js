let pollChart = null;
let firebaseDB = null;
let pollingStarted = false;

document.addEventListener("DOMContentLoaded", function () {
    applyResults(OPTIONS || []);

    if (!IS_EXPIRED) {
        initFirebaseRealtime();
    }
});

function initFirebaseRealtime() {
    try {
        if (!firebase.apps.length) {
            firebase.initializeApp(firebaseConfig);
        }

        firebaseDB = firebase.database();
        const pollRef = firebaseDB.ref(`polls/${POLL_ID}/results`);

        pollRef.on(
            "value",
            function (snapshot) {
                const data = snapshot.val();
                if (!data || !Array.isArray(data.results)) return;
                applyResults(data.results, data.total_votes);
            },
            function (error) {
                console.error("Firebase listener error:", error);
                startPolling();
            }
        );
    } catch (error) {
        console.error("Firebase init error:", error);
        startPolling();
    }
}

function startPolling() {
    if (pollingStarted) return;
    pollingStarted = true;
    fetchLatestResults();
    setInterval(fetchLatestResults, 5000);
}

async function fetchLatestResults() {
    try {
        const response = await fetch(`/api/poll/${POLL_TOKEN}/results`);
        const data = await response.json();
        if (!response.ok || !Array.isArray(data.results)) return;
        applyResults(data.results, data.total_votes);
    } catch (error) {
        console.error("Polling fetch error:", error);
    }
}

function applyResults(results, totalVotesOverride = null) {
    const optionsData = (results || []).map((item) => ({
        text: item.option,
        votes: Number(item.votes || 0),
        percentage: Number(item.percentage || 0),
    }));

    const totalVotes = totalVotesOverride !== null
        ? Number(totalVotesOverride || 0)
        : optionsData.reduce((sum, item) => sum + item.votes, 0);

    updateTotalVotes(totalVotes);
    updateDetails(optionsData);
    drawChart(optionsData);
    toggleEmptyStates(totalVotes);
}

function drawChart(optionsData) {
    const canvas = document.getElementById("pollChart");
    if (!canvas) return;

    const labels = optionsData.map((o) => o.text);
    const votes = optionsData.map((o) => o.votes);
    const colors = generateColors(optionsData.length || 1);

    if (!pollChart) {
        pollChart = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: votes,
                    backgroundColor: colors.bg,
                    borderColor: colors.border,
                    borderWidth: 2,
                    hoverOffset: 8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            padding: 20,
                            font: { size: 13 },
                            color: "#1e1b4b",
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const total = context.dataset.data
                                    .reduce((a, b) => a + b, 0);
                                const pct = total > 0
                                    ? Math.round(context.parsed / total * 100)
                                    : 0;
                                return ` ${context.parsed} votes (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });
    } else {
        pollChart.data.labels = labels;
        pollChart.data.datasets[0].data = votes;
        pollChart.data.datasets[0].backgroundColor = colors.bg;
        pollChart.data.datasets[0].borderColor = colors.border;
        pollChart.update("active");
    }
}

function updateDetails(optionsData) {
    const rows = document.querySelectorAll(".pd-option-row");
    rows.forEach(function (row) {
        const optionTextEl = row.querySelector(".pd-option-text");
        const statEl = row.querySelector(".pd-option-stat");
        const barEl = row.querySelector(".pd-progress-fill");
        if (!optionTextEl || !statEl || !barEl) return;

        const optionText = optionTextEl.textContent.trim();
        const match = optionsData.find((o) => o.text === optionText);
        if (!match) return;

        statEl.textContent = `${match.votes} votes (${match.percentage}%)`;
        barEl.style.width = `${match.percentage}%`;
    });
}

function updateTotalVotes(totalVotes) {
    const totalVotesEl = document.getElementById("pollTotalVotes");
    if (!totalVotesEl) return;
    totalVotesEl.textContent = String(totalVotes);
}

function toggleEmptyStates(totalVotes) {
    const chartEmptyState = document.getElementById("chartEmptyState");
    const noVotesHint = document.getElementById("noVotesHint");

    if (chartEmptyState) {
        chartEmptyState.classList.toggle("d-none", totalVotes > 0);
    }
    if (noVotesHint) {
        noVotesHint.classList.toggle("d-none", totalVotes > 0);
    }
}

function generateColors(count) {
    const palette = [
        { bg: "rgba(79,70,229,0.8)", border: "#4f46e5" },
        { bg: "rgba(139,92,246,0.8)", border: "#8b5cf6" },
        { bg: "rgba(6,182,212,0.8)", border: "#06b6d4" },
        { bg: "rgba(16,185,129,0.8)", border: "#10b981" },
        { bg: "rgba(245,158,11,0.8)", border: "#f59e0b" },
        { bg: "rgba(239,68,68,0.8)", border: "#ef4444" },
    ];

    const bg = [];
    const border = [];
    for (let i = 0; i < count; i++) {
        bg.push(palette[i % palette.length].bg);
        border.push(palette[i % palette.length].border);
    }
    return { bg, border };
}

function copyLink() {
    const link = document.getElementById("shareLink").value;
    navigator.clipboard.writeText(link).then(() => {
        document.getElementById("copyIcon").className = "bi bi-check2";
        const msg = document.getElementById("copyMsg");
        msg.classList.remove("d-none");
        setTimeout(() => {
            document.getElementById("copyIcon").className = "bi bi-clipboard";
            msg.classList.add("d-none");
        }, 2000);
    });
}
