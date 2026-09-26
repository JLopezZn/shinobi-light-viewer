# Tasks: Shinobi Light Viewer

**Input**: Design documents from `specs/001-shinobi-viewer/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All paths are relative to repository root

## Path Conventions

```text
backend/app/          Python backend source
backend/tests/        Test suite (not in scope for this task set)
frontend/             Static HTML/JS/CSS frontend
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the project skeleton before any feature code is written.

- [x] T001 Create directory structure: `backend/app/`, `backend/app/api/`, `backend/app/services/`, `backend/tests/unit/`, `backend/tests/integration/`, `backend/tests/contract/`, `frontend/`
- [x] T002 Create `backend/requirements.txt` with pinned dependencies: `fastapi`, `uvicorn[standard]`, `python-multipart`, `aiofiles`
- [x] T003 [P] Create `backend/.env.example` with variables: `FOOTAGE_DIR`, `DB_PATH`, `CACHE_DIR`, `PORT=8080`, `SCAN_INTERVAL_SECONDS=60`
- [x] T004 [P] Create empty placeholder files: `frontend/index.html`, `frontend/app.js`, `frontend/style.css`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 Implement `backend/app/config.py` — `Settings` dataclass reading from env: `FOOTAGE_DIR: Path`, `DB_PATH: Path`, `CACHE_DIR: Path`, `PORT: int = 8080`, `SCAN_INTERVAL_SECONDS: int = 60`; raise `ValueError` on startup if `FOOTAGE_DIR` does not exist
- [x] T006 Implement `backend/app/database.py` — `init_db(db_path: Path)` that creates the SQLite file and runs the DDL from data-model.md: `monitors` table with `UNIQUE(group_key, monitor_id)`, `video_chunks` table with `UNIQUE(file_path)`, and `idx_chunks_monitor_time` index on `(monitor_id, start_ts, end_ts)`; expose a `get_conn()` context manager returning a `sqlite3.Connection`
- [x] T007 [P] Implement `backend/app/models.py` — Pydantic v2 response models matching contracts/api.md exactly: `MonitorOut` (id, group_key, monitor_id, display_name, first_seen_at, last_seen_at), `VideoChunkOut` (id, monitor_id, file_path, start_ts, end_ts, duration_ms, file_size_bytes, availability), `JobStatusOut` (status, type, progress, download_token, error), `IndexerStatusOut` (last_scan_at, next_scan_in_seconds, total_monitors, total_chunks, unavailable_chunks); and request models `ExportRequest` (monitor_id: int, from_ts: int, to_ts: int), `TimelapseRequest` (same fields)
- [x] T008 [P] Implement `backend/app/services/ffmpeg.py` — four functions: (1) `probe_duration_ms(file_path: str) -> int` using `ffprobe -v quiet -print_format json -show_streams`; (2) `build_filelist(paths: list[str], dest: Path) -> Path` writing an ffmpeg concat filelist.txt to `dest`; (3) `concat_cmd(filelist: Path, output: Path) -> list[str]` returning `["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(filelist), "-c", "copy", "-progress", "pipe:1", "-nostats", str(output)]`; (4) `timelapse_cmd(filelist: Path, output: Path, speed: float) -> list[str]` returning command with `-vf setpts={1/speed}*PTS -r 30 -an -progress pipe:1 -nostats`
- [x] T009 Implement `backend/app/services/job_manager.py` — module-level `job_state: dict` with fields matching the in-memory JobState entity in data-model.md (status, type, progress, proc, output_path, error, download_token); `tokens: dict[str, Path]`; functions: `is_idle() -> bool`, `start_job(type, output_path, proc)`, `update_progress(pct: float)`, `complete_job() -> str` (issues token via `secrets.token_urlsafe(32)`, stores in tokens, returns token), `fail_job(error: str)`, `cancel_job()` (kills proc, unlinks partial output_path, resets state), `consume_token(token: str) -> Path | None` (pops from tokens dict)
- [x] T010 Implement `backend/app/main.py` — FastAPI app factory: create app, call `init_db()` on startup, mount `frontend/` as `StaticFiles` at `/` with `html=True`, include routers (stubs for now), start indexer background loop on startup via `asyncio.create_task`
- [x] T011 Implement `backend/app/indexer.py` — `scan_once(footage_dir: Path, db_path: Path)`: (1) walk `footage_dir` recursively for `.mp4` files matching pattern `GroupKey/MonitorID/YYYY-MM-DD/filename.mp4`; (2) skip any file where `Path.stat().st_mtime > time.time() - 60` (FR-002); (3) upsert monitor row (`INSERT OR IGNORE INTO monitors`); (4) derive `start_ts` and `end_ts` from filename or ffprobe; (5) `INSERT OR IGNORE INTO video_chunks`; (6) mark removed chunks: for each `available` chunk in DB whose `file_path` no longer exists on disk, `UPDATE video_chunks SET availability='unavailable'`; (7) mark re-appeared chunks: `UPDATE video_chunks SET availability='available'` for `unavailable` chunks whose file now exists; AND `run_indexer_loop(settings)`: call `scan_once` immediately, then repeat every `SCAN_INTERVAL_SECONDS` via `asyncio.sleep`

