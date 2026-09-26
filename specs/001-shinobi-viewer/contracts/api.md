# API Contracts: Shinobi Light Viewer

**Date**: 2026-09-25 | **Plan**: [../plan.md](../plan.md) | **Data Model**: [../data-model.md](../data-model.md)

Base URL: `http://localhost:{PORT}/api`

All request/response bodies are JSON unless noted. All timestamps are Unix epoch **milliseconds** (integer).

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

Query indexed chunks for a monitor within a time range. Returns only chunks whose intervals overlap `[from_ts, to_ts]`. Results are ordered by `start_ts` ascending.

**Path params**: `monitor_id` — integer (monitors.id)  
**Query params**: `from_ts`, `to_ts` — Unix milliseconds (both required)

**Response 200**:
```json
[
  {
    "id": 42,
    "monitor_id": 1,
    "file_path": "D:/ShinobiVideos/abc123/cam01/2026-09-25/20260925T080000.mp4",
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

## Video Streaming

### `GET /api/video/{chunk_id}`

Stream a video chunk from the HDD directly to the browser. Supports HTTP Range Requests so the browser `<video>` element can seek within the file without downloading it entirely.

**Path params**: `chunk_id` — integer (video_chunks.id)

**Request headers** (sent automatically by `<video>`):
```
Range: bytes=0-1048575
```

**Response 206** (partial — any request with a `Range` header):
```
HTTP/1.1 206 Partial Content
Accept-Ranges: bytes
Content-Type: video/mp4
Content-Length: 1048576
Content-Range: bytes 0-1048575/104857600
```
Body: binary chunk of the file.

**Response 200** (full — request without `Range` header):
```
HTTP/1.1 200 OK
Accept-Ranges: bytes
Content-Type: video/mp4
Content-Length: 104857600
```
Body: entire file streamed.

**Response 404**: Chunk not found in index.

**Response 410** (Gone): Chunk is marked `'unavailable'` — file no longer exists on HDD.

> Note: `Accept-Ranges: bytes` is always present in the response, even on 200. This header is required for the browser to enable seeking.

---

## Jobs

### `POST /api/jobs/export`

Request a lossless export for one or more cameras over a time range. Generates one `.mp4` per camera (N cameras → N files). The N FFmpeg processes run in parallel; progress is the slowest process.

**Request body**:
```json
{
  "monitor_ids": [1, 2, 3],
  "from_ts": 1727251200000,
  "to_ts": 1727254800000
}
```

**Constraints**:
- `monitor_ids` must be non-empty and contain only IDs of known monitors
- `from_ts` must be strictly less than `to_ts`

**Response 202** (accepted):
```json
{
  "status": "running",
  "type": "export",
  "cameras": [
    { "monitor_id": 1, "display_name": "abc123/cam01" },
    { "monitor_id": 2, "display_name": "abc123/cam02" },
    { "monitor_id": 3, "display_name": "abc123/cam03" }
  ]
}
```

**Response 409** (job already running):
```json
{ "detail": "A job is already in progress. Cancel it or wait for it to complete." }
```

**Response 422** (no chunks in range for all requested cameras):
```json
{ "detail": "No available clips found in the selected time range for any of the requested cameras." }
```

**Response 507** (insufficient SSD space):
```json
{ "detail": "Insufficient disk space on SSD. Estimated 1500 MB required, 800 MB available." }
```

---

### `GET /api/jobs/current`

Poll the status and progress of the active job.

**Response 200 — while running**:
```json
{
  "status": "running",
  "type": "export",
  "progress": 0.47,
  "cameras": [
    { "monitor_id": 1, "display_name": "abc123/cam01", "download_token": null },
    { "monitor_id": 2, "display_name": "abc123/cam02", "download_token": null }
  ],
  "error": null
}
```

**Response 200 — when done**:
```json
{
  "status": "done",
  "type": "export",
  "progress": 1.0,
  "cameras": [
    { "monitor_id": 1, "display_name": "abc123/cam01", "download_token": "tok_abc123..." },
    { "monitor_id": 2, "display_name": "abc123/cam02", "download_token": "tok_def456..." }
  ],
  "error": null
}
```

**Response 200 — when idle**:
```json
{ "status": "idle" }
```

**Response 200 — when failed**:
```json
{
  "status": "failed",
  "type": "export",
  "progress": 0.31,
  "cameras": [],
  "error": "FFmpeg process exited with code 1: ..."
}
```

---

### `DELETE /api/jobs/current`

Cancel the active job. Kills all FFmpeg processes and removes partial output files from SSD.

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

Serve and consume a one-time download token for a single camera's export file. Streams the `.mp4` and deletes it from SSD after delivery. Each camera in a completed export has its own token; call this endpoint once per camera.

**Response 200**: Binary MP4 stream.
```
Content-Type: video/mp4
Content-Disposition: attachment; filename="cam01_2026-09-25_08-00-00.mp4"
```

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
  "total_monitors": 4,
  "total_chunks": 10247,
  "unavailable_chunks": 12
}
```
