# Tasks: Git Updates, Branch Switcher & App Stability

**Input**: Design documents from `specs/003-git-updates-stability/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Not requested — no test tasks generated.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Web app layout (existing):
- Backend: `backend/app/api/`, `backend/app/services/`
- Frontend: `frontend/`
- Supervisor (new): `supervisor/` at repo root

---

## Phase 1: Setup (New Files & Skeletons)

**Purpose**: Create the new files and module stubs so Phase 2 work can proceed in parallel.

- [x] T001 Create `supervisor/__init__.py` as an empty file to make `supervisor/` a Python package
- [x] T002 [P] Create `backend/app/services/git_manager.py` with `REPO_ROOT` detection via `subprocess.run(["git", "rev-parse", "--show-toplevel"])` and empty stubs for `git_pull()`, `list_branches()`, `checkout_branch(branch)`
- [x] T003 [P] Create `backend/app/api/git_ops.py` with a FastAPI `APIRouter`, re-use the existing `require_admin_token` dependency from `backend/app/api/admin.py`, and a `threading.Lock` instance for mutual-exclusion between update and switch operations

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure that MUST be complete before any user story can be validated end-to-end.

**⚠️ CRITICAL**: Start scripts and router registration must be in place before testing any story.

- [x] T004 Implement `AppState` dataclass in `supervisor/supervisor.py` with fields: `status` (str enum literal: `"starting"`, `"running"`, `"restarting"`, `"crash_capped"`), `current_branch` (str), `crash_count` (int), `crash_window_start` (datetime|None), `last_crash_at` (datetime|None), `last_crash_reason` (str|None), `pending_operation` (str|None, values: `None`, `"update"`, `"switch"`); and `CrashEvent` dataclass with fields: `timestamp` (datetime), `exit_code` (int), `reason` (str, truncated to 500 chars per data-model.md), `restarted` (bool); maintain a `deque(maxlen=20)` crash event log per data-model.md
- [x] T005 Update `start.sh` to replace the final `exec "$VENV/bin/uvicorn" ...` line with `exec "$VENV/bin/python3" "$SCRIPT_DIR/supervisor/supervisor.py"` so the supervisor becomes the process entry point; ensure `PORT`, `BACKEND`, `VENV`, and loaded `.env` vars are available to the supervisor via environment
- [x] T006 [P] Update `start.bat` to replace the final `uvicorn.exe` invocation with `"%VENV%\Scripts\python.exe" "%SCRIPT_DIR%supervisor\supervisor.py"` using the same env vars
- [x] T007 Register the `git_ops` router in `backend/app/main.py` with prefix `/api/admin/git` alongside the existing routers (monitors, chunks, video, jobs, admin)

**Checkpoint**: Foundation ready — supervisor entry point wired, router registered, skeletons in place.

---

## Phase 3: User Story 1 — Auto-Restart After Crash (Priority: P1) 🎯 MVP

**Goal**: The app automatically recovers from crashes; operator can manually recover when the crash cap is hit via a status page that stays alive independently of the main app.

**Independent Test**: Follow quickstart.md S1.1 (single crash recovery) and S1.2 (crash-cap + manual restart). Verify main app restarts within 10 s for single crash; verify status page at `$STATUS_PORT` remains accessible and shows "Reiniciar App" when crash-capped; verify clicking it resets the counter and resumes normal operation.

- [x] T008 [US1] Implement the watchdog loop in `supervisor/supervisor.py`: spawn `uvicorn app.main:app --host 0.0.0.0 --port $PORT` as a subprocess inside `$BACKEND` working directory using the virtualenv Python; on exit code 0 or SIGTERM: restart immediately (not a crash); on exit code 42: reset `crash_count` to 0, reset `crash_window_start` to None, restart immediately (intentional restart per research.md Decision 2); on any other exit code: apply crash-cap algorithm from data-model.md (CRASH_LIMIT=5, CRASH_WINDOW_SECONDS=120, BACKOFF_SECONDS=2), append a CrashEvent to the log, update `AppState`; when cap hit: set `status = "crash_capped"` and stop restarting
- [x] T009 [US1] Implement `supervisor/status_server.py` using `http.server.ThreadingHTTPServer` started on `STATUS_PORT` (env var; default `int(os.getenv("PORT", "8090")) + 1`): `GET /` returns HTML; `GET /api/status` returns `AppState` as JSON (all fields from data-model.md); `POST /api/restart` resets crash counter and calls watchdog restart only when `state == "crash_capped"` — if not crash-capped, return `{"status": "already_running"}`
- [x] T010 [US1] Implement the HTML response for `GET /` in `supervisor/status_server.py`: show state badge (color-coded), current branch, crash_count, crash_window_start, last 5 crash events from the log (timestamp + reason excerpt); include a "Reiniciar App" `<button>` that POSTs to `/api/restart` — button MUST be `disabled` in HTML unless `status == "crash_capped"` (FR-002a)
- [x] T011 [US1] Start the status server as a `daemon=True` thread in `supervisor/supervisor.py` at startup, before the watchdog loop begins, so it remains accessible even when the main app process is stopped

**Checkpoint**: US1 complete — crash recovery and status page independently functional. Validate with quickstart.md S1.1 and S1.2 before proceeding.

---

## Phase 4: User Story 2 — Buscar Actualizaciones Button (Priority: P2)

**Goal**: Operator can pull the latest code from the current branch using a UI button; app restarts automatically on success; errors are shown clearly with the repo left in a clean state.

**Independent Test**: Follow quickstart.md S2.1–S2.4. Verify "already up to date" shows no restart; successful pull triggers restart and new commit is visible after; conflict error leaves repo clean; concurrent operation attempt returns 409.

- [x] T012 [US2] Implement `git_pull()` in `backend/app/services/git_manager.py`: run `subprocess.run(["git", "pull"], cwd=REPO_ROOT, capture_output=True, text=True)`; if `returncode != 0`: run `subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=REPO_ROOT)` then return `{"status": "failed", "summary": stderr_text}`; if stdout contains `"Already up to date"`: return `{"status": "up_to_date", "summary": stdout_text}`; otherwise return `{"status": "success", "summary": stdout_text}`
- [x] T013 [US2] Implement `GET /api/admin/git/status` in `backend/app/api/git_ops.py`: run `git rev-parse --abbrev-ref HEAD` to get current branch name; return `{"branch": branch_name, "pending_operation": <None or "update" or "switch" based on lock state>}`
- [x] T014 [US2] Implement `POST /api/admin/git/update` in `backend/app/api/git_ops.py`: attempt to acquire the mutual-exclusion lock (return HTTP 409 with `{"detail": "Una operación está en curso. Intente de nuevo en unos segundos."}` if already held); call `git_manager.git_pull()`; release lock; if status is `"failed"` or `"up_to_date"`, return result as JSON and stop; if status is `"success"`, send the JSON response and schedule `os._exit(42)` via a short-delay background task (0.5 s delay to allow HTTP response to flush) so the supervisor restarts the app
- [x] T015 [US2] Add a "Buscar Actualizaciones" button inside the `#gestor-panel` div in `frontend/index.html`, after the existing docker action buttons and before the error div; give it id `btn-update-app`
- [x] T016 [US2] Implement update button logic in `frontend/app.js`: on `#btn-update-app` click, disable the button and show a loading label; `POST /api/admin/git/update` with `X-Admin-Token` header; on response, display result message in `#gestor-error` (or a dedicated `#update-result` span); if status is `"success"`, poll `GET /api/admin/git/status` (or any lightweight endpoint) every 2 s until the app responds again (handles the restart window), then re-enable the button; on `"up_to_date"` or `"failed"`, re-enable immediately