**Checkpoint**: Foundation ready — all user story implementation can now begin.

---

## Phase 3: User Story 1 — Browse Camera Timeline (Priority: P1) 🎯 MVP

**Goal**: Operator can open the viewer, select a camera, navigate a date, and see a visual timeline of all recorded clips with accurate start/end times. Unavailable clips appear grayed-out.

**Independent Test**: Run indexer against a directory of sample `.mp4` files → open browser → select camera → verify timeline shows correct clips and gaps. See quickstart.md Scenarios 1–3.

- [x] T012 [P] [US1] Implement `GET /api/monitors` in `backend/app/api/monitors.py` — query `SELECT * FROM monitors ORDER BY display_name` and return list of `MonitorOut`; register router at prefix `/api` in `main.py`
- [x] T013 [US1] Implement `GET /api/monitors/{monitor_id}/chunks` in `backend/app/api/chunks.py` — query `SELECT * FROM video_chunks WHERE monitor_id=? AND start_ts <= ? AND end_ts >= ?` using path param and `from_ts`/`to_ts` query params (both required, validated as integers); return list of `VideoChunkOut`; 404 if monitor not found; register router at prefix `/api`
- [x] T014 [P] [US1] Implement `GET /api/indexer/status` in `backend/app/api/monitors.py` — read `last_scan_at` and `next_scan_in_seconds` from module-level state in `indexer.py`; query DB for `total_monitors`, `total_chunks`, `unavailable_chunks`; return `IndexerStatusOut`
- [x] T015 [P] [US1] Build camera list sidebar in `frontend/index.html` and `frontend/app.js` — on page load, `fetch('/api/monitors')` and render a `<ul>` with one `<li>` per monitor showing `display_name`; clicking a monitor calls `loadTimeline(monitorId, selectedDate)`
- [x] T016 [US1] Build date picker and timeline frame in `frontend/index.html` and `frontend/app.js` — `<input type="date">` defaulting to today; on change, recompute `from_ts`/`to_ts` for that full day (00:00:00 to 23:59:59 local) and call `fetch('/api/monitors/{id}/chunks?from_ts=&to_ts=')`; render a horizontal 24h timeline bar (one pixel = N seconds)
- [x] T017 [US1] Implement chunk rendering on timeline in `frontend/app.js` — for each chunk in the API response, compute pixel offset and width from `start_ts`/`end_ts`; render `<div class="chunk available">` for `availability='available'` and `<div class="chunk unavailable">` for `availability='unavailable'`; gaps between chunks render as empty background
- [x] T018 [P] [US1] Style timeline components in `frontend/style.css` — `.chunk.available` (solid blue), `.chunk.unavailable` (gray, 50% opacity, `cursor: not-allowed`), timeline bar background (dark), camera list highlight on active selection, date picker layout
- [x] T019 [US1] Add indexer status indicator to `frontend/app.js` and `frontend/index.html` — fetch `/api/indexer/status` on load and after each scan cycle; display `last_scan_at` as a human-readable relative time ("Last scan: 12s ago") and auto-refresh every 10 seconds

**Checkpoint**: User Story 1 fully functional. Timeline browsing works end-to-end. Validate with quickstart.md Scenarios 1–3.

---

## Phase 4: User Story 2 — Export a Merged Clip (Priority: P2)

**Goal**: Operator selects a start/end time window, requests an export, monitors progress via a progress bar, cancels if needed, and downloads a single lossless `.mp4` covering the selected range. Rejected with clear messages when busy, no clips found, or disk space insufficient.

**Independent Test**: Select a range spanning 2+ chunks, export, download, verify with ffprobe. See quickstart.md Scenarios 4–6, 8, 10.

