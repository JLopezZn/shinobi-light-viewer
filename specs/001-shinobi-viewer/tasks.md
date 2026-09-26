# Tasks: Shinobi Light Viewer

**Input**: Design documents from `specs/001-shinobi-viewer/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/api.md ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks in same phase)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Verify directory structure, dependencies, and configuration baseline.

- [x] T001 Verify/create project directories: `backend/app/api/`, `backend/app/services/`, `backend/tests/unit/`, `backend/tests/integration/`, `frontend/`
- [x] T002 Verify `backend/requirements.txt` contains: `fastapi`, `uvicorn[standard]`, `python-multipart`, `httpx`, `pytest`, `pytest-asyncio`
- [x] T003 Verify `backend/.env.example` documents all required settings: `FOOTAGE_DIR`, `DB_PATH`, `CACHE_DIR`, `PORT` (default 8090), `SCAN_INTERVAL_SECONDS` (default 60); use Windows-appropriate example paths (`D:/ShinobiVideos`, `C:/ProgramData/shinobi-viewer/...`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core backend infrastructure all user stories depend on. No user story work begins until this phase is complete.

**⚠️ CRITICAL**: Complete sequentially — each task feeds the next.

- [x] T004 [P] Implement `backend/app/config.py` — `Settings` using `pydantic-settings` or `python-dotenv`: `FOOTAGE_DIR: Path`, `DB_PATH: Path`, `CACHE_DIR: Path`, `PORT: int = 8090`, `SCAN_INTERVAL_SECONDS: int = 60`; expose singleton `settings = Settings()`
- [x] T005 [P] Implement `backend/app/database.py` — `init_db()` creates SQLite DB at `settings.DB_PATH` using exact DDL from data-model.md (`monitors` + `video_chunks` tables + `idx_chunks_monitor_time` index); `get_conn()` context manager returning a `sqlite3.Connection` with `row_factory = sqlite3.Row`
- [x] T006 [P] Implement `backend/app/models.py` — Pydantic v2 models using `Optional[X]` (not `X | None`) for Python 3.9 compat: `MonitorOut` (id, group_key, monitor_id, display_name, first_seen_at, last_seen_at); `VideoChunkOut` (id, monitor_id, file_path, start_ts, end_ts, duration_ms, file_size_bytes, availability); `CameraExportStatus` (monitor_id, display_name, download_token: `Optional[str] = None`); `JobStatusOut` (status: str, type: `Optional[str] = None`, progress: float = 0.0, cameras: `List[CameraExportStatus] = []`, error: `Optional[str] = None`); `ExportJobRequest` (monitor_ids: `List[int]`, from_ts: int, to_ts: int)
- [x] T007 Implement `backend/app/indexer.py` — Background scan loop: startup scan + repeat every `SCAN_INTERVAL_SECONDS`; recursive walk of `settings.FOOTAGE_DIR`; parse path with regex `(?P<group_key>[^/]+)/(?P<monitor_id>[^/]+)/(?:\d{4}-\d{2}-\d{2}/)?(?P<filename>[^/]+\.mp4)$`; skip files with `mtime > time.time() - 60` (mtime guard FR-002); upsert `monitors` (INSERT OR IGNORE + UPDATE last_seen_at); insert `video_chunks` (INSERT OR IGNORE); after each scan mark chunks not confirmed as `availability='unavailable'`; expose `get_indexer_status()` returning last_scan_at, next_scan_in_seconds, total_monitors, total_chunks, unavailable_chunks; depends on T005
- [x] T008 [P] Implement `backend/app/api/monitors.py` — `GET /api/monitors` returns `List[MonitorOut]` from DB; `GET /api/indexer/status` returns indexer status dict; depends on T005, T006, T007
- [x] T009 [P] Implement `backend/app/api/chunks.py` — `GET /api/monitors/{monitor_id}/chunks?from_ts={ms}&to_ts={ms}` queries chunks overlapping `[from_ts, to_ts]` ordered by `start_ts`; returns `List[VideoChunkOut]`; 404 if monitor not found; depends on T005, T006, T007
- [x] T010 Implement `backend/app/main.py` — FastAPI app factory; call `init_db()` and start indexer loop on startup; register routers for monitors, chunks, video, jobs; mount `frontend/` as `StaticFiles` at `/` with `html=True`; depends on T004–T009

**Checkpoint**: `uvicorn app.main:app --port 8090` starts, `/api/monitors` returns `[]`, `/api/indexer/status` shows `last_scan_at`

---

## Phase 3: User Story 1 — Grid Camera Player (Priority: P1) 🎯 MVP

**Goal**: Operator selects cameras, picks a date+time period, and sees up to 9 synchronized timelapse cells.

**Independent Test**: Point indexer at a directory with ≥2 cameras' `.mp4` files, activate both, confirm 2 cells appear and play synchronized timelapse at 8× speed (quickstart.md Scenario 3).

### Implementation for User Story 1

- [x] T011 [P] [US1] Implement `backend/app/api/video.py` — `GET /api/video/{chunk_id}`: resolve file path from DB; return 404 if chunk not found; return 410 if `availability='unavailable'`; read `Range` header; if present parse `start`/`end` bytes, seek file, stream with `StreamingResponse`, status 206, headers: `Accept-Ranges: bytes`, `Content-Range: bytes {s}-{e}/{size}`, `Content-Length: {e-s+1}`; if no Range header stream full file with status 200; always include `Accept-Ranges: bytes`
- [x] T012 [P] [US1] Implement `frontend/index.html` — two-panel layout: left sidebar (camera toggle list with checkboxes, date picker + from/to time inputs, "Confirmar período" button, speed selector 1×/4×/8×/16×) + main area (video grid `#grid-container` + scrubber bar `#scrubber` with two handles `#h-start`/`#h-end` + export controls `#export-btn`, `#export-progress`, `#download-links`); link `style.css` and `app.js`
- [x] T013 [P] [US1] Implement `frontend/style.css` — CSS Grid for `#grid-container` using `grid-template-columns: repeat(auto-fit, minmax(300px, 1fr))` adjusting to 1–9 cells; `.cell` with relative positioning; `.cell-overlay` (dark bg, centered spinner animation + camera name) shown while buffering; `.scrubber` bar with `.handle` absolutely positioned via `left: X%`; `.scrubber-range` blue highlight zone; `.scrubber-outside` dark overlay zones; sidebar layout; active speed button style; disabled state styles for controls locked during export
- [x] T014 [P] [US1] Implement `CellPlayer` class in `frontend/app.js` — constructor(monitorId, displayName, videoEl, overlayEl); `loadChunks(chunks)` stores sorted chunk array; `seekTo(virtualTimeMs)` finds chunk via `chunks.find(c => ms >= c.start_ts && ms < c.end_ts)`, sets `videoEl.src = '/api/video/' + chunk.id`, waits `loadedmetadata` then sets `videoEl.currentTime = (ms - chunk.start_ts) / 1000`; `play()`/`pause()`; on `ended` event auto-advance to next chunk; show overlay on `waiting`/`stalled`, hide on `playing`; expose `currentTime` getter; if chunks empty show "Sin footage" overlay
- [x] T015 [US1] Implement `GridPlayer` class in `frontend/app.js` — manages `Map<monitorId, CellPlayer>`; `activate(monitorId, displayName)` adds cell (max 9, disable all inactive toggles at cap per FR-008); `deactivate(monitorId)` removes cell, re-enables toggles if count drops below 9; `recalcLayout()` updates `#grid-container` grid-template-columns based on N cells (1→1col, 2→2col, 3→3col, 4→2col, 5-6→3col, 7-9→3col); `loadPeriod(fromMs, toMs)` fetches `/api/monitors/{id}/chunks?from_ts&to_ts` for each active camera, calls `cell.loadChunks()`; `seekAll(virtualTimeMs)` calls `seekTo` on all cells; `playAll()`/`pauseAll()`; exposes `activeCells` array; depends on T014
- [x] T016 [US1] Implement multi-video sync loop in `frontend/app.js` — `syncLoop()` using `requestAnimationFrame`: MASTER = first active cell's `videoEl`; TOLERANCE = 0.05 s; for each follower: if `Math.abs(follower.currentTime - MASTER.currentTime) > TOLERANCE` set `follower.currentTime = MASTER.currentTime`; loop continues only while `!MASTER.paused`; `play()` sets all `cell.videoEl.currentTime = MASTER.currentTime` then calls `.play()` then starts `syncLoop()`; depends on T015
- [x] T017 [P] [US1] Implement speed selector in `frontend/app.js` — 4 buttons for 1×/4×/8×/16×; default active = 8×; on click set `videoEl.playbackRate` on all active cells and update button active state; integrate with GridPlayer; depends on T015
- [x] T018 [US1] Implement period selector in `frontend/app.js` — read date picker + from/to time inputs; on "Confirmar período" click parse inputs to Unix ms `fromMs`/`toMs`; call `GridPlayer.loadPeriod(fromMs, toMs)`; initialize scrubber bar to cover full period (`Scrubber.reset(fromMs, toMs)`); depends on T015

