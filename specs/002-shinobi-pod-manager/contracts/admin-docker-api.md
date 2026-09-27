# API Contract: Admin Docker Management

**Feature**: `002-shinobi-pod-manager` | **Date**: 2026-09-27  
**Base path**: `/api/admin/docker`  
**Auth**: All endpoints require header `X-Admin-Token: <token>` matching the `ADMIN_TOKEN` env var.

---

## Authentication

All endpoints under `/api/admin/` require:

```
X-Admin-Token: <configured-token>
```

**On missing/invalid token:**
```json
HTTP 401 Unauthorized
{"detail": "Unauthorized"}
```

---

## GET /api/admin/docker/status

Returns the current state of the Shinobi container. Used by the frontend polling loop.

**Request**: No body.

**Response 200 OK**:
```json
{
  "status": "running",
  "container": "shinobi"
}
```

**Response 200 OK** (Docker unavailable or container not found):
```json
{
  "status": "unknown",
  "container": "shinobi",
  "message": "Container not found or Docker is unavailable"
}
```

**Status values**: `"running"` | `"stopped"` | `"unknown"`

---

## POST /api/admin/docker/start

Starts the Shinobi container. If already running, returns current state without error.

**Request**: No body.

**Response 200 OK** (started or already running):
```json
{
  "status": "running",
  "container": "shinobi"
}
```

**Response 200 OK** (already running):
```json
{
  "status": "running",
  "container": "shinobi",
  "message": "Container was already running"
}
```

**Response 500 Internal Server Error** (Docker failed):
```json
{
  "detail": "Failed to start container: <docker error output>"
}
```

---

## POST /api/admin/docker/stop

Stops the Shinobi container. If already stopped, returns current state without error.

**Request**: No body.

**Response 200 OK** (stopped or already stopped):
```json
{
  "status": "stopped",
  "container": "shinobi"
}
```

**Response 200 OK** (already stopped):
```json
{
  "status": "stopped",
  "container": "shinobi",
  "message": "Container was already stopped"
}
```

**Response 500 Internal Server Error** (Docker failed):
```json
{
  "detail": "Failed to stop container: <docker error output>"
}
```

---

## POST /api/admin/docker/restart

Stops then starts the Shinobi container. Aborts if the stop step fails.

**Request**: No body.

**Response 200 OK**:
```json
{
  "status": "running",
  "container": "shinobi"
}
```

**Response 500 Internal Server Error** (stop phase failed):
```json
{
  "detail": "Restart aborted: failed to stop container: <docker error output>"
}
```

**Response 500 Internal Server Error** (start phase failed):
```json
{
  "detail": "Restart aborted: container stopped but failed to start: <docker error output>"
}
```

---

## Existing Admin Endpoint (retrofitted)

### DELETE /api/admin/db

Previously unauthenticated. **Now requires** `X-Admin-Token` header (same token).  
Behavior unchanged: clears all indexed monitors and video chunks.

**Response 401**: Token missing or invalid (new behavior).  
**Response 200/409**: Same as before.

---

## Error Handling Summary

| Scenario | HTTP Status | `detail` message |
|----------|-------------|-----------------|
| Missing/invalid token | 401 | `"Unauthorized"` |
| Docker not installed / daemon not running | 200 (`status: unknown`) for status; 500 for actions |
| Container name not found | 200 (`status: unknown`) for status; 500 for actions |
| Operation already in desired state | 200 with `message` field |
| Unexpected subprocess error | 500 | `"<operation> failed: <stderr>"` |
