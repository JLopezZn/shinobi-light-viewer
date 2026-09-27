# Tasks: Shinobi Pod Manager

**Input**: Design documents from `/specs/002-shinobi-pod-manager/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Not requested — no test tasks generated.

**Organization**: Tasks grouped by user story. US4 (startup scripts) is independent of US1–US3 and can run in parallel with Phase 4.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Environment configuration groundwork needed before any implementation.

- [x] T001 Add `SHINOBI_CONTAINER=shinobi` and `ADMIN_TOKEN=changeme` variables to `backend/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story. Docker service + auth dependency gate all endpoints.

**⚠️ CRITICAL**: No user story backend work can begin until T002–T004 are complete.

- [x] T002 Update `Settings.__init__` in `backend/app/config.py` to load `SHINOBI_CONTAINER = os.getenv("SHINOBI_CONTAINER", "shinobi")` and `ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]` (required — raise `KeyError` with helpful message if absent, preventing server start without auth)
- [x] T003 [P] Create `backend/app/services/docker_manager.py` with: `ContainerStatus` dataclass (fields: `status: str` — values `"running"`, `"stopped"`, `"unknown"`; `container: str`; `message: str | None = None`); and four functions — `get_container_status(container: str) -> ContainerStatus` (runs `docker inspect --format={{.State.Status}} <container>`, maps raw Docker state to normalized values per data-model.md status mapping table; returns `unknown` on `FileNotFoundError` or non-zero exit); `start_container(container: str) -> ContainerStatus`; `stop_container(container: str) -> ContainerStatus`; `restart_container(container: str) -> ContainerStatus` (calls `stop_container` then `start_container`; raises `RuntimeError` on stop failure without attempting start). All subprocess calls use `subprocess.run(..., capture_output=True, text=True)`.
- [x] T004 Add `require_admin_token` FastAPI dependency to `backend/app/api/admin.py`: function receives `x_admin_token: str = Header(...)`, compares against `settings.admin_token` using `secrets.compare_digest`, raises `HTTPException(status_code=401, detail="Unauthorized")` on mismatch; apply `Depends(require_admin_token)` to the existing `DELETE /db` endpoint signature

**Checkpoint**: Foundation ready — Docker service + admin auth in place. US4 (startup scripts) can now start in parallel with US1.

---

## Phase 3: User Story 4 — Arranque seguro del servidor (Priority: P1)

**Goal**: `start.sh` and `start.bat` wait for the Shinobi container before launching uvicorn, preventing startup crashes.

**Independent Test**: Run script with container stopped → script loops with progress messages. Start container from another terminal → script detects running state and proceeds. Let it timeout (120s) → script prints error and exits code 1 without starting uvicorn.

- [x] T005 [P] [US4] Modify `start.sh`: after the `.env` loading block (after `set +a`) and before the final `exec uvicorn` line, insert a pre-flight loop — `SHINOBI_CONTAINER="${SHINOBI_CONTAINER:-shinobi}"`, loop using `status=$(docker inspect --format='{{.State.Status}}' "$SHINOBI_CONTAINER" 2>/dev/null || true)` (**`|| true` is required** because `start.sh` has `set -e` at line 2 — without it, a non-zero exit from `docker inspect` when the container is not yet running would abort the script immediately), sleep 5s between attempts, track elapsed time; break loop when `$status` equals `"running"`; if elapsed ≥ 120s print `[docker] Timeout: Shinobi container did not start within 120s. Aborting.` and `exit 1`; on success print `[docker] Shinobi container is running.`
- [x] T006 [P] [US4] Modify `start.bat`: after the env loading `for /f` loop block and before the final `uvicorn.exe` launch line, insert a pre-flight loop — use `docker inspect --format={{.State.Status}} %SHINOBI_CONTAINER%` piped to `findstr /c:"running"`, use `timeout /t 5 /nobreak >nul` for sleep, count iterations (24 max = 120s); on success `echo [docker] Shinobi container is running.`; on timeout `echo [docker] Timeout: Shinobi container did not start within 120s. Aborting.` followed by `pause` and `exit /b 1`

**Checkpoint**: Both startup scripts safely gate uvicorn launch on Shinobi container readiness.

---

## Phase 4: User Story 1 — Detener Shinobi desde la UI (Priority: P1) 🎯 MVP

**Goal**: Admin can see the container status and stop the Shinobi container from the web UI.

