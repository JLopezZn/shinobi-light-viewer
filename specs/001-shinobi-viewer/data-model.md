# Data Model: Shinobi Light Viewer

**Date**: 2026-09-25 | **Plan**: [plan.md](plan.md)

All data resides in a single SQLite database (`shinobi_index.db`) on the local SSD. The external HDD is never written to.

---

## Entity: Monitor

Represents a single Shinobi camera, identified by its `GroupKey` + `MonitorID` path components.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal surrogate key |
| `group_key` | TEXT | NOT NULL | Shinobi group key (directory level 1) |
| `monitor_id` | TEXT | NOT NULL | Shinobi monitor ID (directory level 2) |
| `display_name` | TEXT | NOT NULL | Human-readable label (`{group_key}/{monitor_id}`) |
| `first_seen_at` | INTEGER | NOT NULL | Unix timestamp (ms) of first scan that discovered this monitor |
| `last_seen_at` | INTEGER | NOT NULL | Unix timestamp (ms) of last scan that confirmed this monitor has clips |

**Uniqueness**: `UNIQUE(group_key, monitor_id)`

---

## Entity: VideoChunk

Represents a single recorded `.mp4` file on the external HDD.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal surrogate key |
| `monitor_id` | INTEGER | NOT NULL, FK → monitors.id | Owning monitor |
| `file_path` | TEXT | NOT NULL, UNIQUE | Absolute path to `.mp4` on HDD |
| `start_ts` | INTEGER | NOT NULL | Recording start — Unix timestamp (milliseconds) |
| `end_ts` | INTEGER | NOT NULL | Recording end — Unix timestamp (milliseconds) |
| `duration_ms` | INTEGER | NOT NULL | `end_ts - start_ts` in milliseconds |
| `file_size_bytes` | INTEGER | NOT NULL | File size at index time |
| `availability` | TEXT | NOT NULL, DEFAULT `'available'` | `'available'` or `'unavailable'` |
| `indexed_at` | INTEGER | NOT NULL | Unix timestamp (ms) of first index |
| `last_verified_at` | INTEGER | NOT NULL | Unix timestamp (ms) of last scan that confirmed file exists |

**Indexes**:
- `idx_chunks_monitor_time` on `(monitor_id, start_ts, end_ts)` — primary query path for timeline and export range lookups

**Availability state transitions**:
- `available` → `unavailable`: file no longer found on HDD during scan
- `unavailable` → `available`: file reappears during scan (re-index scenario)

---

## In-Memory: JobState

Jobs are not persisted to SQLite. A single module-level object tracks the active export job for the lifetime of the process.

| Field | Type | Description |
|-------|------|-------------|
| `status` | str | `'idle'` / `'running'` / `'done'` / `'cancelled'` / `'failed'` |
| `type` | str \| None | Always `'export'` when set (timelapse is client-side only) |
| `progress` | float | 0.0–1.0 — minimum progress across all active FFmpeg processes (slowest camera drives the indicator) |
| `cameras` | list[CameraExportState] | Per-camera output state (see below) |
| `error` | str \| None | Error message if status is `'failed'` |

### Sub-object: CameraExportState

Tracks the state of one FFmpeg process within the job.

| Field | Type | Description |
|-------|------|-------------|
| `monitor_id` | int | monitors.id of the camera being exported |
| `display_name` | str | Human-readable camera label |
| `proc` | asyncio.Process \| None | Active FFmpeg subprocess handle |
| `output_path` | Path \| None | Temp output `.mp4` on SSD (deleted after token consumed) |
| `progress` | float | 0.0–1.0 for this camera's FFmpeg process |
| `download_token` | str \| None | Single-use UUID token issued when this camera's process finishes |

**Lifecycle**:
```
idle → running → done | failed | cancelled → idle
```
Reset to `idle` after all tokens are consumed or on next job submission.

---

## UI Concepts (frontend-only, not stored)

### GridCell

Runtime state for a single camera cell in the grid. Held in JavaScript memory only.

| Field | Type | Description |
|-------|------|-------------|
| `monitorId` | number | monitors.id |
| `displayName` | string | Label shown above cell |
| `chunks` | Chunk[] | Sorted array of chunks for the current period |
| `activeChunk` | Chunk \| null | The chunk currently loaded in `<video>` |
| `videoEl` | HTMLVideoElement | The DOM element for this cell |
| `buffering` | boolean | Whether the spinner is visible |

### ScrubRange

The pair of timestamps defined by the dual scrubber handles.

| Field | Type | Description |
|-------|------|-------------|
| `startMs` | number | Unix ms — position of the left handle |
| `endMs` | number | Unix ms — position of the right handle |

Constraint: `startMs < endMs` always enforced; minimum gap is 1 second (1000 ms).

---

## SQLite Schema (DDL)

```sql
CREATE TABLE IF NOT EXISTS monitors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    group_key     TEXT    NOT NULL,
    monitor_id    TEXT    NOT NULL,
    display_name  TEXT    NOT NULL,
    first_seen_at INTEGER NOT NULL,
    last_seen_at  INTEGER NOT NULL,
    UNIQUE(group_key, monitor_id)
);

CREATE TABLE IF NOT EXISTS video_chunks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id       INTEGER NOT NULL REFERENCES monitors(id),
    file_path        TEXT    NOT NULL UNIQUE,
    start_ts         INTEGER NOT NULL,
    end_ts           INTEGER NOT NULL,
    duration_ms      INTEGER NOT NULL,
    file_size_bytes  INTEGER NOT NULL,
    availability     TEXT    NOT NULL DEFAULT 'available',
    indexed_at       INTEGER NOT NULL,
    last_verified_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_monitor_time
    ON video_chunks(monitor_id, start_ts, end_ts);
```
