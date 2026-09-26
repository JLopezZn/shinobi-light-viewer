# Feature Specification: Shinobi Light Viewer

**Feature Branch**: `001-shinobi-viewer`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Shinobi Light Viewer — a local web app for safely indexing, browsing, and exporting surveillance footage recorded by Shinobi to an external HDD, without interfering with Shinobi's ongoing writes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse Camera Timeline (Priority: P1)

A security operator opens the viewer in their browser, selects a camera from the list, and navigates a day's worth of recorded footage on a visual timeline. They can jump to any time window and see which clips are available.

**Why this priority**: Without the ability to browse footage, no other feature is reachable. This is the entry point of the entire application and the core value proposition.

**Independent Test**: Can be fully tested by running the indexer against a directory of sample `.mp4` files, then loading the UI and verifying that the timeline correctly shows the available clips for each camera.

**Acceptance Scenarios**:

1. **Given** the indexer has scanned the footage directory, **When** a user opens the viewer and selects a camera, **Then** the timeline displays all recorded clips for that camera as a visual timeline with accurate start/end times.
2. **Given** the timeline is displayed, **When** the user selects a date, **Then** only clips from that date are shown, and empty periods appear as gaps.
3. **Given** the indexer is running while Shinobi is recording, **When** the indexer encounters a file modified within the last 60 seconds, **Then** that file is skipped and not added to the index until a subsequent scan.

---

### User Story 2 - Export a Merged Clip (Priority: P2)

An operator selects a start and end time spanning multiple consecutive recorded chunks and downloads a single, continuous `.mp4` file covering the entire selected window.

**Why this priority**: Clip export is the primary output action and key business deliverable — the reason users need to review footage is to extract evidence or send it to a stakeholder.

**Independent Test**: Can be fully tested by selecting a time range that spans two or more recorded files, triggering an export, and verifying the downloaded file plays from start to finish without gaps or corruption.

**Acceptance Scenarios**:

1. **Given** a user selects a time range, **When** they request an export, **Then** the system identifies all clips intersecting the range and merges them into one continuous file losslessly.
2. **Given** the export file is ready, **When** the download link is served, **Then** the user can download the file, and the temporary file is automatically deleted from the SSD after delivery.
3. **Given** the selected time range spans a period with no recorded footage, **When** the user requests an export, **Then** the system notifies the user that no clips cover the selected window.

---

### User Story 3 - Generate a Timelapse Preview (Priority: P3)

An operator wants a quick visual summary of a long time window (e.g., 8 hours). They select the start and end time and receive an accelerated timelapse video covering that period.

**Why this priority**: Timelapse is a convenience feature built on the same infrastructure as clip export. It adds significant value for reviewing long periods but is not needed to deliver the core browsing and export workflow.

**Independent Test**: Can be fully tested by requesting a timelapse for a multi-hour window, verifying the output video duration matches the expected acceleration ratio, and confirming the temporary file is cleaned up post-delivery.

**Acceptance Scenarios**:

1. **Given** a user selects a time range and requests a timelapse, **When** processing completes, **Then** the user receives a playable accelerated video covering the selected period.
2. **Given** the timelapse is generated, **When** delivery is complete, **Then** the temporary timelapse file is automatically removed from the SSD.
3. **Given** the footage directory contains gaps within the selected range, **When** the timelapse is generated, **Then** the output video represents only the available footage (no black frames for missing periods).

---

### Edge Cases

