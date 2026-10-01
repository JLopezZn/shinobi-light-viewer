# Contract: Supervisor Status Server

**Server**: Lightweight HTTP server hosted by the supervisor process
**Port**: `$STATUS_PORT` (default: `$PORT + 1`, e.g., 8091 if main app is on 8090)
**Auth**: None — intentionally unauthenticated; local-only emergency recovery tool
**Always available**: This server runs in the supervisor process and stays up even when the main app is down

---

## GET /

Returns an HTML status page. This is the human-readable view the operator sees when the main app is unreachable.

**Response 200** — HTML page containing:
- Current app state (`running` / `starting` / `restarting` / `crash_capped`)
- Current branch name
- Crash count in current window (if any)
- Recent crash log (last 5 events: timestamp, exit code, reason)
- "Reiniciar App" button — **visible and enabled only when state is `crash_capped`**

---

## GET /api/status

Returns the current supervisor state as JSON.

**Response 200**:
```json
{
  "state": "running",
  "branch": "003-git-updates-stability",
  "crash_count": 0,
  "crash_window_start": null,
  "last_crash_at": null,
  "last_crash_reason": null,
  "pending_operation": null,
  "recent_crashes": []
}
```

**Example — crash-capped state**:
```json
{
  "state": "crash_capped",
  "branch": "003-git-updates-stability",
  "crash_count": 5,
  "crash_window_start": "2026-10-01T14:32:10Z",
  "last_crash_at": "2026-10-01T14:33:58Z",
  "last_crash_reason": "Traceback (most recent call last):\n  ...\nValueError: FOOTAGE_DIR does not exist",
  "pending_operation": null,
  "recent_crashes": [
    { "timestamp": "2026-10-01T14:33:58Z", "exit_code": 1, "reason": "ValueError: ...", "restarted": false },
    { "timestamp": "2026-10-01T14:33:45Z", "exit_code": 1, "reason": "ValueError: ...", "restarted": true }
  ]
}
```

---

## POST /api/restart

Triggers a manual restart. Only effective when state is `crash_capped`. Resets the crash counter and starts the app process.

**Request body**: none

**Response 200 — restart triggered**:
```json
{ "status": "restarting" }
```

**Response 200 — no-op** (app is not crash-capped):
```json
{ "status": "already_running" }
```