**Independent Test**: Open app, navigate to admin section, enter token → status badge shows current state with auto-refresh every 3s. Click "Detener Shinobi" → badge transitions to "Detenido" within 30s. Verify `docker ps | grep shinobi` shows no running container.

- [x] T007 [US1] Add `GET /api/admin/docker/status` route to `backend/app/api/admin.py` with `Depends(require_admin_token)`; use decorator `@router.get("/admin/docker/status")` — the route path must be `"/admin/docker/status"` (not `"/api/admin/docker/status"`) because the admin router is already mounted with `prefix="/api"` in `main.py`; calls `docker_manager.get_container_status(settings.shinobi_container)`; returns `{"status": ..., "container": ...}` always with HTTP 200 (never 500 — returns `status: "unknown"` with optional `message` field when Docker is unavailable)
- [x] T008 [US1] Add `POST /api/admin/docker/stop` route to `backend/app/api/admin.py` with `Depends(require_admin_token)`; use decorator `@router.post("/admin/docker/stop")` (path without `/api` prefix — see T007 note); calls `docker_manager.stop_container(settings.shinobi_container)`; returns `ContainerStatus` as JSON; if container was already stopped, calls `get_container_status` and returns 200 with `message: "Container was already stopped"`; on `RuntimeError` from subprocess raises `HTTPException(status_code=500, detail=f"Failed to stop container: {err}")`
- [x] T009 [US1] Add Gestor de Shinobi section to `frontend/index.html` inside the existing admin area: token entry form (`<div id="admin-token-form">` with `<input id="admin-token" type="password">` and Save button), container status display (`<div id="gestor-panel">` hidden until token set, containing `<span id="docker-status" class="badge">...</span>` and three action buttons: `<button id="btn-stop">Detener Shinobi</button>`, `<button id="btn-start" disabled>Iniciar Shinobi</button>`, `<button id="btn-restart" disabled>Reiniciar Shinobi</button>`); **`#btn-start` and `#btn-restart` must be rendered with `disabled` attribute** — their event handlers are wired in T012 and T014 respectively, and they must not be clickable until those tasks are implemented
- [x] T010 [US1] Implement `DockerManager` module in `frontend/app.js`: on section load read `adminToken` from `sessionStorage`; if absent show `#admin-token-form` and hide `#gestor-panel`; Save button writes token to `sessionStorage` and switches visibility; on panel visible start `setInterval(pollStatus, 3000)` calling `GET /api/admin/docker/status` with `X-Admin-Token` header and updating `#docker-status` text and CSS class (`badge-running`, `badge-stopped`, `badge-unknown`); on panel hidden/destroy call `clearInterval`; stop button click: disable `#btn-stop`, `#btn-start`, `#btn-restart`, call `POST /api/admin/docker/stop`, re-enable buttons, show error message `<div id="gestor-error">` on failure

**Checkpoint**: Admin can view live container status and safely stop Shinobi. US1 fully functional.

---

## Phase 5: User Story 2 — Iniciar Shinobi desde la UI (Priority: P2)

**Goal**: Admin can start the Shinobi container from the web UI.

**Independent Test**: With container stopped and admin panel open, click "Iniciar Shinobi" → status transitions to "En ejecución" within 30s. Verify with `docker ps | grep shinobi`.

- [x] T011 [US2] Add `POST /api/admin/docker/start` route to `backend/app/api/admin.py` with `Depends(require_admin_token)`; use decorator `@router.post("/admin/docker/start")` (path without `/api` prefix — see T007 note); calls `docker_manager.start_container(settings.shinobi_container)`; returns `ContainerStatus` as JSON; if container was already running, calls `get_container_status` and returns 200 with `message: "Container was already running"`; on `RuntimeError` raises `HTTPException(status_code=500, detail=f"Failed to start container: {err}")`
- [x] T012 [US2] Wire start button in `frontend/app.js` inside the `DockerManager` module: start button click disables all three action buttons, calls `POST /api/admin/docker/start` with `X-Admin-Token` header, re-enables buttons on response, updates status badge, shows `#gestor-error` message on failure (same pattern as stop handler in T010)

**Checkpoint**: Admin can start and stop the container from the web UI. US1 + US2 fully functional.

---

## Phase 6: User Story 3 — Reiniciar Shinobi desde la UI (Priority: P2)

**Goal**: Admin can restart (stop then start) the Shinobi container in a single click.

