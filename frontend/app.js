// ── CellPlayer ────────────────────────────────────────────────────────────────

class CellPlayer {
  constructor(monitorId, displayName, containerEl) {
    this.monitorId = monitorId;
    this.displayName = displayName;
    this._chunks = [];
    this._activeChunk = null;
    this._hasFootage = true;

    // Build DOM: name label, video, overlay
    containerEl.innerHTML = '';
    containerEl.classList.add('cell');

    const nameEl = document.createElement('div');
    nameEl.className = 'cell-name';
    nameEl.textContent = displayName;
    containerEl.appendChild(nameEl);

    this._videoEl = document.createElement('video');
    this._videoEl.muted = true;
    this._videoEl.playsInline = true;
    this._videoEl.preload = 'auto';
    containerEl.appendChild(this._videoEl);

    this._overlayEl = document.createElement('div');
    this._overlayEl.className = 'cell-overlay';
    this._spinnerEl = document.createElement('div');
    this._spinnerEl.className = 'spinner';
    this._msgEl = document.createElement('div');
    this._msgEl.className = 'no-footage-msg';
    this._overlayEl.appendChild(this._spinnerEl);
    this._overlayEl.appendChild(this._msgEl);
    containerEl.appendChild(this._overlayEl);

    this._videoEl.addEventListener('waiting', () => this._showSpinner());
    this._videoEl.addEventListener('stalled', () => this._showSpinner());
    this._videoEl.addEventListener('playing', () => this._hideOverlay());
    this._videoEl.addEventListener('ended', () => this._onEnded());

    this._showSpinner();
  }

  loadChunks(chunks) {
    this._chunks = chunks.slice().sort((a, b) => a.start_ts - b.start_ts);
    this._activeChunk = null;
    this._hasFootage = chunks.length > 0;
    if (!this._hasFootage) {
      this.showNoFootage();
    }
  }

  seekTo(virtualTimeMs) {
    if (!this._hasFootage) return;
    const chunk = this._chunks.find(c => virtualTimeMs >= c.start_ts && virtualTimeMs < c.end_ts);
    if (!chunk) return;
    const offsetSecs = (virtualTimeMs - chunk.start_ts) / 1000;
    if (this._activeChunk && this._activeChunk.id === chunk.id) {
      this._videoEl.currentTime = offsetSecs;
    } else {
      this._activeChunk = chunk;
      this._showSpinner();
      this._videoEl.src = `/api/video/${chunk.id}`;
      this._videoEl.addEventListener('loadedmetadata', () => {
        this._videoEl.currentTime = offsetSecs;
      }, { once: true });
    }
  }

  play() {
    if (!this._hasFootage || !this._activeChunk) return;
    return this._videoEl.play().catch(() => {});
  }

  pause() {
    this._videoEl.pause();
  }

  get videoEl() { return this._videoEl; }
  get hasFootage() { return this._hasFootage; }
  get activeChunk() { return this._activeChunk; }

  get currentVirtualTimeMs() {
    if (!this._activeChunk) return null;
    return this._activeChunk.start_ts + this._videoEl.currentTime * 1000;
  }

  setPlaybackRate(rate) {
    this._videoEl.playbackRate = rate;
  }

  showNoFootage() {
    this._spinnerEl.style.display = 'none';
    this._msgEl.textContent = 'Sin footage';
    this._overlayEl.classList.remove('hidden');
  }

  _showSpinner() {
    this._spinnerEl.style.display = '';
    this._msgEl.textContent = '';
    this._overlayEl.classList.remove('hidden');
  }

  _hideOverlay() {
    this._overlayEl.classList.add('hidden');
  }

  _onEnded() {
    if (!this._activeChunk) return;
    const idx = this._chunks.indexOf(this._activeChunk);
    if (idx >= 0 && idx < this._chunks.length - 1) {
      const next = this._chunks[idx + 1];
      this._activeChunk = next;
      this._showSpinner();
      this._videoEl.src = `/api/video/${next.id}`;
      this._videoEl.addEventListener('loadedmetadata', () => {
        this._videoEl.currentTime = 0;
        this._videoEl.play().catch(() => {});
      }, { once: true });
    }
  }
}