**Checkpoint**: Camera list loads in sidebar, activating cameras builds correct grid layout, timelapse plays synchronized at 8×, spinner shows while buffering, period selector loads chunks.

---

## Phase 4: User Story 2 — Dual-Handle Scrubber (Priority: P2)

**Goal**: Operator drags two handles to delimit the export range; grid seeks to handle position on drag.

**Independent Test**: With grid active, drag start handle to 25%, drag end handle to 75%, verify highlighted zone updates and grid seeks to start-handle timestamp (quickstart.md Scenario 8).

### Implementation for User Story 2

- [x] T019 [P] [US2] Implement `Scrubber` class in `frontend/app.js` — two `<div>` handles `#h-start` (left) and `#h-end` (right) positioned with `left: X%` over `.scrubber` bar; `mousedown` on handle sets `dragging`; `mousemove` on document computes `pct = (e.clientX - bar.left) / bar.width` clamped [0,1]; enforce constraint: start ≤ end - 0.01 (never cross); update `handle.style.left`; call `onChange(startPct, endPct)`; `mouseup` clears `dragging`; `getRangeMs(periodStartMs, periodEndMs)` returns `{startMs, endMs}`; `reset()` sets start=0%, end=100%
- [x] T020 [US2] Wire scrubber → grid seek in `frontend/app.js` — `onChange` callback: compute `virtualTimeMs = periodStartMs + startPct * (periodEndMs - periodStartMs)`; call `GridPlayer.seekAll(virtualTimeMs)`; call `updateZones(startPct, endPct)`; depends on T019, T015
- [x] T021 [US2] Implement scrubber visual zones in `frontend/app.js` — `updateZones(startPct, endPct)`: set left dark overlay width = `startPct * 100%`; set right dark overlay left = `endPct * 100%`, width = `(1 - endPct) * 100%`; set blue highlight zone left = `startPct * 100%`, width = `(endPct - startPct) * 100%`; add click listener on highlighted zone to seek grid to clicked virtual time; depends on T019
- [x] T022 [US2] Implement bounded playback in `frontend/app.js` — `play()` first calls `GridPlayer.seekAll(scrubber.getRangeMs().startMs)`; in `syncLoop()` check if MASTER virtual time (`periodStartMs + MASTER.currentTime * 1000` for active chunk) exceeds `scrubber.getRangeMs().endMs`; if so call `GridPlayer.pauseAll()`; depends on T019, T016