**Independent Test**: With container running, click "Reiniciar Shinobi" → status cycles through stopped then returns to running within 60s. Container uptime resets.

- [x] T013 [US3] Add `POST /api/admin/docker/restart` route to `backend/app/api/admin.py` with `Depends(require_admin_token)`; use decorator `@router.post("/admin/docker/restart")` (path without `/api` prefix — see T007 note); calls `docker_manager.restart_container(settings.shinobi_container)`; on `RuntimeError` during stop phase raises `HTTPException(status_code=500, detail=f"Restart aborted: failed to stop container: {err}")`; on `RuntimeError` during start phase raises `HTTPException(status_code=500, detail=f"Restart aborted: container stopped but failed to start: {err}")`; on success returns final `ContainerStatus`
- [x] T014 [US3] Wire restart button in `frontend/app.js` inside the `DockerManager` module: restart button click disables all three action buttons, calls `POST /api/admin/docker/restart` with `X-Admin-Token` header, re-enables buttons on response, updates status badge, shows `#gestor-error` on failure

**Checkpoint**: All three container management actions (start/stop/restart) fully functional in the UI.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Visual polish and end-to-end validation.

- [x] T015 [P] Add CSS rules for container status badge states to `frontend/style.css`: `.badge-running` (green background or green text), `.badge-stopped` (red), `.badge-unknown` (grey/amber); ensure badges are visually distinguishable at a glance
- [x] T016 Run all 7 validation scenarios from `specs/002-shinobi-pod-manager/quickstart.md` end-to-end and confirm each passes (startup timeout, token gate, stop/start/restart from UI, Docker unavailable graceful degradation, idempotency)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all backend user story work
- **Phase 3 (US4)**: Can start in parallel with Phase 4 once Phase 2 is done — touches only `start.bat` and `start.sh`
- **Phase 4 (US1)**: Depends on Phase 2 — delivers MVP
- **Phase 5 (US2)**: Depends on Phase 4 (reuses DockerManager module and panel structure)
- **Phase 6 (US3)**: Depends on Phase 4 and Phase 5
- **Phase 7 (Polish)**: Depends on Phases 3–6

### User Story Dependencies

- **US4 (P1)**: Independent of US1–US3; can be done by a separate developer in parallel with Phase 4
- **US1 (P1)**: Requires Phase 2 complete; no dependency on US4
- **US2 (P2)**: Requires US1 panel structure from T009 and polling from T010
- **US3 (P2)**: Requires US2 (all three buttons should work before restart is added)

### Within Each Phase

- T003 and T004 can run in parallel (different files)
- T005 and T006 can run in parallel (different script files)
- T007 and T008 can be done in either order (both in admin.py, but endpoint-level additions)
- T009 (HTML) and T010 (JS) can start in parallel; T010 depends on the IDs defined in T009

---

## Parallel Execution Example: Phase 4 (US1)

```
# Start together (different files):
T007 → backend/app/api/admin.py (GET status endpoint)
T009 → frontend/index.html (panel HTML)

# Then in parallel:
T008 → backend/app/api/admin.py (POST stop endpoint)
T010 → frontend/app.js (DockerManager module)
```

---

## Implementation Strategy

### MVP First (US4 + US1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T004)
3. Complete Phase 3: US4 (T005–T006) — safe startup scripts
4. Complete Phase 4: US1 (T007–T010) — stop from UI + status polling
5. **STOP and VALIDATE**: Run quickstart.md scenarios 1–4
6. **This is the minimum viable feature** — the core safety goal (stop before PC restart) is met

### Full Delivery

6. Phase 5: US2 (T011–T012) — start from UI
7. Phase 6: US3 (T013–T014) — restart from UI
8. Phase 7: Polish (T015–T016) — visual + final validation

### Parallel Opportunity

US4 startup scripts (T005–T006) can be developed simultaneously with US1 backend work (T007–T008) since they touch completely separate files.

---

## Notes

- [P] tasks = different files, no inter-task dependencies — safe to run concurrently
- [Story] label maps each task to its user story for traceability to spec.md
- `ADMIN_TOKEN` is required at server startup; server will not start if absent — communicate this to the user before deploying
- The existing `DELETE /api/admin/db` endpoint becomes auth-protected by T004 — this is a **breaking change** for any existing scripts that call it without a token
- Avoid making the status endpoint return 500; always return `unknown` status so the UI degrades gracefully when Docker is unavailable