**Checkpoint**: US2 complete — update button fully functional. Validate with quickstart.md S2.1–S2.4.

---

## Phase 5: User Story 3 — Branch Switcher (Priority: P3)

**Goal**: Operator can view all local and remote branches in a dropdown (with live fetch), select one, and the app switches and restarts automatically; failures revert cleanly.

**Independent Test**: Follow quickstart.md S3.1–S3.4. Verify remote-only branch appears after fetch; switch triggers restart on correct branch; selecting current branch shows no-op message; non-existent branch returns error and original branch is retained.

- [x] T017 [US3] Implement `list_branches()` in `backend/app/services/git_manager.py`: run `git fetch --prune --quiet`; if fetch fails, note the error string; run `git branch -a`; parse output: strip leading `* ` and `  `, strip `remotes/origin/` prefix from remote refs, skip `HEAD ->` lines, build a list of unique `{"name": str, "is_current": bool, "is_local": bool, "is_remote": bool}` dicts; return `{"branches": [...], "warning": fetch_error_or_None}`
- [x] T018 [US3] Implement `checkout_branch(branch: str)` in `backend/app/services/git_manager.py`: capture current branch via `git rev-parse --abbrev-ref HEAD`; run `git checkout <branch>`; if exit non-zero, run `git checkout <previous_branch>` to revert, return `{"status": "failed", "branch": previous_branch, "summary": stderr}`; if checkout succeeds return `{"status": "success", "branch": branch}`; if already on requested branch return `{"status": "already_current", "branch": branch}`
- [x] T019 [US3] Implement `GET /api/admin/git/branches` in `backend/app/api/git_ops.py`: acquire mutual-exclusion lock (return 409 if held); call `list_branches()`; release lock; return response including `branches` array and optional `warning` field if remote fetch failed
- [x] T020 [US3] Implement `POST /api/admin/git/switch` in `backend/app/api/git_ops.py`: validate request body has `branch` field (required, max 200 chars per data-model.md; reject with 422 if missing or exceeds limit; reject with 422 if `branch` does not match `^[\w\-./]+$` to prevent shell metacharacter injection); acquire mutual-exclusion lock (409 if held); call `checkout_branch(branch)`; release lock; if `"already_current"`, return result without restart; if `"failed"`, return error response; if `"success"`, send response then schedule `os._exit(42)` via background task (same pattern as T014)
- [x] T021 [US3] Add branch selector UI to `frontend/index.html`: add a `<div id="branch-section">` inside `#gestor-panel` with a `<select id="branch-select">` (placeholder option "Cargando ramas..."), a loading spinner element `<span id="branch-loading">`, and a `<button id="btn-switch-branch" disabled>Cambiar rama</button>`
- [x] T022 [US3] Implement branch switcher JS in `frontend/app.js`: when `#gestor-panel` becomes visible (token saved), immediately fetch branches via `GET /api/admin/git/branches` with admin token, show `#branch-loading` during fetch, populate `#branch-select` with options (marking the current branch as selected and disabled); on `#btn-switch-branch` click, disable button, POST `/api/admin/git/switch` with `{"branch": selected_value}` and admin token header; on success, poll until app is back online then reload branches; on `"already_current"`, show info message; on error, show error message and re-enable button

