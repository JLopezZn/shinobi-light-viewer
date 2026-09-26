# Quickstart Validation Guide: Shinobi Light Viewer

**Date**: 2026-09-25 | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/api.md](contracts/api.md)

This guide documents how to validate the feature end-to-end once implemented. It covers prerequisites, setup, and verification of each acceptance scenario from the spec.

---

## Prerequisites

- Python 3.10+ installed
- FFmpeg installed and on `PATH` (`ffmpeg -version` must succeed)
- A directory of `.mp4` footage files in Shinobi's layout (`GroupKey/MonitorID/YYYY-MM-DD/filename.mp4`) — use real footage or a synthetic set for testing
- Local SSD with at least 5 GB free

---

## Setup

```bash
# Install backend dependencies
cd backend
pip install -r requirements.txt

# Configure (copy and edit)
cp .env.example .env
# Set: FOOTAGE_DIR=/path/to/hdd/footage, DB_PATH=/path/to/ssd/shinobi_index.db, CACHE_DIR=/path/to/ssd/cache

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8080

# Open the UI
open http://localhost:8080
```

---

## Scenario 1 — Indexer Startup Scan (FR-012, SC-002)

**Verify**: On launch, the indexer scans the footage directory immediately and populates the database.

```bash
# After startup, check indexer status
curl http://localhost:8080/api/indexer/status
# Expected: last_scan_at is set, total_chunks > 0
```

Wait 60 seconds and re-run — `last_scan_at` should update (periodic scan confirmed).

---

## Scenario 2 — Browse Camera Timeline (User Story 1, SC-001)

**Verify**: Timeline query returns results under 500ms.

```bash
# List monitors
curl http://localhost:8080/api/monitors

# Query a full 24-hour window (replace timestamps)
curl "http://localhost:8080/api/monitors/1/chunks?from_ts=1727222400000&to_ts=1727308800000"
# Expected: array of chunks with accurate start_ts/end_ts; response time < 500ms
```

**UI check**: Open browser → select a camera → navigate the day's timeline → gaps appear where no footage exists.

---

## Scenario 3 — mtime Guard (FR-002)

**Verify**: Files modified within the last 60 seconds are not indexed.

```bash
# Touch a file to simulate active write
touch -m /path/to/footage/GroupKey/MonitorID/2026-09-25/new_clip.mp4

# Trigger a scan (or wait for the 60s cycle)
# Query chunks — the touched file should NOT appear until 60s have elapsed
curl "http://localhost:8080/api/monitors/1/chunks?from_ts=...&to_ts=..."
```

---

## Scenario 4 — Export a Merged Clip (User Story 2, SC-003, SC-005)

**Verify**: A 1-hour export completes within 2 minutes, plays without gaps.

```bash
curl -X POST http://localhost:8080/api/jobs/export \
  -H "Content-Type: application/json" \
  -d '{"monitor_id": 1, "from_ts": 1727251200000, "to_ts": 1727254800000}'
# Expected: 202 {"status": "running", "type": "export"}

# Poll progress
watch -n2 'curl -s http://localhost:8080/api/jobs/current'
# Expected: progress increases 0.0 → 1.0; status becomes "done" with download_token

# Download
curl -o export.mp4 "http://localhost:8080/api/downloads/{token}"
# Verify: ffprobe export.mp4 — duration matches selected range; plays without gaps
```

---

## Scenario 5 — Conflict Rejection (FR-013)

**Verify**: A second job request while one is running returns 409.

```bash
# Start a job
curl -X POST http://localhost:8080/api/jobs/export -d '{...}'

# Immediately submit another
curl -X POST http://localhost:8080/api/jobs/timelapse -d '{...}'
# Expected: 409 {"detail": "A job is already in progress..."}
```

---

## Scenario 6 — Cancel a Job (FR-015)

**Verify**: Cancelling a running job stops it and removes partial output.

```bash
# Start a long export
curl -X POST http://localhost:8080/api/jobs/export -d '{...}'

# Cancel
curl -X DELETE http://localhost:8080/api/jobs/current
# Expected: 200 {"status": "cancelled"}

# Confirm no partial file remains in CACHE_DIR
ls $CACHE_DIR   # should be empty
```

---

## Scenario 7 — Timelapse Preview (User Story 3, SC-004)

**Verify**: A 1-hour timelapse is available within 60 seconds.

```bash
curl -X POST http://localhost:8080/api/jobs/timelapse \
  -H "Content-Type: application/json" \
  -d '{"monitor_id": 1, "from_ts": 1727251200000, "to_ts": 1727254800000}'

# Poll until done, then download and verify
curl -o timelapse.mp4 "http://localhost:8080/api/downloads/{token}"
# Verify: plays at accelerated speed; no black frames; duration ≈ 60s
```

---

## Scenario 8 — Disk Space Pre-Check (FR-014)

**Verify**: Request rejected before processing when SSD has insufficient space.

Simulate by setting `CACHE_DIR` to a filesystem with < 1 MB free, then submit an export. Expected: 507 response with message, no partial file written.

---

## Scenario 9 — Unavailable Chunk Handling (FR-016)

**Verify**: Deleted HDD clips appear grayed-out and are unselectable.

```bash
# Delete a file from the HDD footage directory
rm /path/to/footage/GroupKey/MonitorID/2026-09-25/clip.mp4

# Wait for next scan (up to 60s), then query chunks
curl "http://localhost:8080/api/monitors/1/chunks?from_ts=...&to_ts=..."
# Expected: affected chunk has "availability": "unavailable"
```

**UI check**: Grayed-out segment on timeline; clicking it does not enable the export button.

---

## Scenario 10 — One-Time Download Token (FR-010)

**Verify**: Token is consumed on first download; second attempt returns 404.

```bash
# After a completed job, use the token once
curl -o out.mp4 "http://localhost:8080/api/downloads/{token}"  # 200 OK

# Use the same token again
curl "http://localhost:8080/api/downloads/{token}"  # Expected: 404
```

Confirm the temp file in `CACHE_DIR` no longer exists after the first successful download.