**Checkpoint**: Scrubber handles drag, never cross, zones darken/highlight correctly, grid seeks on drag, play stops at end handle.

---

## Phase 5: User Story 3 — Export Selected Range (Priority: P3)

**Goal**: With range selected, export produces one `.mp4` per active camera using lossless FFmpeg concat.

**Independent Test**: 2 active cameras, scrubber range = 10 min, click Export → 2 files generated, each ~10 min duration, download links labeled with camera name (quickstart.md Scenario 10).

### Implementation for User Story 3

- [x] T023 [P] [US3] Implement `backend/app/services/ffmpeg.py` — `concat_cmd(filelist: Path, output: Path) -> list[str]`: returns `["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(filelist), "-c", "copy", "-progress", "pipe:1", "-nostats", str(output)]`; `compute_export_size(chunks: list) -> int`: sum of `c['file_size_bytes']` across all chunks (byte estimate for disk space check)
- [x] T024 [US3] Implement `backend/app/services/job_manager.py` — `JobManager` singleton with `_state` dict; `start_export(monitor_ids, from_ts, to_ts, chunks_per_monitor: dict)` — raises `HTTPException(409)` if status != 'idle'; creates temp filelist files in `settings.CACHE_DIR`; launches N `asyncio` tasks via `asyncio.create_subprocess_exec(*concat_cmd(...), stdout=PIPE)`; reads FFmpeg `-progress pipe:1` stdout (parse `out_time_ms=` lines) to track per-camera progress; `progress = min(cam.progress for cam in cameras)`; on each camera process exit assign `download_token = str(uuid.uuid4())` and store `output_path`; on all done set status='done'; `cancel()` kills all procs, deletes partial outputs + filelists from CACHE_DIR, resets to idle; `consume_token(token) -> Optional[Path]` returns path if valid then removes token from state; depends on T023
- [x] T025 [US3] Implement `backend/app/api/jobs.py` — `POST /api/jobs/export`: parse `ExportJobRequest`; validate `monitor_ids` non-empty and `from_ts < to_ts`; query chunks per camera from DB (only `availability='available'`); 422 if no chunks for any camera; compute `compute_export_size(all_chunks)`; check `shutil.disk_usage(str(settings.CACHE_DIR)).free >= estimated_bytes` → 507 if not; call `job_manager.start_export(...)`; return 202; `GET /api/jobs/current`: return `JobStatusOut` serialized from `job_manager._state`; `DELETE /api/jobs/current`: 404 if idle, call `job_manager.cancel()`, return 200; `GET /api/downloads/{token}`: call `job_manager.consume_token(token)`; 404 if None; stream with `FileResponse(path, media_type='video/mp4', headers={'Content-Disposition': f'attachment; filename=...'})`; schedule file deletion after response; depends on T024, T006
- [x] T026 [US3] Implement `ExportManager` class in `frontend/app.js` — `export(monitorIds, fromMs, toMs)`: POST to `/api/jobs/export`; on 202 call `lock()` and start `setInterval(poll, 2000)`; `poll()` calls `GET /api/jobs/current` and updates `#export-progress` bar width; on status='done' stop polling, call `unlock()`, render download links; on error stop polling, call `unlock()`, show error message; `lock()` disables camera toggles, scrubber handles, Export button; `unlock()` re-enables all; depends on T025
- [x] T027 [US3] Implement export UI wiring in `frontend/app.js` — wire `#export-btn` click: collect active monitor IDs from `GridPlayer.activeCells` filtering out "Sin footage" cells; get `{startMs, endMs}` from `Scrubber.getRangeMs()`; call `ExportManager.export(monitorIds, startMs, endMs)`; disable `#export-btn` when `activeCells.length === 0`; on done render per-camera download links in `#download-links` as `<a href="/api/downloads/{token}" download>camera.display_name</a>`; depends on T026