- [x] T020 [US2] Implement disk-space pre-check in `backend/app/services/job_manager.py` — `check_disk_space(estimated_bytes: int, cache_dir: Path)`: call `shutil.disk_usage(cache_dir).free`; raise `HTTPException(507)` with detail message `"Insufficient disk space on SSD. Estimated {X} MB required, {Y} MB available."` if free < estimated_bytes * 1.1 (10% safety margin)
- [x] T021 [US2] Implement `POST /api/jobs/export` in `backend/app/api/jobs.py` — (1) 409 if `not is_idle()`; (2) query `video_chunks` for chunks where `monitor_id=req.monitor_id AND availability='available' AND start_ts <= req.to_ts AND end_ts >= req.from_ts` ordered by `start_ts`; (3) 422 with `"No available clips found in the selected time range."` if empty; (4) estimate size as `sum(chunk.file_size_bytes)`; (5) call `check_disk_space(estimated_bytes, CACHE_DIR)`; (6) build filelist via `ffmpeg.build_filelist()`; (7) launch `asyncio.create_subprocess_exec` with `ffmpeg.concat_cmd()`; (8) call `start_job('export', output_path, proc)`; (9) launch `asyncio.create_task(_monitor_job(proc, total_duration_ms))` for progress updates; (10) return 202
- [x] T022 [P] [US2] Implement `_monitor_job(proc, total_duration_ms)` coroutine in `backend/app/api/jobs.py` — read stdout line-by-line; regex `out_time_ms=(\d+)` → `update_progress(elapsed_ms / total_duration_ms)`; on process exit code 0 call `complete_job()`; on non-zero call `fail_job(stderr)`
- [x] T023 [US2] Implement `GET /api/jobs/current` in `backend/app/api/jobs.py` — return `job_state` dict as `JobStatusOut`; if status is `idle` return `{"status": "idle"}`
- [x] T024 [US2] Implement `DELETE /api/jobs/current` in `backend/app/api/jobs.py` — 404 if `is_idle()`; call `cancel_job()` which kills proc and unlinks partial output; return `{"status": "cancelled"}`
- [x] T025 [US2] Implement `GET /api/downloads/{token}` in `backend/app/api/jobs.py` — call `consume_token(token)`; 404 if None or path does not exist; add `BackgroundTasks` task `path.unlink(missing_ok=True)`; return `FileResponse(path, media_type="video/mp4", filename="export.mp4")`
- [x] T026 [US2] Register jobs router in `backend/app/main.py` at prefix `/api`
- [x] T027 [P] [US2] Build time-range selector in `frontend/index.html` and `frontend/app.js` — two `<input type="time">` fields for from/to within the active date; "Export" button (disabled when no monitor/date selected or job running); on click, compute `from_ts`/`to_ts` and `POST /api/jobs/export`; handle 409/422/507 responses with inline error messages
- [x] T028 [US2] Build progress bar and cancel button in `frontend/app.js` — show a `<progress>` element and "Cancel" button when job status is `running`; poll `GET /api/jobs/current` every 2 seconds; update `<progress value="{progress}">` from response; clicking Cancel calls `DELETE /api/jobs/current` and hides progress UI
- [x] T029 [US2] Build download trigger in `frontend/app.js` — when `GET /api/jobs/current` returns `status='done'`, stop polling, hide progress bar, show "Download" link pointing to `/api/downloads/{download_token}`; after link click, reset job UI to idle state; when status is `failed`, show `error` field message and reset UI

**Checkpoint**: User Story 2 fully functional. Export, cancel, download, and all rejection cases work end-to-end. Validate with quickstart.md Scenarios 4–6, 8, 10.

---

## Phase 5: User Story 3 — Generate a Timelapse Preview (Priority: P3)

**Goal**: Operator selects a time window and receives an accelerated video covering only the available footage (no black frames for gaps), ready for download within 60 seconds for a 1-hour window.

**Independent Test**: Select a multi-hour range, request timelapse, download, verify duration ≈ 60s, no black frames. See quickstart.md Scenario 7.