// ── GridPlayer ────────────────────────────────────────────────────────────────

class GridPlayer {
  constructor(containerEl) {
    this._containerEl = containerEl;
    this._cells = new Map(); // monitorId → { cell: CellPlayer, el: HTMLElement }
  }

  activate(monitorId, displayName) {
    if (this._cells.has(monitorId)) return;
    if (this._cells.size >= 9) return;

    const el = document.createElement('div');
    this._containerEl.appendChild(el);
    const cell = new CellPlayer(monitorId, displayName, el);
    this._cells.set(monitorId, { cell, el });
    this._recalcLayout();
    this._updateToggles();
  }

  deactivate(monitorId) {
    const entry = this._cells.get(monitorId);
    if (!entry) return;
    entry.cell.pause();
    this._containerEl.removeChild(entry.el);
    this._cells.delete(monitorId);
    this._recalcLayout();
    this._updateToggles();
  }

  _recalcLayout() {
    const n = this._cells.size;
    let cols;
    if (n <= 1) cols = 1;
    else if (n <= 3) cols = n;
    else if (n === 4) cols = 2;
    else cols = 3;
    this._containerEl.setAttribute('data-cols', cols);
  }

  _updateToggles() {
    const atCap = this._cells.size >= 9;
    document.querySelectorAll('#camera-list input[type="checkbox"]').forEach(cb => {
      const mid = parseInt(cb.dataset.monitorId, 10);
      if (!this._cells.has(mid)) {
        cb.disabled = atCap;
      }
    });
  }

  async loadPeriod(fromMs, toMs) {
    const promises = [];
    for (const [monitorId, { cell }] of this._cells) {
      promises.push(
        fetch(`/api/monitors/${monitorId}/chunks?from_ts=${fromMs}&to_ts=${toMs}`)
          .then(r => r.ok ? r.json() : [])
          .then(chunks => cell.loadChunks(chunks))
          .catch(() => cell.loadChunks([]))
      );
    }
    await Promise.all(promises);
  }

  seekAll(virtualTimeMs) {
    for (const { cell } of this._cells.values()) {
      cell.seekTo(virtualTimeMs);
    }
  }

  playAll() {
    for (const { cell } of this._cells.values()) {
      cell.play();
    }
  }

  pauseAll() {
    for (const { cell } of this._cells.values()) {
      cell.pause();
    }
  }

  setPlaybackRate(rate) {
    for (const { cell } of this._cells.values()) {
      cell.setPlaybackRate(rate);
    }
  }

  get activeCells() {
    return [...this._cells.values()]
      .map(e => e.cell)
      .filter(c => c.hasFootage);
  }

  get masterCell() {
    return this.activeCells[0] || null;
  }

  get size() { return this._cells.size; }
}

// ── Scrubber ──────────────────────────────────────────────────────────────────

class Scrubber {
  constructor() {
    this._el = document.getElementById('scrubber');
    this._hStart = document.getElementById('h-start');
    this._hEnd = document.getElementById('h-end');
    this._rangeEl = document.getElementById('scrubber-range');
    this._leftEl = document.getElementById('scrubber-left');
    this._rightEl = document.getElementById('scrubber-right');
    this._lblRangeStart = document.getElementById('lbl-range-start');
    this._lblRangeEnd = document.getElementById('lbl-range-end');

    this._startPct = 0;
    this._endPct = 1;
    this._periodFromMs = null;
    this._periodToMs = null;
    this._dragging = null;

    this.onChange = null;

    this._hStart.addEventListener('mousedown', e => { this._dragging = 'start'; e.preventDefault(); });
    this._hEnd.addEventListener('mousedown', e => { this._dragging = 'end'; e.preventDefault(); });
    document.addEventListener('mousemove', e => this._onMouseMove(e));
    document.addEventListener('mouseup', () => { this._dragging = null; });

    // Click inside highlighted range → seek
    this._el.addEventListener('click', e => {
      if (!this._periodFromMs || this._dragging) return;
      const rect = this._el.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      if (pct >= this._startPct && pct <= this._endPct) {
        const virtualMs = this._periodFromMs + pct * (this._periodToMs - this._periodFromMs);
        if (this.onChange) this.onChange(this._startPct, this._endPct, virtualMs);
      }
    });
  }