**Checkpoint**: Export with 2 cameras produces 2 files, progress bar fills, download links appear, temp files deleted after download, 409 on concurrent export attempt.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final wiring, edge-case hardening, zero-HDD-write verification.

- [x] T028 Ensure `backend/app/api/video.py` router is registered in `backend/app/main.py` and verify `Accept-Ranges: bytes` header is present on both 200 and 206 responses via `curl -i http://localhost:8090/api/video/1`
- [x] T029 Harden "Sin footage" case in `frontend/app.js` — after `GridPlayer.loadPeriod()`, for each camera whose chunk array is empty: call `cell.showNoFootage()` (overlay with "Sin footage" text), mark cell as inactive in `activeCells` for sync loop and export; Export button must exclude these cells from `monitor_ids`
- [x] T030 Add 10-camera cap enforcement in `frontend/app.js` — in `GridPlayer.activate()` when `activeCells.size >= 9` set `disabled=true` on all inactive camera checkbox inputs; in `deactivate()` when count drops below 9 remove `disabled` from all camera checkboxes
- [x] T031 Verify `start.sh` and `start.bat` — `start.sh`: uses `. "$ENV_FILE"` (not `source <(...)`), activates `.venv/bin/activate`, runs `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`; `start.bat`: equivalent Windows batch, activates `.venv\Scripts\activate.bat`, sets vars from `.env`, runs uvicorn; test both end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 completion
- **US2 (Phase 4)**: Depends on Phase 3 completion (scrubber integrates with GridPlayer)
- **US3 (Phase 5)**: Depends on Phase 2 (backend) and Phase 4 (scrubber range for export)
- **Polish (Phase 6)**: Depends on all story phases

