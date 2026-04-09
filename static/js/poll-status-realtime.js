(() => {
  const STATUS_CLASSES = [
    "mp-badge-active",
    "mp-badge-not-started",
    "mp-badge-expired",
    "db-badge-active",
    "db-badge-not-started",
    "db-badge-ended",
  ];

  function parseMs(value) {
    if (!value) return NaN;
    const ms = Date.parse(value);
    return Number.isFinite(ms) ? ms : NaN;
  }

  function computeStatus(startMs, endMs, nowMs) {
    if (Number.isFinite(endMs) && nowMs >= endMs) return "Expired";
    if (Number.isFinite(startMs) && nowMs < startMs) return "Not Started";
    return "Active";
  }

  function applyClasses(el, status) {
    for (const cls of STATUS_CLASSES) el.classList.remove(cls);

    const hasMpBase = el.classList.contains("mp-badge");
    const hasDbBase = el.classList.contains("db-poll-badge");

    if (hasMpBase) {
      if (status === "Active") el.classList.add("mp-badge-active");
      else if (status === "Not Started") el.classList.add("mp-badge-not-started");
      else el.classList.add("mp-badge-expired");
      return;
    }

    if (hasDbBase) {
      if (status === "Active") el.classList.add("db-badge-active");
      else if (status === "Not Started") el.classList.add("db-badge-not-started");
      else el.classList.add("db-badge-ended");
      return;
    }

    // Fallback to the admin-dashboard style mapping.
    if (status === "Active") el.classList.add("db-badge-active");
    else if (status === "Not Started") el.classList.add("mp-badge-not-started");
    else el.classList.add("mp-badge-expired");
  }

  function updateOne(el, nowMs) {
    const startMs = parseMs(el.getAttribute("data-poll-start"));
    const endMs = parseMs(el.getAttribute("data-poll-end"));
    const status = computeStatus(startMs, endMs, nowMs);

    const textEl = el.querySelector(".js-poll-status-text");
    if (textEl && textEl.textContent !== status) {
      textEl.textContent = status;
    }

    applyClasses(el, status);
  }

  function nextChangeDelayMs(el, nowMs) {
    const startMs = parseMs(el.getAttribute("data-poll-start"));
    const endMs = parseMs(el.getAttribute("data-poll-end"));

    let nextMs = Infinity;
    if (Number.isFinite(startMs) && startMs > nowMs) nextMs = Math.min(nextMs, startMs);
    if (Number.isFinite(endMs) && endMs > nowMs) nextMs = Math.min(nextMs, endMs);
    if (!Number.isFinite(nextMs) || nextMs === Infinity) return null;
    return Math.max(0, nextMs - nowMs);
  }

  function updateAll() {
    const nowMs = Date.now();
    const nodes = document.querySelectorAll(".js-poll-status[data-poll-start], .js-poll-status[data-poll-end]");
    for (const el of nodes) updateOne(el, nowMs);
    return nodes;
  }

  function scheduleNextTick(nodes) {
    const nowMs = Date.now();
    let nextDelay = null;

    for (const el of nodes) {
      const delay = nextChangeDelayMs(el, nowMs);
      if (delay == null) continue;
      if (nextDelay == null || delay < nextDelay) nextDelay = delay;
    }

    if (nextDelay == null) return;

    const delayWithBuffer = Math.min(nextDelay + 750, 2147483000);
    window.setTimeout(() => {
      const refreshedNodes = updateAll();
      scheduleNextTick(refreshedNodes);
    }, delayWithBuffer);
  }

  function init() {
    const nodes = updateAll();
    scheduleNextTick(nodes);
    window.setInterval(updateAll, 60000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

