# Quickstart Validation Guide: Shinobi Light Viewer

**Date**: 2026-09-25 | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/api.md](contracts/api.md)

This guide documents how to validate the feature end-to-end once implemented. It covers prerequisites, setup, and verification of each acceptance scenario from the spec.

---

## Prerequisites

- Python 3.10+ installed, with a virtual environment set up (`backend/.venv`)
- FFmpeg installed and on `PATH` (`ffmpeg -version` must succeed)
- A directory of `.mp4` footage files in Shinobi's layout:
  - `GroupKey/MonitorID/YYYY-MM-DD/filename.mp4` (date dir optional)
  - At least 2 monitors with clips overlapping a common time window (for multi-camera grid testing)
- Local SSD with at least 5 GB free

---

## Setup

```bash
# Activate virtualenv and install dependencies
cd backend
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: set FOOTAGE_DIR, DB_PATH, CACHE_DIR, PORT (see plan.md for Windows paths)

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8090

# Open the UI
# Browser: http://localhost:8090
```

---

## Scenario 1 — Indexer Startup Scan (FR-001, FR-004)

**Verify**: On launch the indexer scans immediately and populates the database.

```bash
curl http://localhost:8090/api/indexer/status
# Expected: last_scan_at is set, total_chunks > 0, total_monitors >= 1
```

Wait 60 seconds, re-run — `last_scan_at` should update (periodic scan confirmed, FR-004).

---

## Scenario 2 — Camera List (FR-005, FR-007)

**Verify**: All monitors from the HDD appear in the sidebar.

```bash
curl http://localhost:8090/api/monitors
# Expected: array with one object per GroupKey/MonitorID combination found on HDD
```

**UI check**: Open `http://localhost:8090` → sidebar lists each camera with a toggle.

---

## Scenario 3 — Grid Assembly (US1, FR-008, SC-001)

**Verify**: Selecting cameras builds the correct grid layout, loads in < 3 seconds.

1. Open the viewer.
2. Set a date and time range that has footage for at least 2 cameras.
3. Activate 1 camera → grid shows 1×1 cell.
4. Activate a second → grid reorganizes to 1×2.
5. Continue to 4 cameras → grid becomes 2×2.
6. Activate up to 9 cameras → grid is 3×3, all 9 toggles active.
7. Try to activate a 10th → toggle is disabled (FR-008 cap).

**Timing**: From clicking "Confirm period" to video playing in all cells — must be under 3 seconds (SC-001).

---

## Scenario 4 — Range Request Streaming (FR-006b)

**Verify**: The browser can seek within a video file without downloading it entirely.

```bash
# Get a chunk ID from the API
curl "http://localhost:8090/api/monitors/1/chunks?from_ts=1727251200000&to_ts=1727254800000"
# Note the "id" of the first chunk

# Simulate a browser range request
curl -i -H "Range: bytes=0-1048575" http://localhost:8090/api/video/42
# Expected: HTTP/1.1 206 Partial Content
#           Accept-Ranges: bytes
#           Content-Range: bytes 0-1048575/<total_size>

# Full request (no Range header) — should also return Accept-Ranges
curl -i http://localhost:8090/api/video/42
# Expected: HTTP/1.1 200 OK
#           Accept-Ranges: bytes
```

**UI check**: In the grid, scrub to a midpoint in a cell — video jumps to that position without reloading (confirms 206 seeking works).

---

## Scenario 5 — Multi-Video Synchronization (FR-009)

**Verify**: All grid cells display the same virtual timestamp simultaneously.

1. With 4+ cameras in the grid, press Play.
2. Watch for a recognizable event visible in at least 2 cameras (e.g., motion, lighting change).
3. Pause — all cells should freeze at the same moment within 50 ms tolerance.
4. Use the scrubber to seek to a specific time — all cells jump to that instant together.

---

## Scenario 6 — Speed Selector (FR-010b)

**Verify**: Playback rate changes apply to all cells simultaneously.

1. Grid playing at default 8×.
2. Click the 1× speed button — playback slows to real-time across all cells.
3. Click 16× — playback visibly accelerates across all cells.
4. Confirm the speed selector shows the active value highlighted.

---

## Scenario 7 — Spinner on Load (FR-010c)

**Verify**: Each cell shows a spinner while buffering, then disappears when ready.

1. Select a period and activate 4+ cameras.
2. Immediately after clicking confirm — each cell should show a centered spinner with the camera name above it on a dark background.
3. As each cell finishes loading, its spinner disappears and video starts playing automatically.

---

## Scenario 8 — Dual-Handle Scrubber (US2, FR-010, FR-011, FR-012)

