# Data Model: Git Updates, Branch Switcher & App Stability

**Date**: 2026-10-01 | **Feature**: 003-git-updates-stability

All state for this feature is **in-memory** (no database tables). The SQLite database (`shinobi_index.db`) is not modified by this feature.

---

## Entities

### AppState (supervisor in-memory)

Held by the supervisor process. Reset on supervisor restart.

| Field | Type | Description |
|-------|------|-------------|
| `status` | `Enum` | One of: `running`, `starting`, `restarting`, `crash_capped` |
| `current_branch` | `str` | Output of `git rev-parse --abbrev-ref HEAD` at startup |
| `crash_count` | `int` | Number of crashes in the current 2-minute window |
| `crash_window_start` | `datetime \| None` | Start of the current crash-counting window; `None` if no crashes yet |
| `last_crash_at` | `datetime \| None` | Timestamp of the most recent crash |
| `last_crash_reason` | `str \| None` | Exit code / stderr snippet from the most recent crash |
| `pending_operation` | `Enum \| None` | One of: `None`, `update`, `switch`; used for mutual-exclusion lock (FR-010) |

**State transitions**:
```
starting → running           (uvicorn starts successfully)
running  → restarting        (crash detected, cap not hit)
running  → crash_capped      (crash count >= 5 in window)
restarting → running         (restart succeeds)
restarting → crash_capped    (cap hit during restart attempt)
crash_capped → starting      (operator clicks "Reiniciar App" → POST /api/restart)
running → starting           (exit code 42: intentional restart after update/switch)
```

---

### UpdateResult (transient, returned by API)

Returned by `POST /api/admin/git/update`. Not persisted.

| Field | Type | Description |
|-------|------|-------------|
| `status` | `Enum` | One of: `success`, `up_to_date`, `failed` |
| `summary` | `str` | Human-readable result (e.g., git output or error message) |
| `timestamp` | `datetime` | When the operation completed |

---

### BranchInfo (transient, returned by API)

Each item in the list returned by `GET /api/admin/git/branches`.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Branch name (remote refs stripped of `remotes/origin/` prefix) |
| `is_current` | `bool` | True if this is the currently checked-out branch |
| `is_local` | `bool` | True if the branch exists locally |
| `is_remote` | `bool` | True if the branch exists on the remote (as a remote-tracking ref) |

---

### SwitchRequest (API input)

Body of `POST /api/admin/git/switch`.

| Field | Type | Validation |
|-------|------|-----------|
| `branch` | `str` | Required; must match a name from `BranchInfo.name`; max 200 chars |

---

### CrashEvent (in-memory log, supervisor)

The supervisor keeps a bounded rolling log (last 20 entries) for display on the status page.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | When the crash occurred |
| `exit_code` | `int` | The process exit code |
| `reason` | `str` | stderr excerpt (truncated to 500 chars) |
| `restarted` | `bool` | Whether the supervisor attempted a restart after this event |

---

## Crash-Cap Algorithm

```
CRASH_LIMIT = 5
CRASH_WINDOW_SECONDS = 120
BACKOFF_SECONDS = 2

on_process_exit(exit_code):
  if exit_code == 42:
    reset crash_count to 0
    reset crash_window_start to None
    restart immediately
    return

  if exit_code == 0 or exit_code == -SIGTERM:
    restart immediately
    return

  # Unclean exit — crash
  now = datetime.utcnow()
  if crash_window_start is None or (now - crash_window_start).seconds > CRASH_WINDOW_SECONDS:
    crash_window_start = now
    crash_count = 0
  crash_count += 1

  if crash_count >= CRASH_LIMIT:
    set status = crash_capped
    stop restarting
  else:
    sleep BACKOFF_SECONDS
    restart
```
