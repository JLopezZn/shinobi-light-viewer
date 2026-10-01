# Research: Git Updates, Branch Switcher & App Stability

**Date**: 2026-10-01 | **Feature**: 003-git-updates-stability

All unknowns resolved from codebase inspection and established patterns. No external research agents required.

---

## Decision 1: Process Supervisor Architecture

**Decision**: Python supervisor script (`supervisor/supervisor.py`) launched by updated `start.sh`/`start.bat`. The supervisor spawns uvicorn as a subprocess, monitors exit codes, implements crash-cap logic, and hosts a status HTTP server on a secondary port.

**Rationale**: The existing start scripts use `exec uvicorn` with no restart logic. A Python supervisor is cross-platform (works for both `.sh` and `.bat`), can host the status server in a thread alongside the watchdog loop, and avoids introducing a new OS-level dependency (systemd, pm2, supervisor daemon, etc.). The stdlib `subprocess` + `http.server` + `threading` modules are sufficient — no new dependencies.

**Alternatives considered**:
- **Shell loop in start.sh**: Cannot host the status server (no Python HTTP server in bash). Windows `.bat` equivalent is cumbersome. Rejected.
- **systemd/pm2/supervisord**: External dependency, requires OS-level configuration, not portable to Windows. Rejected.
- **Asyncio supervisor**: Overly complex; a simple threading model is sufficient for one child process and one HTTP server. Rejected.

---

## Decision 2: Intentional-Restart Signal (Exit Code 42)

**Decision**: FastAPI admin endpoints that perform git operations exit the process with code 42. The supervisor treats code 42 as "intentional restart" — it restarts without incrementing the crash counter and without backoff delay.

**Rationale**: A dedicated exit code is the cleanest cross-platform IPC mechanism between the FastAPI process and its parent supervisor. It requires no shared files, pipes, or sockets. Code 42 is arbitrary but well outside the range of standard Python/OS exit codes (0, 1, 2) and uvicorn's codes.

**Alternatives considered**:
- **Signal-based IPC (SIGUSR1)**: Not available on Windows. Rejected.
- **Shared file flag**: Introduces a race condition between write and supervisor poll. Rejected.
- **HTTP call from app to supervisor**: Circular dependency; supervisor would need an extra server endpoint just for this. Rejected.

---

## Decision 3: Status Server Port

**Decision**: Status server runs on `$STATUS_PORT` (default: main port + 1, e.g., 8091 if main is 8090). Configurable via env var. No authentication on the status server.

**Rationale**: The status server's primary use case is emergency recovery when the main app is down — authentication would defeat the purpose. It is a local tool not exposed externally. Port offset (+1) avoids hard-coding and prevents conflicts when running multiple instances.

**Alternatives considered**:
- **Same port, different path prefix**: Impossible if the main app process is dead — the status server must be a completely independent process/thread. Rejected.
- **Fixed port 8081**: Risks conflict if the user runs other services. Rejected.

---

## Decision 4: Git Operations Location in Codebase

**Decision**: New `backend/app/services/git_manager.py` for git logic; new `backend/app/api/git_ops.py` router for the HTTP endpoints. Registered in `main.py` alongside existing routers.

**Rationale**: Consistent with the existing pattern (`docker_manager.py` service + `admin.py` router). Separation of concerns: the service is independently testable without HTTP; the router is thin.

**Alternatives considered**:
- **Inline in admin.py**: Existing `admin.py` already has Docker management. Git ops would bloat it. Rejected.
- **Supervisor-side HTTP endpoints for git ops**: Forces git API calls to go to a different port/server; the existing admin token auth in FastAPI cannot be reused. Rejected.

---

## Decision 5: Branch Switcher Remote Fetch

**Decision**: `GET /api/admin/git/branches` runs `git fetch --prune --quiet` before listing, then returns all branches including remote-tracking refs. A loading indicator is shown in the UI during the fetch.

**Rationale**: User story 3 acceptance scenario 1 and clarification Q4 require remote branches to be visible. Fetch-on-demand (only when the dropdown is opened) avoids unnecessary background network traffic.

**Alternatives considered**:
- **Periodic background fetch**: Adds complexity, fetches even when operator never opens the dropdown. Rejected.
- **Local-only listing**: Does not satisfy FR-007 or clarification Q4 answer. Rejected.

---

## Decision 6: Git Pull Conflict Handling

**Decision**: On any non-zero exit from `git pull`, immediately run `git reset --hard HEAD` to restore the repo to its pre-pull state, then return the git stderr as the error message to the operator.

**Rationale**: This is the safest recovery: no merge artifacts, no partial state, running version unchanged (clarification Q3: Option A). The operator has no git knowledge and cannot resolve conflicts from the terminal.

**Alternatives considered**:
- **Leave repo in conflicted state**: Operator cannot recover. Rejected.
- **Force-pull (reset to remote)**: Could discard intentional local commits. Rejected.
