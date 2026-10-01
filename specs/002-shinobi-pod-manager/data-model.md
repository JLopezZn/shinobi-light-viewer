# Data Model: Shinobi Pod Manager

**Feature**: `002-shinobi-pod-manager` | **Date**: 2026-09-27

## Overview

This feature introduces no persistent data entities — it operates on ephemeral runtime state (container status) and transient configuration (env vars). There is no new database table or schema migration.

---

## Runtime State: ContainerStatus

Represents the current state of the Shinobi Docker container as reported by the Docker daemon.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `status` | string (enum) | `running`, `stopped`, `unknown` | Normalized state exposed to the frontend. `unknown` when Docker is unavailable or the container does not exist. |
| `container` | string | e.g. `"shinobi"` | The configured container name, echoed back for UI confirmation. |
| `raw_status` | string (optional) | Docker inspect output | Raw Docker state string (e.g. `"exited"`, `"paused"`, `"created"`). Mapped to the normalized `status` above. For internal use / debugging. Not required in the API response. |

### Status Mapping

| Docker raw state | Normalized status |
|-----------------|-------------------|
| `running` | `running` |
| `exited` | `stopped` |
| `paused` | `stopped` |
| `created` | `stopped` |
| `restarting` | `running` (transitional) |
| Docker unavailable / container not found | `unknown` |

---

## Configuration (Environment Variables)

New variables added to `.env.example` and `Settings`:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SHINOBI_CONTAINER` | string | `shinobi` | Name or ID of the Docker container running Shinobi |
| `ADMIN_TOKEN` | string | *(required — no default)* | Secret token required in `X-Admin-Token` header to access admin endpoints |

### Validation Rules

- `SHINOBI_CONTAINER`: Must be a non-empty string. No whitespace. Validated at startup.
- `ADMIN_TOKEN`: Must be a non-empty string. If absent or empty, the server must refuse to start (to prevent accidentally running with an open admin surface).

---

## Operation Result

Returned by start / stop / restart endpoints after the operation completes.

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Final normalized container state (`running`, `stopped`, `unknown`) |
| `container` | string | Configured container name |
| `message` | string (optional) | Human-readable description, used for errors or edge cases (e.g. "Container was already stopped") |

---

## No Persistent Storage Changes

- No new SQLite tables
- No schema migrations
- No changes to `shinobi_index.db`
- All state is transient (queried live from Docker daemon on each request)
