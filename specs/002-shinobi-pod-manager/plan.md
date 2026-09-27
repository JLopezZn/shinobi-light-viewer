# Implementation Plan: Shinobi Pod Manager

**Branch**: `001-shinobi-viewer` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-shinobi-pod-manager/spec.md`

## Summary

Add a Shinobi container management panel to the existing admin section of the web UI, allowing users to start, stop, and restart the Docker container running Shinobi before shutting down the host machine. Additionally, patch `start.bat` and `start.sh` to wait for the container to be running before launching the FastAPI server, preventing startup crashes. The backend exposes four new endpoints under `/api/admin/docker/` protected by a token-based admin auth dependency (also retrofitted to the existing `DELETE /api/admin/db` endpoint). The frontend polls the status endpoint every 3 seconds while the admin panel is open.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: FastAPI 0.110, uvicorn 0.28, aiofiles 23.2 (no new pip dependencies required)

**Storage**: No new storage — all state is ephemeral (Docker daemon query per request)

**Testing**: pytest + pytest-asyncio

**Target Platform**: Windows (Docker Desktop) + Linux (Docker Engine)

**Project Type**: Web service (FastAPI backend + Vanilla JS static frontend)

**Performance Goals**: Status endpoint must respond in < 2 seconds (single `docker inspect` subprocess call)

**Constraints**: No new pip dependencies; Docker CLI must be on PATH; `ADMIN_TOKEN` must be non-empty at startup

**Scale/Scope**: Single-operator local network app; 1 user at a time

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Zero Interference with Shinobi HDD | ✅ PASS | No file operations — only Docker subprocess calls |
| Concurrent Read/Write Safety | ✅ PASS | No filesystem access from this feature |
| Decoupled Metadata Storage | ✅ PASS | No new DB writes; env vars on local system |
| Python 3.10+ / FastAPI | ✅ PASS | All new code follows existing stack |
| SQLite on Local SSD | ✅ PASS | No schema changes |
| FFmpeg via controlled subprocesses | N/A | Not applicable to this feature |
| Temp file purge | N/A | No temp files generated |

**Post-design re-check**: All gates still pass. Docker subprocess calls are read/control operations against the Docker daemon — no interaction with the HDD or Shinobi's data files.

## Project Structure

### Documentation (this feature)

```text
specs/002-shinobi-pod-manager/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── admin-docker-api.md   ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code Changes

```text
backend/
├── app/
│   ├── api/
│   │   └── admin.py              ← modified: add docker routes + auth dependency
│   ├── config.py                 ← modified: add SHINOBI_CONTAINER, ADMIN_TOKEN
│   └── services/
│       └── docker_manager.py     ← NEW: Docker subprocess operations
├── .env.example                  ← modified: add SHINOBI_CONTAINER, ADMIN_TOKEN
└── requirements.txt              ← unchanged (no new deps)

frontend/
├── index.html                    ← modified: add manager panel section
└── app.js                        ← modified: add polling logic + action handlers

start.bat                         ← modified: add Docker pre-flight wait loop
start.sh                          ← modified: add Docker pre-flight wait loop
```

**Structure Decision**: Single project (web service), existing structure. Feature slots into the existing `backend/app/services/` and `backend/app/api/` patterns with no new top-level directories.

## Component Design

### 1. `backend/app/services/docker_manager.py` (NEW)

Thin wrapper around Docker CLI via `subprocess`. No async — Docker CLI calls are fast (< 1s locally) and blocking is acceptable for admin operations. Uses `subprocess.run` with `capture_output=True`.

**Functions**:
- `get_container_status(container: str) -> ContainerStatus` — runs `docker inspect --format={{.State.Status}} <container>`, maps raw state to normalized enum
- `start_container(container: str) -> ContainerStatus` — runs `docker start <container>`, then calls `get_container_status`
- `stop_container(container: str) -> ContainerStatus` — runs `docker stop <container>`, then calls `get_container_status`
- `restart_container(container: str) -> ContainerStatus` — calls `stop_container` then `start_container`; raises on stop failure before attempting start

**Error handling**: If subprocess returns non-zero exit code, raises `RuntimeError` with stderr content. If `docker` is not on PATH (`FileNotFoundError`), returns `unknown` status for status queries, raises for action operations.

### 2. `backend/app/config.py` (MODIFIED)

Add two new env var reads to `Settings.__init__`:
- `SHINOBI_CONTAINER = os.getenv("SHINOBI_CONTAINER", "shinobi")` — no default validation needed (has fallback)
- `ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]` — **required**; raises `KeyError` at startup if absent, preventing the server from running without auth

### 3. `backend/app/api/admin.py` (MODIFIED)

Add:
1. **Auth dependency** `require_admin_token(x_admin_token: str = Header(...)) -> None` — compares against `settings.admin_token` using `secrets.compare_digest`; raises `HTTPException(401)` on mismatch
2. **Apply to existing `DELETE /db`** — add `Depends(require_admin_token)` (breaking change, intentional per spec)
3. **Four new routes** all with `Depends(require_admin_token)`:
   - `GET /api/admin/docker/status`
   - `POST /api/admin/docker/start`
   - `POST /api/admin/docker/stop`
   - `POST /api/admin/docker/restart`

See [`contracts/admin-docker-api.md`](contracts/admin-docker-api.md) for response shapes.

### 4. `frontend/index.html` (MODIFIED)

Add a **Gestor de Shinobi** panel inside the existing admin section. Contains:
- Status badge: `<span id="docker-status">...</span>` styled by state (green/red/grey)
- Three action buttons: `<button id="btn-start">`, `<button id="btn-stop">`, `<button id="btn-restart">`
- Token input: `<input id="admin-token" type="password">` + `<button>Guardar token</button>` (visible until token is set in sessionStorage)

### 5. `frontend/app.js` (MODIFIED)

Add a `DockerManager` module:
- On panel visibility: start `setInterval` polling `GET /api/admin/docker/status` every 3 seconds
- On panel hidden/destroy: `clearInterval`
- On action button click: disable all three buttons, call relevant endpoint, re-enable on response (success or error)
- Token stored in `sessionStorage` under key `adminToken`; if missing, show token input, hide action buttons

### 6. `start.bat` / `start.sh` (MODIFIED)

After `.env` is loaded (so `SHINOBI_CONTAINER` is available), insert a pre-flight loop:

**start.sh pattern**:
```
SHINOBI_CONTAINER="${SHINOBI_CONTAINER:-shinobi}"
MAX_WAIT=120; waited=0; interval=5
while true; do
  status=$(docker inspect --format='{{.State.Status}}' "$SHINOBI_CONTAINER" 2>/dev/null)
  [ "$status" = "running" ] && break
  if [ $waited -ge $MAX_WAIT ]; then
    echo "[docker] Timeout: Shinobi container did not start within ${MAX_WAIT}s. Aborting."
    exit 1
  fi
  echo "[docker] Waiting for Shinobi container... (${waited}s)"
  sleep $interval; waited=$((waited + interval))
done
echo "[docker] Shinobi container is running."
```

**start.bat pattern** (batch): equivalent loop using `docker inspect` + `findstr "running"` + `timeout /t 5`.

## Complexity Tracking

No constitution violations. No complexity justification required.