**Checkpoint**: US3 complete — branch switcher fully functional. Validate with quickstart.md S3.1–S3.4.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, environment documentation, and final validation.

- [x] T023 [P] Add `STATUS_PORT` to `backend/.env.example` with a comment explaining it defaults to `$PORT + 1` and controls the supervisor status server port; also document `PORT` default in the same file if not already present
- [x] T024 [P] Audit all `subprocess.run(["git", ...])` calls in `backend/app/services/git_manager.py` and `supervisor/supervisor.py` to confirm every call uses `cwd=REPO_ROOT`; add a module-level assertion that `REPO_ROOT` contains a `.git` directory at startup
- [x] T025 [P] Verify the `#gestor-panel` update and branch-switcher UI elements in `frontend/index.html` are hidden when no admin token is set (consistent with existing `display:none` behavior of `#gestor-panel`) and visible once the token is saved
- [x] T026 Run all 10 scenarios in `specs/003-git-updates-stability/quickstart.md` and confirm each passes against the verification checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T002 and T003 can run in parallel with T001
- **Foundational (Phase 2)**: Requires Phase 1 complete — BLOCKS all user stories; T005, T006, T007 can run in parallel after T004
- **US1 (Phase 3)**: Requires Phase 2 — T008 first, then T009–T011 can proceed (T010 depends on T009)
- **US2 (Phase 4)**: Requires Phase 2 (and Phase 3 for exit-code-42 to work); T012–T014 before T015–T016; T015 and T016 can be worked in parallel once T014 is done
- **US3 (Phase 5)**: Requires Phase 2 (and Phase 3); T017–T018 in parallel, then T019–T020 (T019 needs T017, T020 needs T018), then T021–T022 in parallel
- **Polish (Phase 6)**: Requires all user stories complete; T023–T025 can run in parallel

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 — no other story dependencies
- **US2 (P2)**: Depends on Phase 2 + US1 (supervisor must handle exit code 42)
- **US3 (P3)**: Depends on Phase 2 + US1 (supervisor must handle exit code 42); independent of US2