- What happens when a file is still being written by Shinobi at scan time (mtime < 60 seconds)?
- What happens when the selected time range spans multiple days with no continuous footage?
- When local SSD disk space is insufficient: the system pre-checks space before starting and rejects the job with a clear message (FR-014).
- When a previously indexed clip is deleted by Shinobi's retention policy: the indexer marks it as `unavailable` on the next scan; the timeline shows it grayed-out and non-selectable (FR-016).
- What happens when two cameras have overlapping time ranges and one is selected for export?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The indexer MUST recursively scan the configured footage directory and index `.mp4` files using Shinobi's folder structure (`GroupKey/MonitorID/YYYY-MM-DD/filename.mp4`).
- **FR-002**: The indexer MUST skip any file whose modification time is within the last 60 seconds to prevent race conditions with Shinobi's active writes.
- **FR-003**: The indexer MUST store all metadata (file paths, start times, end times, durations, sizes) exclusively in a local SQLite database on the system SSD — never writing anything to the external HDD.
- **FR-004**: The system MUST expose an endpoint to list all available cameras/monitors discovered during indexing.
- **FR-005**: The system MUST expose an endpoint to query video chunks by camera and time range, returning results in milliseconds from the local database.
- **FR-006**: Users MUST be able to select a precise start and end time window via the UI for both export and timelapse operations.
- **FR-007**: The system MUST identify all `.mp4` files that intersect a user-selected time range for merge and timelapse operations.
- **FR-008**: The system MUST merge selected clips losslessly into a single continuous `.mp4` file without re-encoding the video stream.
- **FR-009**: The system MUST generate accelerated timelapse previews for a user-selected time window, caching the temporary output on the local SSD.
- **FR-010**: The system MUST provide a temporary download link for exported clips and timelapse files, and MUST automatically delete these files from the SSD after delivery.
- **FR-011**: The system MUST NEVER write, modify, move, rename, or delete any files within the Shinobi footage directory on the external HDD.
- **FR-012**: The indexer MUST perform a full scan of the footage directory immediately on application startup, and MUST continue scanning automatically on a fixed 60-second interval for the entire lifetime of the process.
- **FR-013**: The system MUST allow only one active export or timelapse job at a time. If a job is already in progress when a new request arrives, the system MUST reject the new request immediately with a clear message informing the user that a job is already running.
- **FR-014**: Before starting any export or timelapse job, the system MUST verify that the local SSD has sufficient free space to accommodate the estimated output file. If space is insufficient, the system MUST reject the job with a clear message before any processing begins; no partial files shall be written.
- **FR-015**: While an export or timelapse job is in progress, the UI MUST display a progress bar reflecting job completion status and MUST provide a cancel button that aborts the job and removes any partial output files from the SSD.
- **FR-016**: During each scan cycle, the indexer MUST check whether previously indexed chunks still exist on the HDD. Any chunk whose file is no longer present MUST be marked as `unavailable` in the index. The UI MUST render unavailable chunks as visually distinct (e.g., grayed-out) on the timeline; they MUST NOT be selectable for export or timelapse operations.

### Key Entities

- **Monitor**: A Shinobi camera identified by a `GroupKey` and `MonitorID`, used to scope timeline queries and exports.
- **Video Chunk**: A single recorded `.mp4` file with a start timestamp, end timestamp, duration, file size, absolute path on the HDD, and an availability status (`available` or `unavailable`) updated on each scan cycle.
- **Index**: The local SQLite database on the SSD containing all `monitors` and `video_chunks` records.
- **Export Job**: A transient operation that merges one or more video chunks into a single output file on the SSD, with a lifecycle ending at download completion.
- **Timelapse Job**: A transient operation that produces an accelerated preview video from a set of indexed chunks, with a lifecycle ending at download completion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Timeline queries for a full 24-hour window on a single camera return results in under 500 milliseconds.
- **SC-002**: The indexer completes a full scan of a 10,000-file footage directory without causing any file access errors or interruptions to Shinobi's recording process.
- **SC-003**: A merged clip export for a 1-hour recording is available for download within 2 minutes of the user requesting it.
- **SC-004**: A timelapse preview for a 1-hour window is available for download within 60 seconds of the user requesting it.
- **SC-005**: Exported merged clips play back without gaps, corruption, or quality loss compared to the source footage.
- **SC-006**: Temporary export and timelapse files are automatically removed from the SSD within 60 seconds of the user's download completing.

## Assumptions

- The Shinobi footage directory path is configurable at startup and does not change during operation.
- The viewer is deployed locally on the same machine that hosts the SSD index database — there is no multi-user or remote-deployment requirement for v1.
- FFmpeg is installed and accessible on the host system's PATH.
- The external HDD is mounted and readable at all times while the application is running; the application does not need to handle hot-plug or reconnect scenarios.
- Shinobi's own retention policy may delete clips from the HDD; the indexer marks stale entries as `unavailable` on the next scan cycle and the UI reflects this state (FR-016).
- Mobile browser support is out of scope for v1; the UI targets desktop browsers only.
- Authentication and access control are out of scope for v1, as the viewer is intended for local LAN use only.

## Clarifications

### Session 2026-09-25

- Q: How should the indexer determine when to scan the footage directory for new clips? → A: Startup scan immediately on launch, then periodic every 60 seconds.
- Q: If a user submits a new export or timelapse request while one is already processing, what should the system do? → A: Allow only one active job at a time; reject new requests with a clear error message while busy.
- Q: What should the system do when the local SSD has insufficient disk space to generate an export or timelapse? → A: Check available SSD space before starting; reject the job with a clear message if space is insufficient, without writing any partial files.
- Q: What should the user see in the UI while an export or timelapse job is processing? → A: Progress bar with a cancel option that aborts the job and cleans up partial files.
- Q: When the indexer finds a previously indexed clip no longer exists on the HDD, what should happen to that entry? → A: Mark it as unavailable in the index; show it grayed-out and non-selectable in the timeline.
