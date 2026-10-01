# Implementation Plan: Git Updates, Branch Switcher & App Stability

**Branch**: `003-git-updates-stability` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-git-updates-stability/spec.md`

## Summary

Add a Python process supervisor that wraps the uvicorn process, auto-restarts it on crash (capped at 5 crashes/2 min), and hosts a lightweight status server on a secondary port that stays alive when the main app is down. Add git operations service + admin API endpoints to the FastAPI app so the operator can pull updates and switch branches from the existing UI. Both update and branch-switch cause the app to exit with a reserved exit code; the supervisor detects that code and restarts cleanly without counting it as a crash.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: FastAPI 0.110, Uvicorn 0.28, `subprocess` (stdlib) for git and child-process management, `http.server` (stdlib) for the status server

**Storage**: SQLite on local SSD (existing) — no new storage; supervisor state is in-memory

**Testing**: pytest + pytest-asyncio (existing)

**Target Platform**: Windows (start.bat) + Linux/macOS (start.sh) — both must be updated

**Project Type**: Web application — FastAPI backend + Vanilla JS frontend (existing structure maintained)

**Performance Goals**: Crash recovery within 10 s (SC-001); update/branch-switch completes within 30 s (SC-002, SC-003)

**Constraints**: Must not touch `FOOTAGE_DIR` or any Shinobi files; all git ops run in repo root only

**Scale/Scope**: Single operator; no concurrency concerns beyond the mutual-exclusion lock on update vs. switch operations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Zero Interference with Shinobi | ✅ PASS | Git operations target repo root only; `FOOTAGE_DIR` is never touched |
| Concurrent Read/Write Safety | ✅ PASS | Feature does not interact with the indexer or video files |
| Decoupled Metadata Storage | ✅ PASS | No new writes to external HDD; supervisor state is in-memory only |

## Project Structure

### Documentation (this feature)

```text
specs/003-git-updates-stability/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── admin-git-api.md     # Main app git endpoints contract
│   └── status-server-api.md # Supervisor status server contract
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
supervisor/
├── __init__.py
├── supervisor.py        # NEW: process watchdog + crash-cap logic + status server host
└── status_server.py     # NEW: minimal HTTP server (stdlib) for /status page + /api/restart

backend/app/
├── api/
│   ├── admin.py         # EXISTING: extend with git operation endpoints
│   └── git_ops.py       # NEW: router for /api/admin/git/* endpoints
├── services/
│   └── git_manager.py   # NEW: git pull, branch list, checkout via subprocess
└── main.py              # EXISTING: register git_ops router

frontend/
├── index.html           # EXISTING: add update + branch switcher UI elements to sidebar
└── app.js               # EXISTING: add update/switch JS logic

start.sh                 # EXISTING: updated to launch supervisor.py instead of uvicorn directly
start.bat                # EXISTING: same
```

**Structure Decision**: Web application layout (Option 2) is already in use. All new backend code follows the existing `backend/app/api` + `backend/app/services` pattern. The supervisor lives at the repo root under `supervisor/` since it orchestrates the entire app (not just the FastAPI layer).

## Complexity Tracking

No constitution violations — section not required.

## Supervisor Design

The supervisor is the new process entry point launched by `start.sh`/`start.bat`:

```
start.sh / start.bat
  └── python supervisor/supervisor.py
        ├── Thread 1: Status HTTP server (port 8091 by default, configurable via STATUS_PORT env)
        │     GET  /          → HTML status page
        │     GET  /api/status → JSON: { state, branch, crash_count, last_crash }
        │     POST /api/restart → manual restart (no-op unless crash-capped)
        └── Thread 2: Watchdog loop
              spawn: uvicorn app.main:app --port $PORT
              on exit 0 or SIGTERM  → restart (not a crash)
              on exit 42            → restart immediately, reset crash counter (intentional restart)
              on other exit code    → crash: increment counter
                if counter < 5 within 2-min window → restart after 2 s backoff
                if counter >= 5                     → enter crash-capped state, stop restarting
```

Exit code 42 is the **intentional-restart signal**: the FastAPI app exits with this code after a successful git pull or branch switch, telling the supervisor "restart me now, this is not a crash."

## Git Operations Design

All git operations run via `subprocess.run(["git", ...], cwd=REPO_ROOT, capture_output=True)`:

| Operation | Command | On conflict/error |
|-----------|---------|------------------|
| Pull update | `git pull` | If exit non-zero: `git reset --hard HEAD` then return error detail |
| List branches | `git fetch --prune --quiet && git branch -a` | If fetch fails: return cached local list with warning |
| Switch branch | `git checkout <branch>` | If exit non-zero: revert to prior branch, return error detail |
