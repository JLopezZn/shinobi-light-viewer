# Implementation Plan: Shinobi Light Viewer

**Branch**: `001-shinobi-viewer` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-shinobi-viewer/spec.md`

## Summary

A local web application that indexes `.mp4` surveillance footage recorded by Shinobi on an external HDD, exposes a timeline-based browser UI, and allows operators to export merged clips or timelapse previews — all without ever writing to the HDD. The backend is a FastAPI server (Python 3.10+) that runs an auto-scanning indexer, stores metadata in a local SQLite database, and delegates all video processing to FFmpeg subprocesses writing exclusively to a local SSD cache.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: FastAPI, Uvicorn, SQLite (stdlib `sqlite3`), FFmpeg (via `subprocess`), Vanilla JS / HTML5 (frontend, no build step)

**Storage**: SQLite on local SSD (`shinobi_index.db`)

**Testing**: pytest, pytest-asyncio (for async FastAPI routes), httpx (for test client)

**Target Platform**: Single Linux/Windows machine, LAN access via desktop browser

**Project Type**: Web service (FastAPI backend serving both the REST API and static frontend files)

**Performance Goals**:
- Timeline queries for 24h window < 500ms (SC-001)
- Export of 1-hour footage available within 2 minutes (SC-003)
- Timelapse of 1-hour window available within 60 seconds (SC-004)

**Constraints**:
- Zero writes to external HDD — all writes go to local SSD only
- mtime guard: skip any file modified within the last 60 seconds
- At most one active export/timelapse job at any time (FR-013)
- Temp files deleted within 60 seconds of download completion (SC-006)

**Scale/Scope**: Single operator, local LAN, desktop browsers only, v1

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status |
|------|-------------|--------|
| Zero HDD writes | App NEVER writes/modifies/deletes files in Shinobi footage directory (FR-011) | PASS — enforced as hard constraint; FFmpeg output paths always target SSD cache dir |
| mtime race guard | Indexer skips files with mtime < 60 seconds (FR-002) | PASS — checked on every scan cycle before inserting/updating any record |
| Decoupled metadata | SQLite db and all temp files reside on local SSD only (FR-003) | PASS — db path and cache dir are both SSD-side, configurable at startup |

All gates pass. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-shinobi-viewer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py              # FastAPI app factory, startup/shutdown hooks
│   ├── config.py            # Settings (footage dir, db path, cache dir, scan interval)
│   ├── database.py          # SQLite connection, schema init
│   ├── indexer.py           # Scan loop, mtime guard, availability check
│   ├── models.py            # Dataclasses / Pydantic models (Monitor, VideoChunk, Job)
│   ├── api/
│   │   ├── monitors.py      # GET /api/monitors
│   │   ├── chunks.py        # GET /api/monitors/{id}/chunks
│   │   └── jobs.py          # POST /api/jobs/export|timelapse, GET/DELETE /api/jobs/current, GET /api/downloads/{token}
│   └── services/
│       ├── ffmpeg.py        # Lossless concat, timelapse, progress reporting
│       └── job_manager.py   # Single-job lock, cancellation, token generation, cleanup
└── tests/
    ├── unit/
    │   ├── test_indexer.py
    │   ├── test_ffmpeg.py
    │   └── test_job_manager.py
    ├── integration/
    │   ├── test_monitors_api.py
    │   ├── test_chunks_api.py
    │   └── test_jobs_api.py
    └── contract/
        └── test_api_contracts.py

frontend/
├── index.html
├── app.js               # Timeline rendering, job submission, progress polling
└── style.css
```

**Structure Decision**: Web application layout (Option 2) — separate `backend/` and `frontend/` directories. The FastAPI app serves the frontend static files directly via `StaticFiles` mount, so no separate web server is needed for v1.

## Complexity Tracking

> No constitution violations detected. Section not required.
