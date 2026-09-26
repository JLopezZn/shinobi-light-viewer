# Functional Specification: Shinobi Light Viewer Features

## Feature 1: Safe Background Indexer (`indexer.py`)
- **Objective:** Recursively scan `D:\ShinobiVideos` to build a fast, local SQLite index without interrupting Shinobi's ongoing writes.
- **Requirements:**
  - Parse Shinobi's folder nomenclature (`GroupKey/MonitorID/YYYY-MM-DD/filename.mp4`).
  - Implement the `mtime` security rule: skip files modified within the last 60 seconds to avoid race conditions and file locks.
  - Populate SQLite tables (`monitors`, `videos`) containing file paths, start times, end times, durations, and sizes.

## Feature 2: High-Performance Timeline API (`main.py` & `database.py`)
- **Objective:** Serve timeline metadata instantly to the frontend from the local SSD database.
- **Requirements:**
  - Endpoints to fetch available cameras/monitors.
  - Endpoint to query video chunks filtered by a custom date and time range across one or multiple cameras in milliseconds.

## Feature 3: Custom Date/Time Range & Timelapse Generation (`processor.py`)
- **Objective:** Provide visual summaries and quick previews of specific time intervals.
- **Requirements:**
  - Allow users to select a precise start and end time window via UI.
  - Generate accelerated timelapse previews using FFmpeg, caching temporary results locally on the SSD.

## Feature 4: Clip Merging & Export (`processor.py` & API)
- **Objective:** Allow users to download a continuous video file spanning multiple consecutive recorded chunks.
- **Requirements:**
  - Automatically identify all `.mp4` files intersecting the user-selected time range.
  - Use FFmpeg's concat demuxer (`-f concat -safe 0 -i list.txt -c copy output.mp4`) to merge clips losslessly into a single file.
  - Provide a secure, temporary download link followed by automatic cleanup of the generated export file from the SSD.