  reset(periodFromMs, periodToMs) {
    this._periodFromMs = periodFromMs;
    this._periodToMs = periodToMs;
    this._startPct = 0;
    this._endPct = 1;
    this._updateDOM();
  }

  _onMouseMove(e) {
    if (!this._dragging || !this._periodFromMs) return;
    const rect = this._el.getBoundingClientRect();
    let pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    if (this._dragging === 'start') {
      pct = Math.min(pct, this._endPct - 0.01);
      this._startPct = pct;
    } else {
      pct = Math.max(pct, this._startPct + 0.01);
      this._endPct = pct;
    }
    this._updateDOM();
    const virtualMs = this._periodFromMs + this._startPct * (this._periodToMs - this._periodFromMs);
    if (this.onChange) this.onChange(this._startPct, this._endPct, virtualMs);
  }

  _updateDOM() {
    this._hStart.style.left = `${this._startPct * 100}%`;
    this._hEnd.style.left = `${this._endPct * 100}%`;
    this._leftEl.style.width = `${this._startPct * 100}%`;
    this._rightEl.style.width = `${(1 - this._endPct) * 100}%`;
    this._rightEl.style.right = '0';
    this._rightEl.style.left = 'auto';
    this._rangeEl.style.left = `${this._startPct * 100}%`;
    this._rangeEl.style.width = `${(this._endPct - this._startPct) * 100}%`;
    if (this._periodFromMs) {
      this._lblRangeStart.textContent = fmtTime(this.startMs);
      this._lblRangeEnd.textContent = fmtTime(this.endMs);
    }
  }

  get startMs() {
    if (!this._periodFromMs) return 0;
    return this._periodFromMs + this._startPct * (this._periodToMs - this._periodFromMs);
  }

  get endMs() {
    if (!this._periodToMs) return 0;
    return this._periodFromMs + this._endPct * (this._periodToMs - this._periodFromMs);
  }

  getRangeMs() {
    return { startMs: this.startMs, endMs: this.endMs };
  }
}

// ── ExportManager ─────────────────────────────────────────────────────────────

class ExportManager {
  constructor() {
    this._pollTimer = null;
  }

  async start(monitorIds, fromMs, toMs) {
    this._clearError();
    document.getElementById('download-links').innerHTML = '';

    let res;
    try {
      res = await fetch('/api/jobs/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ monitor_ids: monitorIds, from_ts: fromMs, to_ts: toMs }),
      });
    } catch {
      this._showError('Error de red al iniciar exportación.');
      return;
    }

    if (res.status === 409) {
      this._showError('Ya hay una exportación en curso.');
      return;
    }
    if (res.status === 507) {
      const d = await res.json().catch(() => ({}));
      this._showError(d.detail || 'Espacio insuficiente en disco.');
      return;
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      this._showError(d.detail || `Error ${res.status}`);
      return;
    }