### Within Each User Story

- Services before endpoints (git_manager.py before git_ops.py)
- Endpoints before frontend
- Backend implementation before frontend wiring

### Parallel Opportunities

- T002, T003 (Phase 1): different files, no dependency between them
- T005, T006, T007 (Phase 2): different files, no dependency between them
- T009, T010, T011 (US1): T009 before T010; T011 can start alongside T009
- T012, T013 (US2): different methods/endpoints, no dependency
- T015, T016 (US2): frontend HTML and JS can proceed in parallel once T014 is done
- T017, T018 (US3): different functions in git_manager.py — can be split
- T021, T022 (US3): HTML and JS skeleton can be built in parallel
- T023, T024, T025 (Polish): all independent

---

## Parallel Example: User Story 1

```
Phase 3 start → T008 (watchdog loop)
             → T009 (status server HTTP scaffold)
                └─→ T010 (HTML page — needs server routes)
             → T011 (daemon thread start — can proceed with T009)
```

## Parallel Example: User Story 3

```
Phase 5 start → T017 (list_branches) ──→ T019 (GET /branches endpoint)
             → T018 (checkout_branch) ─→ T020 (POST /switch endpoint)
             → T021 (HTML elements)
             → T022 (JS logic — after T019/T020 contract is known)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T007)
3. Complete Phase 3: US1 (T008–T011)
4. **STOP and VALIDATE**: Run quickstart.md S1.1 and S1.2
5. App now self-heals — ship this increment

### Incremental Delivery

1. Setup + Foundational → wired entry point
2. US1 (T008–T011) → crash recovery + status page (MVP)
3. US2 (T012–T016) → in-app update button
4. US3 (T017–T022) → branch switcher
5. Polish (T023–T026) → final hardening

### Single Developer Order (Sequential)

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 → T016 → T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024 → T025 → T026

---

## Notes

- `[P]` tasks touch different files — safe to hand to parallel agents or developers
- Exit code 42 is the intentional-restart signal; US2 and US3 rely on this being handled in US1
- `os._exit(42)` bypasses Python atexit handlers — use it (not `sys.exit()`) to guarantee the supervisor receives the exact exit code
- All git subprocess calls must use `cwd=REPO_ROOT`, never `cwd=BACKEND` — the repo root is one level above `backend/`
- The `branch` field in POST /switch must be validated against `^[\w\-./]+$` before passing to subprocess (T020) to prevent shell injection
- Commit after each phase checkpoint to keep rollback clean
