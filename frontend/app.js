// ── CellPlayer ────────────────────────────────────────────────────────────────

class CellPlayer {
  constructor(monitorId, displayName, containerEl) {
    this.monitorId = monitorId;
    this.displayName = displayName;
    this._chunks = [];
    this._activeChunk = null;
    this._hasFootage = true;
    this._spinnerTimer = null;

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
    this._videoEl.addEventListener('canplay', () => this._hideOverlay());
    this._videoEl.addEventListener('playing', () => this._hideOverlay());
    this._videoEl.addEventListener('ended', () => this._onEnded());

    this._showSpinner(true);
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
    let chunk = this._chunks.find(c => virtualTimeMs >= c.start_ts && virtualTimeMs < c.end_ts);
    let offsetSecs = 0;
    if (!chunk) {
      // Requested instant falls in a gap or before/after all footage —
      // jump forward to the next available chunk instead of hanging forever.
      chunk = this._chunks.find(c => c.start_ts > virtualTimeMs);
      if (!chunk) {
        this._activeChunk = null;
        this._videoEl.pause();
        this.showNoFootage();
        return;
      }
    } else {
      offsetSecs = (virtualTimeMs - chunk.start_ts) / 1000;
    }
    if (this._activeChunk && this._activeChunk.id === chunk.id) {
      this._videoEl.currentTime = offsetSecs;
    } else {
      const wasPlaying = !this._videoEl.paused;
      this._activeChunk = chunk;
      this._showSpinner();
      this._videoEl.src = `/api/video/${chunk.id}`;
      this._videoEl.addEventListener('loadedmetadata', () => {
        this._videoEl.currentTime = offsetSecs;
        if (wasPlaying) this._videoEl.play().catch(() => {});
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

  // Returns { fromMs, toMs } spanning all chunks, or null if no footage
  get chunkExtent() {
    if (!this._chunks.length) return null;
    return { fromMs: this._chunks[0].start_ts, toMs: this._chunks[this._chunks.length - 1].end_ts };
  }

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

  _showSpinner(force = false) {
    if (this._spinnerTimer) clearTimeout(this._spinnerTimer);
    const show = () => {
      this._spinnerTimer = null;
      this._spinnerEl.style.display = '';
      this._msgEl.textContent = '';
      this._overlayEl.classList.remove('hidden');
    };
    if (force) show();
    else this._spinnerTimer = setTimeout(show, 300);
  }

  _hideOverlay() {
    if (this._spinnerTimer) { clearTimeout(this._spinnerTimer); this._spinnerTimer = null; }
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
    el.addEventListener('dblclick', () => el.classList.toggle('maximized'));
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
    const checkboxes = [...document.querySelectorAll('#camera-list input[type="checkbox"]')];
    checkboxes.forEach(cb => {
      const mid = parseInt(cb.dataset.monitorId, 10);
      if (!this._cells.has(mid)) cb.disabled = atCap;
    });
    const allChecked = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
    const btn = document.getElementById('btn-select-all');
    if (btn) btn.textContent = allChecked ? 'Deseleccionar todas' : 'Seleccionar todas';
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

  // Union of all chunk extents across all active cameras
  get footageRange() {
    let fromMs = Infinity, toMs = -Infinity;
    for (const { cell } of this._cells.values()) {
      const ext = cell.chunkExtent;
      if (!ext) continue;
      if (ext.fromMs < fromMs) fromMs = ext.fromMs;
      if (ext.toMs   > toMs)   toMs   = ext.toMs;
    }
    return fromMs === Infinity ? null : { fromMs, toMs };
  }

  get size() { return this._cells.size; }
}

// ── Scrubber ──────────────────────────────────────────────────────────────────

class Scrubber {
  constructor() {
    this._el        = document.getElementById('scrubber');
    this._hStart    = document.getElementById('h-start');
    this._hEnd      = document.getElementById('h-end');
    this._rangeEl   = document.getElementById('scrubber-range');
    this._leftEl    = document.getElementById('scrubber-left');
    this._rightEl   = document.getElementById('scrubber-right');
    this._lblStart  = document.getElementById('lbl-range-start');
    this._lblEnd    = document.getElementById('lbl-range-end');
    this._tooltip   = document.getElementById('scrubber-tooltip');
    this._miniView  = document.getElementById('minimap-view');
    this._miniS     = document.getElementById('minimap-start');
    this._miniE     = document.getElementById('minimap-end');
    this._zoomLbl   = document.getElementById('scrubber-zoom-label');
    this._hPlay     = document.getElementById('h-play');

    // Handle positions and view window — all in [0,1] relative to full period
    this._startPct  = 0;
    this._endPct    = 1;
    this._playPct   = null;
    this._viewStart = 0;
    this._viewEnd   = 1;

    this._periodFromMs = null;
    this._periodToMs   = null;

    this._dragging  = null;
    this._panning   = false;
    this._panLastX  = null;
    this._panned    = false;

    this.onChange = null; // (startPct, endPct, seekMs) => {}
    this.onSeek   = null; // (ms) => {} — fired when playhead is dragged

    // Handle drag
    this._hStart.addEventListener('mousedown', e => { this._dragging = 'start'; e.preventDefault(); e.stopPropagation(); });
    this._hEnd.addEventListener('mousedown',   e => { this._dragging = 'end';   e.preventDefault(); e.stopPropagation(); });
    this._hPlay.addEventListener('mousedown',  e => { this._dragging = 'play';  e.preventDefault(); e.stopPropagation(); });

    // Pan (drag on bar background)
    this._el.addEventListener('mousedown', e => {
      if (e.target === this._hStart || e.target === this._hEnd || e.target === this._hPlay) return;
      this._panning = true;
      this._panLastX = e.clientX;
      e.preventDefault();
    });

    document.addEventListener('mousemove', e => this._onMove(e));
    document.addEventListener('mouseup', () => {
      this._dragging = null;
      this._panning  = false;
      this._panLastX = null;
      this._el.style.cursor = '';
    });

    // Zoom with mouse wheel
    this._el.addEventListener('wheel', e => this._onWheel(e), { passive: false });

    // Tooltip on hover
    this._el.addEventListener('mousemove', e => this._showTooltip(e));
    this._el.addEventListener('mouseleave', () => { this._tooltip.style.display = 'none'; });

    // Click anywhere on bar → move playhead + seek
    this._el.addEventListener('click', e => {
      if (!this._periodFromMs || this._panned) { this._panned = false; return; }
      const rect = this._el.getBoundingClientRect();
      const vpct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const full = this._v2p(vpct);
      const ms = this._periodFromMs + full * (this._periodToMs - this._periodFromMs);
      this._playPct = full;
      this._updateDOM();
      if (this.onSeek) this.onSeek(ms);
    });
  }

  // period-space → view-space (0–1 of visible bar)
  _p2v(p) {
    const sz = this._viewEnd - this._viewStart;
    return sz === 0 ? 0 : (p - this._viewStart) / sz;
  }

  // view-space → period-space
  _v2p(v) {
    return this._viewStart + v * (this._viewEnd - this._viewStart);
  }

  _onWheel(e) {
    e.preventDefault();
    if (!this._periodFromMs) return;
    const rect   = this._el.getBoundingClientRect();
    const vpct   = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const pivot  = this._v2p(vpct);
    const factor = e.deltaY > 0 ? 1.4 : 1 / 1.4;
    const curSz  = this._viewEnd - this._viewStart;
    const minSz  = Math.max(1e-5, 5000 / (this._periodToMs - this._periodFromMs)); // min 5 s
    const newSz  = Math.min(1, Math.max(minSz, curSz * factor));

    let ns = pivot - vpct * newSz;
    let ne = pivot + (1 - vpct) * newSz;
    if (ns < 0) { ne -= ns; ns = 0; }
    if (ne > 1) { ns -= (ne - 1); ne = 1; }
    this._viewStart = Math.max(0, ns);
    this._viewEnd   = Math.min(1, ne);
    this._updateDOM();
  }

  _onMove(e) {
    if (this._panning && this._panLastX !== null) {
      if (!this._periodFromMs) return;
      const rect    = this._el.getBoundingClientRect();
      const dx      = e.clientX - this._panLastX;
      const viewSz  = this._viewEnd - this._viewStart;
      const delta   = -(dx / rect.width) * viewSz;
      let ns = this._viewStart + delta;
      let ne = this._viewEnd   + delta;
      if (ns < 0) { ne -= ns; ns = 0; }
      if (ne > 1) { ns -= (ne - 1); ne = 1; }
      this._viewStart = Math.max(0, ns);
      this._viewEnd   = Math.min(1, ne);
      this._panLastX  = e.clientX;
      this._panned    = true;
      this._el.style.cursor = 'grabbing';
      this._updateDOM();
      return;
    }

    if (!this._dragging || !this._periodFromMs) return;
    const rect     = this._el.getBoundingClientRect();
    const vpct     = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const full     = Math.max(0, Math.min(1, this._v2p(vpct)));
    const periodMs = this._periodToMs - this._periodFromMs;

    if (this._dragging === 'play') {
      this._playPct = full;
      this._updateDOM();
      const ms = this._periodFromMs + full * periodMs;
      if (this.onSeek) this.onSeek(ms);
      return;
    }

    const minGap   = Math.max(1e-6, 1000 / periodMs); // min 1 s between handles

    if (this._dragging === 'start') {
      this._startPct = Math.max(0, Math.min(full, this._endPct - minGap));
    } else {
      this._endPct   = Math.min(1, Math.max(full, this._startPct + minGap));
    }
    this._updateDOM();
    const seekMs = this._periodFromMs + this._startPct * periodMs;
    if (this.onChange) this.onChange(this._startPct, this._endPct, seekMs, this._dragging);
  }

  _showTooltip(e) {
    if (!this._periodFromMs) return;
    const rect  = this._el.getBoundingClientRect();
    const vpct  = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const ms    = this._periodFromMs + this._v2p(vpct) * (this._periodToMs - this._periodFromMs);
    this._tooltip.textContent = fmtTime(ms);
    this._tooltip.style.display = 'block';
    this._tooltip.style.left = `${e.clientX}px`;
    this._tooltip.style.top  = `${e.clientY - 34}px`;
  }

  _updateDOM() {
    const sv = this._p2v(this._startPct);
    const ev = this._p2v(this._endPct);
    const svc = Math.max(0, Math.min(1, sv));
    const evc = Math.max(0, Math.min(1, ev));

    // Handle positions (clamped to visible bar)
    this._hStart.style.left       = `${svc * 100}%`;
    this._hEnd.style.left         = `${evc * 100}%`;
    this._hStart.style.visibility = sv >= 0 && sv <= 1 ? '' : 'hidden';
    this._hEnd.style.visibility   = ev >= 0 && ev <= 1 ? '' : 'hidden';

    // Dark outside zones
    this._leftEl.style.width  = `${svc * 100}%`;
    this._rightEl.style.width = `${(1 - evc) * 100}%`;

    // Blue range zone
    const rLeft  = Math.max(0, sv);
    const rRight = Math.min(1, ev);
    this._rangeEl.style.left  = `${rLeft * 100}%`;
    this._rangeEl.style.width = `${Math.max(0, rRight - rLeft) * 100}%`;

    // Labels
    if (this._periodFromMs) {
      this._lblStart.textContent = fmtTime(this.startMs);
      this._lblEnd.textContent   = fmtTime(this.endMs);
    }

    // Mini-map: view window + handle markers
    const vs = this._viewEnd - this._viewStart;
    if (this._miniView) {
      this._miniView.style.left  = `${this._viewStart * 100}%`;
      this._miniView.style.width = `${vs * 100}%`;
    }
    if (this._miniS) this._miniS.style.left = `${this._startPct * 100}%`;
    if (this._miniE) this._miniE.style.left = `${this._endPct * 100}%`;

    // Zoom label
    if (this._zoomLbl) {
      this._zoomLbl.textContent = vs < 0.99 ? `${(Math.round(10 / vs) / 10)}×` : '';
    }

    // Playhead marker
    if (this._hPlay) {
      if (this._playPct !== null) {
        const pv = this._p2v(this._playPct);
        this._hPlay.style.display    = 'block';
        this._hPlay.style.left       = `${Math.max(0, Math.min(1, pv)) * 100}%`;
        this._hPlay.style.visibility = pv >= 0 && pv <= 1 ? 'visible' : 'hidden';
      } else {
        this._hPlay.style.display = 'none';
      }
    }

    // Cursor hint: grab when zoomed in
    if (!this._panning) {
      this._el.style.cursor = vs < 0.99 ? 'grab' : '';
    }
  }

  setPlayhead(ms) {
    if (!this._periodFromMs) return;
    const total = this._periodToMs - this._periodFromMs;
    this._playPct = Math.max(0, Math.min(1, (ms - this._periodFromMs) / total));
    this._updateDOM();
  }

  reset(periodFromMs, periodToMs) {
    this._periodFromMs = periodFromMs;
    this._periodToMs   = periodToMs;
    this._startPct     = 0;
    this._endPct       = 1;
    this._playPct      = 0;
    this._viewStart    = 0;
    this._viewEnd      = 1;
    this._updateDOM();
  }

  get startMs() {
    if (!this._periodFromMs) return 0;
    return this._periodFromMs + this._startPct * (this._periodToMs - this._periodFromMs);
  }

  get endMs() {
    if (!this._periodToMs) return 0;
    return this._periodFromMs + this._endPct * (this._periodToMs - this._periodFromMs);
  }

  setRange(startPct, endPct) {
    this._startPct = Math.max(0, Math.min(1, startPct));
    this._endPct   = Math.min(1, Math.max(this._startPct + 1e-6, endPct));
    this._playPct  = this._startPct;
    this._updateDOM();
  }

  get playheadMs() {
    if (!this._periodFromMs || this._playPct === null) return null;
    return this._periodFromMs + this._playPct * (this._periodToMs - this._periodFromMs);
  }

  getRangeMs() { return { startMs: this.startMs, endMs: this.endMs }; }
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
        body: JSON.stringify({ monitor_ids: monitorIds, from_ts: Math.round(fromMs), to_ts: Math.round(toMs) }),
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
      const msg = typeof d.detail === 'string'
        ? d.detail
        : Array.isArray(d.detail)
          ? d.detail.map(e => e.msg || JSON.stringify(e)).join('; ')
          : `Error ${res.status}`;
      this._showError(msg);
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

    const virtualNow = master.currentVirtualTimeMs;

    // Master ran out of footage ahead (e.g. past the last recorded chunk) — stop.
    if (virtualNow === null) {
      gridPlayer.pauseAll();
      _isPlaying = false;
      updatePlayPauseButton(false);
      return;
    }

    // Stop at scrubber end
    if (virtualNow >= scrubber.endMs) {
      gridPlayer.pauseAll();
      _isPlaying = false;
      updatePlayPauseButton(false);
      return;
    }

    // Advance playhead
    scrubber.setPlayhead(virtualNow);

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
let _playbackSpeed = 1;
let _isPlaying = false;

// Default date = today (local timezone, not UTC)
const _today = new Date();
document.getElementById('date-picker').value =
  `${_today.getFullYear()}-${String(_today.getMonth() + 1).padStart(2, '0')}-${String(_today.getDate()).padStart(2, '0')}`;

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

  // Auto-position handles to actual footage extent across all cameras
  const footage = gridPlayer.footageRange;
  if (footage) {
    const total = _periodToMs - _periodFromMs;
    scrubber.setRange(
      Math.max(0, (footage.fromMs - _periodFromMs) / total),
      Math.min(1, (footage.toMs   - _periodFromMs) / total)
    );
  }

  gridPlayer.seekAll(scrubber.startMs);

  const transportBtns = ['btn-play-pause','btn-to-start','btn-back-30','btn-fwd-30','btn-to-end'];
  transportBtns.forEach(id => { document.getElementById(id).disabled = false; });
  updateExportButton();
});

// Scrubber change callback — don't seek during playback to avoid spinner flicker
scrubber.onChange = (startPct, endPct, seekMs, handle) => {
  if (!_isPlaying && handle !== 'end') gridPlayer.seekAll(seekMs);
};

// Playhead drag/click → seek all cells (works during playback too)
scrubber.onSeek = ms => {
  gridPlayer.seekAll(ms);
  if (_isPlaying) setTimeout(() => startSyncLoop(gridPlayer, scrubber), 150);
};

// ESC restores any maximized cell
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.cell.maximized').forEach(el => el.classList.remove('maximized'));
  }
});

// Play / Pause
document.getElementById('btn-play-pause').addEventListener('click', () => {
  if (!_periodFromMs) return;
  _isPlaying = !_isPlaying;
  if (_isPlaying) {
    // Resume from playhead position if set, otherwise from range start
    const resumeMs = scrubber.playheadMs ?? scrubber.startMs;
    gridPlayer.seekAll(resumeMs);
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

// Transport helpers
function _seekTo(ms) {
  scrubber.setPlayhead(ms);
  gridPlayer.seekAll(ms);
  if (_isPlaying) setTimeout(() => startSyncLoop(gridPlayer, scrubber), 150);
}

document.getElementById('btn-to-start').addEventListener('click', () => {
  if (!_periodFromMs) return;
  _seekTo(scrubber.startMs);
});

document.getElementById('btn-to-end').addEventListener('click', () => {
  if (!_periodFromMs) return;
  _seekTo(scrubber.endMs);
});

document.getElementById('btn-back-30').addEventListener('click', () => {
  if (!_periodFromMs) return;
  const ms = Math.max(scrubber.startMs, (scrubber.playheadMs ?? scrubber.startMs) - 30_000);
  _seekTo(ms);
});

document.getElementById('btn-fwd-30').addEventListener('click', () => {
  if (!_periodFromMs) return;
  const ms = Math.min(scrubber.endMs, (scrubber.playheadMs ?? scrubber.startMs) + 30_000);
  _seekTo(ms);
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

// Select-all toggle
document.getElementById('btn-select-all').addEventListener('click', () => {
  const checkboxes = [...document.querySelectorAll('#camera-list input[type="checkbox"]:not(:disabled)')];
  const allChecked = checkboxes.every(cb => cb.checked);
  checkboxes.forEach(cb => {
    if (cb.checked === allChecked) {
      cb.checked = !allChecked;
      cb.dispatchEvent(new Event('change'));
    }
  });
});

// Bootstrap
loadCameras();
pollIndexerStatus();
setInterval(pollIndexerStatus, 30000);