    this._lock();
    document.getElementById('export-progress-wrapper').classList.remove('hidden');
    this._pollTimer = setInterval(() => this._poll(), 2000);
  }

  async _poll() {
    let data;
    try {
      const res = await fetch('/api/jobs/current');
      data = await res.json();
    } catch { return; }

    const pct = Math.round((data.progress || 0) * 100);
    document.getElementById('export-progress').value = data.progress || 0;
    document.getElementById('export-pct').textContent = `${pct}%`;

    if (data.status === 'done') {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
      document.getElementById('export-progress-wrapper').classList.add('hidden');
      this._renderDownloads(data.cameras || []);
      this._unlock();
    } else if (data.status === 'failed') {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
      document.getElementById('export-progress-wrapper').classList.add('hidden');
      this._showError(data.error || 'La exportación falló.');
      this._unlock();
    }
  }

  _renderDownloads(cameras) {
    const container = document.getElementById('download-links');
    container.innerHTML = '';
    for (const cam of cameras) {
      if (!cam.download_token) continue;
      const a = document.createElement('a');
      a.href = `/api/downloads/${cam.download_token}`;
      a.download = '';
      a.textContent = `⬇ ${cam.display_name}`;
      container.appendChild(a);
    }
  }

  async cancel() {
    clearInterval(this._pollTimer);
    this._pollTimer = null;
    await fetch('/api/jobs/current', { method: 'DELETE' }).catch(() => {});
    document.getElementById('export-progress-wrapper').classList.add('hidden');
    document.getElementById('export-progress').value = 0;
    document.getElementById('export-pct').textContent = '0%';
    this._unlock();
  }

  _lock() {
    document.body.classList.add('export-locked');
    document.getElementById('btn-export').disabled = true;
    document.getElementById('btn-cancel-export').disabled = false;
  }

  _unlock() {
    document.body.classList.remove('export-locked');
    updateExportButton();
  }

  _showError(msg) {
    const el = document.getElementById('export-error');
    el.textContent = msg;
    el.classList.remove('hidden');
  }

  _clearError() {
    document.getElementById('export-error').classList.add('hidden');
  }
}

// ── Sync loop ─────────────────────────────────────────────────────────────────

let _rafId = null;
const SYNC_TOLERANCE = 0.05;

function startSyncLoop(gridPlayer, scrubber) {
  if (_rafId) cancelAnimationFrame(_rafId);

  function loop() {
    const master = gridPlayer.masterCell;
    if (!master) return;
    const masterVid = master.videoEl;

    // Stop at scrubber end
    const virtualNow = master.currentVirtualTimeMs;
    if (virtualNow !== null && virtualNow >= scrubber.endMs) {
      gridPlayer.pauseAll();
      updatePlayPauseButton(false);
      return;
    }

    // Sync followers
    for (const cell of gridPlayer.activeCells) {
      if (cell === master) continue;
      if (Math.abs(cell.videoEl.currentTime - masterVid.currentTime) > SYNC_TOLERANCE) {
        cell.videoEl.currentTime = masterVid.currentTime;
      }
    }

    if (!masterVid.paused) {
      _rafId = requestAnimationFrame(loop);
    }
  }

  _rafId = requestAnimationFrame(loop);
}

