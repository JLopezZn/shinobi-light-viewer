const API = "/api";

let activeMonitorId = null;
let activeDate = todayISO();
let pollTimer = null;

// ── Helpers ────────────────────────────────────────────────────────────────

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function dayBoundsMs(dateISO) {
  const start = new Date(`${dateISO}T00:00:00`).getTime();
  const end   = new Date(`${dateISO}T23:59:59`).getTime();
  return { start, end };
}

function timeToMs(dateISO, timeStr) {
  return new Date(`${dateISO}T${timeStr}:00`).getTime();
}

function showError(msg) {
  const el = document.getElementById("error-banner");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 6000);
}

function hideError() {
  document.getElementById("error-banner").classList.add("hidden");
}

// ── Camera list ────────────────────────────────────────────────────────────

async function loadCameras() {
  const res = await fetch(`${API}/monitors`);
  if (!res.ok) { showError("Failed to load cameras."); return; }
  const monitors = await res.json();
  const ul = document.getElementById("camera-list");
  ul.innerHTML = "";
  for (const m of monitors) {
    const li = document.createElement("li");
    li.textContent = m.display_name;
    li.dataset.id = m.id;
    li.addEventListener("click", () => selectCamera(m.id, li));
    ul.appendChild(li);
  }
}

function selectCamera(id, liEl) {
  document.querySelectorAll("#camera-list li").forEach(el => el.classList.remove("active"));
  liEl.classList.add("active");
  activeMonitorId = id;
  loadTimeline();
}

// ── Timeline ───────────────────────────────────────────────────────────────

async function loadTimeline() {
  if (!activeMonitorId || !activeDate) return;
  const { start, end } = dayBoundsMs(activeDate);
  const res = await fetch(`${API}/monitors/${activeMonitorId}/chunks?from_ts=${start}&to_ts=${end}`);
  if (!res.ok) { showError("Failed to load timeline."); return; }
  const chunks = await res.json();
  renderTimeline(chunks, start, end);
  updateJobButtons(chunks);
}

function renderTimeline(chunks, dayStart, dayEnd) {
  const bar = document.getElementById("timeline-bar");
  bar.innerHTML = "";
  const totalMs = dayEnd - dayStart;

  for (const chunk of chunks) {
    const left = ((chunk.start_ts - dayStart) / totalMs) * 100;
    const width = ((chunk.end_ts - chunk.start_ts) / totalMs) * 100;
    const div = document.createElement("div");
    div.className = `chunk ${chunk.availability}`;
    div.style.left = `${Math.max(0, left)}%`;
    div.style.width = `${Math.max(0.1, width)}%`;
    if (chunk.availability === "unavailable") {
      div.title = "This segment is no longer available on disk";
    }
    bar.appendChild(div);
  }

  renderTimeLabels();
}

function renderTimeLabels() {
  const labels = document.getElementById("time-labels");
  labels.innerHTML = "";
  for (let h = 0; h <= 24; h += 4) {
    const span = document.createElement("span");
    span.textContent = `${String(h).padStart(2, "0")}:00`;
    labels.appendChild(span);
  }
}

function updateJobButtons(chunks) {
  const hasAvailable = chunks.some(c => c.availability === "available");
  document.getElementById("btn-export").disabled = !hasAvailable;
  document.getElementById("btn-timelapse").disabled = !hasAvailable;
}

// ── Indexer status ─────────────────────────────────────────────────────────

async function refreshIndexerStatus() {
  const res = await fetch(`${API}/indexer/status`);
  if (!res.ok) return;
  const data = await res.json();
  const el = document.getElementById("indexer-status");
  const lastScan = data.last_scan_at
    ? `${Math.round((Date.now() - data.last_scan_at) / 1000)}s ago`
    : "never";
  el.textContent = `Last scan: ${lastScan}\nNext in: ${data.next_scan_in_seconds ?? "—"}s\n${data.total_chunks} chunks (${data.unavailable_chunks} unavailable)`;
}

// ── Job submission ─────────────────────────────────────────────────────────

async function submitJob(type) {
  if (!activeMonitorId) return;
  const fromMs = timeToMs(activeDate, document.getElementById("from-time").value);
  const toMs   = timeToMs(activeDate, document.getElementById("to-time").value);

  hideError();
  const res = await fetch(`${API}/jobs/${type}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ monitor_id: activeMonitorId, from_ts: fromMs, to_ts: toMs }),
  });

  if (res.status === 202) {
    showJobPanel(type === "export" ? "Exporting…" : "Generating timelapse…");
    startPolling();
  } else {
    const data = await res.json().catch(() => ({}));
    showError(data.detail || `Error ${res.status}`);
  }
}

// ── Progress polling ───────────────────────────────────────────────────────

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollJob, 2000);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function pollJob() {
  const res = await fetch(`${API}/jobs/current`);
  if (!res.ok) return;
  const data = await res.json();

  const progress = document.getElementById("job-progress");
  progress.value = data.progress ?? 0;

  if (data.status === "done") {
    stopPolling();
    showDownloadLink(data.download_token);
  } else if (data.status === "failed") {
    stopPolling();
    hideJobPanel();
    showError(data.error || "Job failed.");
  } else if (data.status === "idle") {
    stopPolling();
    hideJobPanel();
  }
}

// ── Job panel UI ───────────────────────────────────────────────────────────

function showJobPanel(label) {
  document.getElementById("job-label").textContent = label;
  document.getElementById("job-progress").value = 0;
  document.getElementById("download-link").classList.add("hidden");
  document.getElementById("job-panel").classList.remove("hidden");
  document.getElementById("btn-export").disabled = true;
  document.getElementById("btn-timelapse").disabled = true;
}

function hideJobPanel() {
  stopPolling();
  document.getElementById("job-panel").classList.add("hidden");
  document.getElementById("btn-export").disabled = false;
  document.getElementById("btn-timelapse").disabled = false;
}

function showDownloadLink(token) {
  const link = document.getElementById("download-link");
  link.href = `${API}/downloads/${token}`;
  link.classList.remove("hidden");
  document.getElementById("job-label").textContent = "Ready to download";
  link.onclick = () => setTimeout(hideJobPanel, 500);
}

async function cancelJob() {
  await fetch(`${API}/jobs/current`, { method: "DELETE" });
  stopPolling();
  hideJobPanel();
}

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const datePicker = document.getElementById("date-picker");
  datePicker.value = activeDate;
  datePicker.addEventListener("change", e => {
    activeDate = e.target.value;
    loadTimeline();
  });

  document.getElementById("btn-export").addEventListener("click", () => submitJob("export"));
  document.getElementById("btn-timelapse").addEventListener("click", () => submitJob("timelapse"));
  document.getElementById("btn-cancel").addEventListener("click", cancelJob);

  loadCameras();
  refreshIndexerStatus();
  setInterval(refreshIndexerStatus, 10_000);
});