### Within Phase 2

- T004, T005, T006 can run in parallel (separate files)
- T007 requires T005
- T008, T009 can run in parallel (both require T007 + T006)
- T010 requires T008 + T009

### Within Phase 3

- T011, T012, T013, T014 can run in parallel (all different files)
- T015 requires T014
- T016 requires T015
- T017 can run in parallel with T016 (both require T015)
- T018 requires T015

### Within Phase 4

- T019 is independent
- T020, T021 require T019
- T022 requires T019 + T016

### Within Phase 5

- T023 is independent
- T024 requires T023
- T025 requires T024
- T026 requires T025
- T027 requires T026

---

## Parallel Example: User Story 1

```text
# Run these in parallel (different files):
T011: backend/app/api/video.py        (Range Request endpoint)
T012: frontend/index.html             (HTML layout)
T013: frontend/style.css              (grid + scrubber styles)
T014: frontend/app.js CellPlayer      (per-cell video logic)

# Then sequentially:
T015: GridPlayer (needs CellPlayer)
T016: sync loop  (needs GridPlayer)
T017: speed selector (can run with T016, both need GridPlayer)
T018: period selector (needs GridPlayer)
```

---

## Phase 7: Post-MVP Improvements

**Purpose**: UX fixes and quality-of-life enhancements applied after initial implementation.

