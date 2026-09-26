# Constitutional Specification: Shinobi Light Viewer

## 1. Core Principles & Directives
- **Zero Interference with Shinobi (Crucial):** Shinobi has exclusive write access to the external HDD (`D:\ShinobiVideos`). The custom app must **NEVER** write, modify, move, rename, or delete any files inside the Shinobi storage directory. All file operations on the external HDD are strictly read-only.
- **Concurrent Read/Write Safety & Race Condition Prevention:** Because both Shinobi and the indexer may access the external HDD simultaneously, the indexer must implement safety checks. It must inspect file modification times (`mtime`) and completely ignore any file modified within the last 60 seconds to prevent reading files while Shinobi is still actively writing data packets to them.
- **Decoupled Metadata Storage:** All metadata, database records (`shinobi_index.db`), and cache files must reside exclusively on the local high-speed system SSD, ensuring zero write traffic to the external HDD from the custom app.

## 2. Technical Stack & Boundaries
- **Language & Framework:** Python 3.10+ with FastAPI.
- **Metadata Database:** SQLite (Local SSD).
- **Video Manipulation Engine:** FFmpeg (via controlled subprocesses, reading from the HDD but writing temporary exports/timelapses exclusively to local SSD cache).
- **Frontend:** Vanilla JS / HTML5 with native HTTP Range Requests for streaming.

## 3. Compliance & Safety
- **File Access Verification:** Every filesystem scan must verify `mtime` thresholds before attempting to index or read metadata.
- **Resource Management:** Temporary files generated during clip merging or timelapse rendering must be automatically purged from the SSD after delivery.