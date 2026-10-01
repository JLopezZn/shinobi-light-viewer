# Research: Shinobi Pod Manager

**Feature**: `002-shinobi-pod-manager` | **Date**: 2026-09-27

## Decision Log

---

### Docker Interaction Method

**Decision**: Use Python `subprocess` to call the `docker` CLI directly.

**Rationale**: The `docker` binary is available on both Docker Desktop (Windows) and Docker Engine (Linux) via PATH. It handles socket/pipe configuration internally, so no platform-specific socket path logic is needed in the app. Using the CLI avoids adding a new SDK dependency (`docker` Python package), which would require Docker socket permissions that differ between Windows named pipes and Linux Unix sockets.

**Alternatives considered**:
- Docker SDK for Python (`pip install docker`): Cleaner async API, but requires connecting to the Docker socket directly (`//./pipe/docker_engine` on Windows, `/var/run/docker.sock` on Linux). Cross-platform path management adds complexity. Rejected.
- Docker REST API via `httpx`: Same socket complexity as SDK without the abstraction benefit. Rejected.

---

### Admin Authentication Mechanism

**Decision**: HTTP header `X-Admin-Token` validated against a `ADMIN_TOKEN` environment variable, implemented as a FastAPI `Depends()` reusable dependency.

**Rationale**: The app currently has NO authentication on any admin endpoint (`DELETE /db` is fully open). A simple token in an env variable is appropriate for a single-operator home-network app. It requires no user database, no session storage, and no cookie management on the server. The frontend stores the token in `sessionStorage` and presents a token-entry prompt on first use.

**Alternatives considered**:
- HTTP Basic Auth: Requires browser dialog or manual header injection. Poor UX for the existing vanilla JS frontend. Rejected.
- Full session/cookie auth: Overkill for a single-operator home app. Requires server-side session store. Rejected.
- No auth (rely on network isolation): Violates the spec requirement (FR-001: admin-only access). Rejected.

**Side effect**: The existing `DELETE /db` endpoint must be retrofitted with the same token dependency for consistency. This is a prerequisite task within this feature.

---

### Frontend Polling Strategy

**Decision**: `setInterval` polling every 3 seconds while the admin panel section is in the DOM/visible. Clear interval when the panel is hidden or destroyed. During an active operation (start/stop/restart in progress), reduce to 1-second polling until state resolves.

**Rationale**: The existing frontend is Vanilla JS with no reactive framework. `setInterval` is the standard, dependency-free mechanism. 3 seconds balances responsiveness (user sees state changes quickly) with server load (minimal overhead for a local app). The polling endpoint is a lightweight `docker inspect` subprocess call — negligible cost on localhost.

**Alternatives considered**:
- WebSocket: Real-time, but requires server-side async event emission and adds WebSocket connection management. Disproportionate complexity for a local admin tool. Rejected.
- Server-Sent Events (SSE): Better than WebSocket for one-way updates, but still requires a persistent connection and streaming endpoint. Overkill for this use case. Rejected.
- Manual refresh button only: Does not meet FR-002 (automatic polling required). Rejected.

---

### Container Name Configuration

**Decision**: Add `SHINOBI_CONTAINER` as an environment variable loaded via the existing `Settings` class in `config.py`, with a default value of `"shinobi"`.

**Rationale**: Consistent with how all other configuration is handled in the project (env vars, `.env` file). Default of `"shinobi"` matches the typical Docker Compose service name used by Shinobi OSS deployments.

**Alternatives considered**:
- Separate config file (JSON/YAML): Adds file-management complexity for a single value. Rejected.
- Hardcoded: Violates FR-011. Rejected.

---

### Startup Script Pre-flight Strategy

**Decision**: Both `start.bat` and `start.sh` get a new section that polls `docker inspect --format={{.State.Status}} <SHINOBI_CONTAINER>` in a loop with 5-second sleep intervals, up to a maximum of 120 seconds (24 attempts). On timeout, print an error and exit with code 1 without launching uvicorn.

**Rationale**: `docker inspect` is available on both platforms and returns immediately with the container state. 5-second intervals are gentle on the system during cold start. 120 seconds covers Docker Desktop startup on Windows (which can take 60–90s). `SHINOBI_CONTAINER` value comes from the loaded `.env` file (already parsed in both scripts before this new section runs).

**Alternatives considered**:
- `docker ps | grep <name>`: Requires text parsing; brittle. Rejected.
- HTTP health check against Shinobi's web port: More accurate (ensures Shinobi is actually ready), but requires knowing Shinobi's port and adds network dependency. Over-specified for this stage. Noted as a future improvement.
- Separate health-check script: Unnecessary indirection for a simple loop. Rejected.

---

## No Unresolved Clarifications

All NEEDS CLARIFICATION items from Technical Context are resolved above.