- [x] T030 [US3] Implement speed-factor calculation in `backend/app/services/ffmpeg.py` — `compute_speed(total_source_ms: int, target_output_ms: int = 60_000) -> float`: returns `max(total_source_ms / target_output_ms, 1.0)` to ensure output is never longer than source
- [x] T031 [US3] Implement `POST /api/jobs/timelapse` in `backend/app/api/jobs.py` — same validation flow as export (409/422/507); compute `speed = compute_speed(total_source_duration_ms)`; estimate output size as `sum(file_size_bytes) / speed`; build filelist; launch `asyncio.create_subprocess_exec` with `ffmpeg.timelapse_cmd(filelist, output, speed)`; launch `_monitor_job` task; return 202
- [x] T032 [P] [US3] Add "Timelapse" button alongside "Export" in `frontend/app.js` and `frontend/index.html` — reuses the same from/to time inputs and the existing progress bar + download UI from US2; on click, calls `POST /api/jobs/timelapse`
- [x] T033 [US3] Show job-type label in progress UI in `frontend/app.js` — read `type` field from `GET /api/jobs/current` and display `"Exporting…"` or `"Generating timelapse…"` above the progress bar accordingly

**Checkpoint**: All three user stories fully functional. Validate with quickstart.md Scenario 7.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hardening and UX completeness across all stories.

- [x] T034 [P] Enforce unavailable-chunk non-selectability in `frontend/app.js` — when user drags or clicks the time-range selector, clamp the selection to exclude ranges covered only by `unavailable` chunks; show tooltip "This segment is no longer available on disk" on hover of grayed-out chunks
- [x] T035 [P] Add global error boundary in `frontend/app.js` — catch all `fetch` errors (network down, 500) and display a dismissible banner; auto-retry indexer status fetch on network error
- [x] T036 Validate all 10 quickstart.md scenarios end-to-end — run each `curl`/browser scenario from `specs/001-shinobi-viewer/quickstart.md` and confirm expected outcomes; document any deviations
- [x] T037 [P] Create `backend/README.md` with setup instructions: prerequisites (Python 3.10+, FFmpeg), install (`pip install -r requirements.txt`), configure (copy `.env.example` to `.env`, set paths), run (`uvicorn app.main:app --host 0.0.0.0 --port 8080`), and link to quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Requires Phase 1 complete — **blocks all user stories**
- **US1 (Phase 3)**: Requires Phase 2 complete
- **US2 (Phase 4)**: Requires Phase 2 complete; integrates JobManager from T009
- **US3 (Phase 5)**: Requires Phase 2 complete; reuses export infrastructure from Phase 4 (T009, T021–T026)
- **Polish (Phase 6)**: Requires all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 — fully independent
- **US2 (P2)**: Depends on Phase 2 + T009 (JobManager); independently testable without US1 UI (via `curl`)
- **US3 (P3)**: Depends on Phase 2 + T009 + T021–T026 (export infrastructure reused) — independently testable via `curl`

### Within Each Phase

- Tasks marked **[P]** within the same phase can run in parallel (they touch different files)
- Tasks without **[P]** depend on the immediately preceding non-parallel task in the same phase

---

## Parallel Execution Examples

### Phase 2 (Foundational)

```bash
# These four can run in parallel (different files):
Task T007: backend/app/models.py
Task T008: backend/app/services/ffmpeg.py

# Then T009 depends on T007 (uses models)
# Then T010 depends on T006, T007 (imports)
# Then T011 depends on T006, T010
```

### Phase 3 (US1)

```bash
# These can run in parallel:
Task T012: backend/app/api/monitors.py
Task T013: backend/app/api/chunks.py
Task T014: backend/app/api/monitors.py (indexer status — different function)
Task T015: frontend/index.html + app.js (camera list)
Task T018: frontend/style.css
```

### Phase 4 (US2)

```bash
# These can run in parallel:
Task T022: _monitor_job coroutine (within jobs.py)
Task T027: frontend time-range selector (different concern from backend)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Open browser, select camera, browse timeline
5. Deploy/demo if ready

### Incremental Delivery

1. **Phase 1 + Phase 2** → Foundation ready
2. **+ Phase 3** → Browse camera timeline → **Demo (MVP)**
3. **+ Phase 4** → Export merged clip → **Demo**
4. **+ Phase 5** → Timelapse preview → **Demo**
5. **+ Phase 6** → Polished, validated product

### Parallel Team Strategy

With two developers after Phase 2 completes:

- Developer A: Phase 3 (US1 — timeline browsing)
- Developer B: Phase 4 (US2 — export) using `curl` to test without UI

---

## Notes

- `[P]` tasks touch different files and have no shared in-progress dependencies
- `[Story]` label maps each task to a user story for traceability
- Constitution guards (zero HDD writes, mtime < 60s guard, SSD-only metadata) must be preserved in T011 and T008 — never pass HDD paths as FFmpeg output targets
- All timestamps in the API and DB are Unix milliseconds (integers)
- Commit after each checkpoint to enable easy rollback to a working state
