# API Contracts: Shinobi Light Viewer

**Date**: 2026-09-25 | **Plan**: [../plan.md](../plan.md) | **Data Model**: [../data-model.md](../data-model.md)

Base URL: `http://localhost:{PORT}/api`

All request/response bodies are JSON. All timestamps are Unix epoch **milliseconds** (integer).

---

## Monitors

### `GET /api/monitors`

List all monitors discovered by the indexer.

**Response 200**:
```json
[
  {
    "id": 1,
    "group_key": "abc123",
    "monitor_id": "cam01",
    "display_name": "abc123/cam01",
    "first_seen_at": 1727200000000,
    "last_seen_at": 1727286400000
  }
]
```

---

## Video Chunks

### `GET /api/monitors/{monitor_id}/chunks?from_ts={ms}&to_ts={ms}`

Query indexed chunks for a monitor within a time range. Returns only chunks whose intervals overlap `[from_ts, to_ts]`.

**Path params**: `monitor_id` — integer (monitors.id)
**Query params**: `from_ts`, `to_ts` — Unix milliseconds (both required)

**Response 200**:
```json
[
  {
    "id": 42,
    "monitor_id": 1,
    "file_path": "/mnt/hdd/ShinobiVideos/abc123/cam01/2026-09-25/20260925T080000.mp4",
    "start_ts": 1727251200000,
    "end_ts": 1727254800000,
    "duration_ms": 3600000,
    "file_size_bytes": 1073741824,
    "availability": "available"
  }
]
```

**Response 404**: Monitor not found.

---

## Jobs

### `POST /api/jobs/export`

Request a lossless merged clip export.

**Request body**:
```json
{
  "monitor_id": 1,
  "from_ts": 1727251200000,
  "to_ts": 1727254800000
}
```

**Response 202** (accepted):
```json
{ "status": "running", "type": "export" }
```

**Response 409** (job already running):
```json
{ "detail": "A job is already in progress. Cancel it or wait for it to complete." }
```

**Response 422** (no chunks in range):
```json
{ "detail": "No available clips found in the selected time range." }
```

**Response 507** (insufficient SSD space):
```json
{ "detail": "Insufficient disk space on SSD. Estimated {X} MB required, {Y} MB available." }
```

---

### `POST /api/jobs/timelapse`

Request an accelerated timelapse preview.

**Request body**:
```json
{
  "monitor_id": 1,
  "from_ts": 1727222400000,
  "to_ts": 1727251200000
}
```

Speed factor is computed server-side to target a ~60-second output (SC-004).

**Response 202**: Same shape as export.
**Response 409**, **422**, **507**: Same as export.

---

### `GET /api/jobs/current`

Poll the status and progress of the active job.

**Response 200**:
```json
{
  "status": "running",
  "type": "export",
  "progress": 0.47,
  "download_token": null,
  "error": null
}
```

When `status` is `"done"`:
```json
{
  "status": "done",
  "type": "export",
  "progress": 1.0,
  "download_token": "abc123xyz...",
  "error": null
}
```

When `status` is `"idle"`: returns `{ "status": "idle" }`.

---

### `DELETE /api/jobs/current`

Cancel the active job. Kills the FFmpeg process and removes any partial output file.

**Response 200**:
```json
{ "status": "cancelled" }
```

**Response 404** (no active job):
```json
{ "detail": "No job is currently running." }
```

---

## Downloads

### `GET /api/downloads/{token}`

Serve and consume a one-time download token. Streams the output file and deletes it from SSD after delivery.

**Response 200**: Binary MP4 stream with `Content-Type: video/mp4` and `Content-Disposition: attachment`.

**Response 404**: Token not found or already consumed.

---

## Indexer Status

### `GET /api/indexer/status`

Return the current state of the background indexer.

**Response 200**:
```json
{
  "last_scan_at": 1727286400000,
  "next_scan_in_seconds": 42,
  "total_monitors": 3,
  "total_chunks": 10247,
  "unavailable_chunks": 12
}
```