**Verify**: Scrubber handles constrain each other and seek all cells.

1. With the grid active, the scrubber shows the full period. Start handle is at 0%, end handle at 100%.
2. Drag the start handle to 25% → zone to the left darkens; grid jumps to the 25% timestamp in all cells.
3. Drag the end handle to 75% → zone to the right darkens; grid jumps to the 75% timestamp.
4. Attempt to drag start handle past the end handle → it stops at `end - 1 second` (handles never cross).
5. Click inside the highlighted zone → grid seeks to the clicked position.

---

## Scenario 9 — Bounded Playback (US2, scenario 5)

**Verify**: Play stops at the end handle position.

1. Set start handle to 10%, end handle to 30%.
2. Press Play — playback begins from the start handle position.
3. When the virtual time reaches the end handle, playback pauses automatically.

---

## Scenario 10 — Export Selected Range (US3, FR-013, SC-003)

**Verify**: Export produces one file per active camera, covering exactly the scrubber range.

```bash
# Via API (equivalent to UI clicking Export with 2 cameras active)
curl -X POST http://localhost:8090/api/jobs/export \
  -H "Content-Type: application/json" \
  -d '{"monitor_ids": [1, 2], "from_ts": 1727251200000, "to_ts": 1727254800000}'
# Expected: 202 {"status": "running", "type": "export", "cameras": [...]}

# Poll progress
curl http://localhost:8090/api/jobs/current
# Expected: progress increases 0.0 → 1.0 across polling; both cameras tracked

# When done, each camera has a download_token
curl http://localhost:8090/api/jobs/current
# Expected: {"status":"done","cameras":[{"monitor_id":1,"download_token":"tok_abc"},{"monitor_id":2,"download_token":"tok_def"}]}

# Download camera 1
curl -o cam01.mp4 http://localhost:8090/api/downloads/tok_abc
# Download camera 2
curl -o cam02.mp4 http://localhost:8090/api/downloads/tok_def

# Verify durations
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 cam01.mp4
# Expected: ~3600.0 (if 1-hour range selected)
```

**SC-003 check**: A 1-hour range across 4 cameras must complete and be available for download in under 5 minutes.

---

## Scenario 11 — Conflict Rejection (FR-015)

**Verify**: A second export request while one is running returns 409.

```bash
curl -X POST http://localhost:8090/api/jobs/export -H "Content-Type: application/json" \
  -d '{"monitor_ids":[1],"from_ts":1727251200000,"to_ts":1727254800000}'

# Immediately submit another
curl -X POST http://localhost:8090/api/jobs/export -H "Content-Type: application/json" \
  -d '{"monitor_ids":[2],"from_ts":1727251200000,"to_ts":1727254800000}'
# Expected: 409
```

**UI check**: While export is running, the Export button, camera toggles, and scrubber handles are all disabled (FR-016).

---

## Scenario 12 — Camera Without Footage (FR-020)

**Verify**: A camera with no clips in the selected period shows "Sin footage" and is excluded from export.

1. Select a time period where camera A has clips but camera B does not.
2. Activate both cameras.
3. Camera A cell plays normally; camera B cell shows "Sin footage" message.
4. Submit export — only camera A produces a file.

---

## Scenario 13 — Disk Space Pre-Check (FR-014)

**Verify**: Export rejected before starting when SSD has insufficient space.

Simulate by setting `CACHE_DIR` to a near-full filesystem, then submit an export. Expected: 507 response with a clear message; no partial file is written to the SSD.

---

## Scenario 14 — mtime Guard (FR-002)

**Verify**: Files modified within 60 seconds are not indexed.

```bash
# Touch a file to simulate an active write by Shinobi
touch /path/to/footage/GroupKey/MonitorID/active_clip.mp4

# Trigger scan or wait for 60s cycle
curl http://localhost:8090/api/indexer/status

# Query chunks — the touched file must NOT appear
curl "http://localhost:8090/api/monitors/1/chunks?from_ts=...&to_ts=..."
# It should appear in the next scan after 60 seconds have passed since the touch
```

---

## Scenario 15 — Unavailable Chunk Handling (FR-020)

**Verify**: Chunks whose files were deleted from HDD are marked unavailable.

```bash
# Delete a file
rm /path/to/footage/GroupKey/MonitorID/2026-09-25/clip.mp4

# Wait for next scan (up to 60s)
curl "http://localhost:8090/api/monitors/1/chunks?from_ts=...&to_ts=..."
# Expected: affected chunk shows "availability": "unavailable"
```

**UI check**: The affected segment in the cell shows as grayed-out; dragging the scrubber over it still works but the chunk is skipped in any export.