- [x] T032 Fix date picker defaulting to UTC day instead of local day in `frontend/app.js` — replace `new Date().toISOString().split('T')[0]` with explicit `getFullYear()/getMonth()+1/getDate()` local-time formatting
- [x] T033 Add scrubber zoom/pan in `frontend/app.js` — `_viewStart`/`_viewEnd` window in period-space [0,1]; `_p2v()`/`_v2p()` converters; mouse wheel zoom (1.4× per tick, min window 5 s, zoom around cursor pivot); drag bar background to pan; zoom label shows current magnification (e.g. "4×"); mini-map bar shows full period with view window highlighted; grab cursor when zoomed in
- [x] T034 Add scrubber hover tooltip in `frontend/app.js` and `frontend/style.css` — `position:fixed` tooltip div shows formatted time at cursor; displayed on `mousemove`, hidden on `mouseleave`; correct position using `e.clientX / e.clientY - 34`
- [x] T035 Fix playback stop bug when scrubber handles are dragged during playback in `frontend/app.js` — `scrubber.onChange` must skip `gridPlayer.seekAll()` when `_isPlaying === true`; dragging during play adjusts the range boundary without interrupting video
- [x] T036 Add cell maximize on double-click in `frontend/app.js` and `frontend/style.css` — `dblclick` on any cell toggles `.maximized` CSS class (`position:fixed; inset:0; width:100vw; height:100vh; z-index:100`); pressing Escape removes `.maximized` from all cells
- [x] T037 Add spinner buffer in `frontend/app.js` — `_showSpinner()` delays overlay reveal by 300 ms via `setTimeout`; `_hideOverlay()` cancels the pending timer so brief buffering moments (< 300 ms) never flash the spinner; initial overlay on construction is immediate (`force=true`); listen for `canplay` in addition to `playing` to hide overlay earlier
- [x] T038 Document tooltip (FR-021) and playhead (FR-022) in `specs/001-shinobi-viewer/spec.md` — add Functional Requirements entries and acceptance scenarios for User Story 2
- [x] T039 Implement playhead marker in `frontend/app.js`, `frontend/index.html`, `frontend/style.css` — `#h-play` yellow (#ffd600) handle (3 px, z-index 3, circle cap via `::before`); Scrubber tracks `_playPct`; `setPlayhead(ms)` called every rAF frame from sync loop; dragging `h-play` fires `onSeek(ms)` which calls `gridPlayer.seekAll()` without stopping playback; playhead hidden before first `reset()`; fix `_isPlaying = false` when sync loop auto-stops at range end
- [x] T040 Fix click-seek + playhead bugs in `frontend/app.js` — click anywhere on bar fires `onSeek` and moves playhead; `CellPlayer.seekTo()` captures `wasPlaying` before src change and resumes `play()` in `loadedmetadata` callback; `onSeek` restarts sync loop after 150 ms when `_isPlaying`; `scrubber.playheadMs` getter exposes current playhead position; Play button resumes from `playheadMs` instead of always from `startMs`; playhead `display: 'block'` instead of `''` to override CSS default
- [x] T042 Add transport controls (FR-023) in `frontend/index.html`, `frontend/style.css`, `frontend/app.js` — buttons ⏮ ⏪30s ▶/⏸ 30s⏩ ⏭; helper `_seekTo(ms)` moves playhead + seeks all cells + restarts sync loop if playing; ⏪/⏩ clamp to range bounds; all buttons enabled on period confirm
- [x] T041 Auto-position scrubber handles to actual footage extent (FR-024) in `frontend/app.js` — after `loadPeriod`, compute union of all `chunkExtent` across cameras via `GridPlayer.footageRange`; call `scrubber.setRange(startPct, endPct)` to clamp handles to real footage bounds; operator sees blue zone matching available footage even if selected period is wider — click anywhere on bar fires `onSeek` and moves playhead; `CellPlayer.seekTo()` captures `wasPlaying` before src change and resumes `play()` in `loadedmetadata` callback; `onSeek` restarts sync loop after 150 ms when `_isPlaying`; `scrubber.playheadMs` getter exposes current playhead position; Play button resumes from `playheadMs` instead of always from `startMs`; playhead `display: 'block'` instead of `''` to override CSS default
- [x] T043 Add select-all / deselect-all camera button (FR-025) in `frontend/index.html` and `frontend/app.js` — button above camera list toggles all non-disabled checkboxes; dispatches `change` event on each so existing activate/deactivate logic fires; label switches to "Deseleccionar todas" when all cameras are active, updated via `GridPlayer._updateToggles()`
- [x] T044 Add per-camera coverage lanes on scrubber (FR-026) in `frontend/index.html`, `frontend/style.css`, `frontend/app.js` — `#coverage-lanes` div below scrubber bar; `Scrubber.setCoverageData(cameras)` + `_renderCoverage()` render one thin lane per camera with colored segments mapped from chunk `start_ts`/`end_ts`; lanes respect zoom/pan via `_p2v()`; colored `cam-dot` span added to sidebar camera list items for color correlation; colorblind-safe palette (blues, orange, purple, yellow); lanes update on period confirm and camera toggle
- [x] T045 Fix memory leaks in CellPlayer (FR-N/A) in `frontend/app.js` — `AbortController` (`_ac`) for persistent video event listeners removed all at once in `destroy()`; `_seekAc` aborted on every chunk change so stale `loadedmetadata` callbacks never fire on wrong chunk; `destroy()` clears spinner timer, aborts both controllers, releases media via `src=''` + `load()`; `GridPlayer.deactivate()` calls `cell.destroy()` instead of just `pause()`
- [x] T046 Add audio toggle on maximized cell (FR-027) in `frontend/style.css` and `frontend/app.js` — `CellPlayer` creates `.audio-btn` (hidden by default); `showAudioControl(visible)` shows/hides it and resets mute on hide; `GridPlayer.activate()` dblclick handler calls `showAudioControl(isMax)`; ESC key handler also calls `showAudioControl(false)` on all cells
- [x] T047 Fix stuck export state (FR-028) in `frontend/app.js` — `ExportManager.resume()` checks `/api/jobs/current` and attaches UI (progress bar + cancel) to any running job; called on page load and when server returns 409; eliminates dead-end "ya hay una exportación" error with no cancel option
- [x] T048 Fix playback state lost on seek across chunk boundary (FR-030) in `frontend/app.js` — add `shouldPlay` param to `CellPlayer.seekTo()` and `GridPlayer.seekAll()`; caller passes `_isPlaying` so wasPlaying is always correct even when src is already paused from a prior rapid seek; also stop sync loop immediately in `onSeek` and `_seekTo` (before seekAll) so stale loop frame can't falsely detect end-of-range and call pauseAll(); debounce sync loop restart with `_seekRestartTimer` so rapid drag events don't pile up setTimeout calls
- [x] T049 Add horizontal scroll pan on scrubber (FR-029) in `frontend/app.js` and `frontend/index.html` — in `Scrubber._onWheel()` detect `Math.abs(deltaX) > Math.abs(deltaY)` (trackpad horizontal swipe) or `e.shiftKey` (Shift+wheel) and pan the view window; normalize delta for pixel vs line deltaMode; vertical wheel without Shift continues to zoom; update hint text to mention Shift+rueda and deslizar horizontal
- [x] T050 Add "Limpiar DB" button (FR-031) in `frontend/index.html`, `frontend/style.css`, `frontend/app.js`, and `backend/app/api/admin.py` — new `DELETE /api/db` endpoint deletes all rows from `video_chunks` and `monitors` tables, returns HTTP 409 if a job is running; sidebar button shows browser `confirm()` dialog before calling the endpoint; on success reloads the page; on error (including 409) shows `alert()` with the server message without reloading; button styled with muted red to signal destructive action; register `admin.router` in `backend/app/main.py`

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational) — 7 tasks
3. Complete Phase 3 (US1) — 8 tasks
4. **STOP and VALIDATE**: Open browser, confirm camera list loads, grid assembles, timelapse plays synchronized at 8×

### Incremental Delivery

1. Phase 1 + 2 → Backend up, API responding
2. + Phase 3 (US1) → Grid plays **(MVP!)**
3. + Phase 4 (US2) → Scrubber fully functional
4. + Phase 5 (US3) → Export complete
5. + Phase 6 → Production-ready

---

## Notes

- All `Optional[X]` annotations must use `from typing import Optional` — Python 3.9 + Pydantic v2 does not support `X | None` syntax even with `from __future__ import annotations`
- `GET /api/video/{chunk_id}` MUST always include `Accept-Ranges: bytes` (even on 200) — browsers require it to enable seeking
- FFmpeg progress: parse `out_time_ms=` lines from `-progress pipe:1` stdout to compute per-camera progress fraction
- Zero HDD writes: `settings.FOOTAGE_DIR` paths are **read-only** — never pass them as FFmpeg output; all output goes to `settings.CACHE_DIR`
- Grid column logic: 1→1col, 2→2col, 3→3col, 4→2col (2×2), 5→3col, 6→3col (2×3), 7-9→3col (3×3)
- sync loop MUST only run via `requestAnimationFrame` — never `setInterval` — to avoid drift accumulation