function stopSyncLoop() {
  if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(ms) {
  if (!ms) return '';
  const d = new Date(ms);
  return d.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function parsePeriod() {
  const date = document.getElementById('date-picker').value;
  const from = document.getElementById('from-time').value || '00:00';
  const to = document.getElementById('to-time').value || '23:59';
  if (!date) return null;
  const fromMs = new Date(`${date}T${from}:00`).getTime();
  const toMs = new Date(`${date}T${to}:59`).getTime();
  if (isNaN(fromMs) || isNaN(toMs) || fromMs >= toMs) return null;
  return { fromMs, toMs };
}

function updateExportButton() {
  const btn = document.getElementById('btn-export');
  const hasActive = gridPlayer.activeCells.length > 0;
  btn.disabled = !hasActive || document.body.classList.contains('export-locked');
}

function updatePlayPauseButton(playing) {
  const btn = document.getElementById('btn-play-pause');
  btn.textContent = playing ? '⏸ Pausa' : '▶ Play';
}

// ── App initialization ────────────────────────────────────────────────────────

const gridPlayer = new GridPlayer(document.getElementById('grid-container'));
const scrubber = new Scrubber();
const exportManager = new ExportManager();

let _periodFromMs = null;
let _periodToMs = null;
let _playbackSpeed = 8;
let _isPlaying = false;

// Default date = today
document.getElementById('date-picker').value = new Date().toISOString().slice(0, 10);

// Load camera list
async function loadCameras() {
  try {
    const res = await fetch('/api/monitors');
    const monitors = await res.json();
    const list = document.getElementById('camera-list');
    list.innerHTML = '';
    for (const m of monitors) {
      const li = document.createElement('li');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.dataset.monitorId = m.id;
      cb.dataset.displayName = m.display_name;
      cb.addEventListener('change', () => {
        if (cb.checked) {
          gridPlayer.activate(m.id, m.display_name);
          if (_periodFromMs) {
            fetch(`/api/monitors/${m.id}/chunks?from_ts=${_periodFromMs}&to_ts=${_periodToMs}`)
              .then(r => r.ok ? r.json() : [])
              .then(chunks => {
                const entry = gridPlayer._cells.get(m.id);
                if (entry) entry.cell.loadChunks(chunks);
              });
          }
        } else {
          gridPlayer.deactivate(m.id);
        }
        updateExportButton();
      });
      const label = document.createElement('label');
      label.textContent = m.display_name;
      label.prepend(cb);
      li.appendChild(label);
      list.appendChild(li);
    }
  } catch (e) {
    console.error('Failed to load cameras', e);
  }
}

// Confirm period
document.getElementById('btn-confirm-period').addEventListener('click', async () => {
  const period = parsePeriod();
  if (!period) { alert('Fecha o rango horario inválido.'); return; }
  _periodFromMs = period.fromMs;
  _periodToMs = period.toMs;

  document.getElementById('lbl-period-start').textContent = fmtTime(_periodFromMs);
  document.getElementById('lbl-period-end').textContent = fmtTime(_periodToMs);

  scrubber.reset(_periodFromMs, _periodToMs);
  await gridPlayer.loadPeriod(_periodFromMs, _periodToMs);

  // Seek all cells to start of scrubber range
  gridPlayer.seekAll(scrubber.startMs);

  document.getElementById('btn-play-pause').disabled = false;
  updateExportButton();
});

// Scrubber change callback
scrubber.onChange = (startPct, endPct, seekMs) => {
  gridPlayer.seekAll(seekMs);
};

// Play / Pause
document.getElementById('btn-play-pause').addEventListener('click', () => {
  if (!_periodFromMs) return;
  _isPlaying = !_isPlaying;
  if (_isPlaying) {
    // Start from scrubber start position
    gridPlayer.seekAll(scrubber.startMs);
    setTimeout(() => {
      gridPlayer.setPlaybackRate(_playbackSpeed);
      gridPlayer.playAll();
      startSyncLoop(gridPlayer, scrubber);
      updatePlayPauseButton(true);
    }, 100);
  } else {
    stopSyncLoop();
    gridPlayer.pauseAll();
    updatePlayPauseButton(false);
  }
});

// Speed selector
document.getElementById('speed-btns').addEventListener('click', e => {
  const btn = e.target.closest('.speed-btn');
  if (!btn) return;
  _playbackSpeed = parseFloat(btn.dataset.speed);
  document.querySelectorAll('.speed-btn').forEach(b => b.classList.toggle('active', b === btn));
  gridPlayer.setPlaybackRate(_playbackSpeed);
});

// Export button
document.getElementById('btn-export').addEventListener('click', () => {
  const monitorIds = gridPlayer.activeCells.map(c => c.monitorId);
  if (!monitorIds.length) return;
  const { startMs, endMs } = scrubber.getRangeMs();
  exportManager.start(monitorIds, startMs, endMs);
});

// Cancel export
document.getElementById('btn-cancel-export').addEventListener('click', () => {
  exportManager.cancel();
});

// Indexer status polling
async function pollIndexerStatus() {
  try {
    const res = await fetch('/api/indexer/status');
    const data = await res.json();
    const el = document.getElementById('indexer-status');
    if (data.last_scan_at) {
      el.textContent = `Índice: ${data.total_chunks} clips · ${data.total_monitors} cámaras`;
    }
  } catch {}
}

// Bootstrap
loadCameras();
pollIndexerStatus();
setInterval(pollIndexerStatus, 30000);
