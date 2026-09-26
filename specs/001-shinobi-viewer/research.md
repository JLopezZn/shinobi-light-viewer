# Research: Shinobi Light Viewer

**Date**: 2026-09-25 | **Plan**: [plan.md](plan.md)

## Decision 1: FFmpeg Lossless Concatenation

**Decision**: Use the FFmpeg concat demuxer with stream copy (`-c copy`).

**Rationale**: No re-encoding means zero quality loss and fast processing (limited by disk read speed, not CPU). The concat demuxer adjusts timestamps so each segment continues from where the last ended, producing a seamless output file.

**Command pattern**:
```bash
# Build input list
printf "file '%s'\n" /path/to/chunk1.mp4 /path/to/chunk2.mp4 > /tmp/filelist.txt

# Merge losslessly
ffmpeg -f concat -safe 0 -i /tmp/filelist.txt -c copy output.mp4
```

**Alternatives considered**: Re-encoding with `-c:v libx264` — rejected because it violates FR-008 (lossless requirement) and would be far slower.

**Known gotcha**: If source files have non-zero start PTS (possible with some IP cameras), A/V drift may occur. Mitigation: probe source files with `ffprobe` at index time and flag chunks with non-standard PTS for warning in export.

---

## Decision 2: Timelapse Generation (No Black Frames for Gaps)

**Decision**: Concat demuxer + `setpts` video filter. Gaps between recordings are absent from the `filelist.txt`; the concat demuxer naturally omits missing periods.

**Rationale**: Using `setpts=<1/speed>*PTS` accelerates playback by rewriting presentation timestamps. Because the concat demuxer continuously adjusts timestamps, gap periods never appear in the output stream — they simply don't exist in the input.

**Command pattern** (10× speed-up):
```bash
ffmpeg -f concat -safe 0 -i /tmp/filelist.txt \
  -vf "setpts=0.1*PTS" \
  -r 30 \
  -an \
  output_timelapse.mp4
```

**Speed factor**: The UI allows the user to select a time range; the speed factor will be computed automatically to target a ~60-second output (SC-004). Formula: `speed = total_source_duration / 60`.

**Alternatives considered**: Extracting keyframes as images + `ffmpeg -r <fps> -i frame_%04d.jpg` — rejected because it requires full decode of all frames (slow) and introduces quality loss from JPEG re-compression.

---

## Decision 3: FFmpeg Progress Reporting

**Decision**: Use `-progress pipe:1 -nostats` to emit machine-readable key=value lines to stdout; parse `out_time` and compute percentage against total duration.

**Rationale**: The `-progress` flag produces structured output at every frame, making it reliable and race-condition-free. Total duration is obtained via `ffprobe` before the job starts, enabling a real percentage.

**Python pattern**:
```python
proc = await asyncio.create_subprocess_exec(
    "ffmpeg", "-progress", "pipe:1", "-nostats", "-f", "concat",
    "-safe", "0", "-i", filelist_path, "-c", "copy", output_path,
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
)
async for line in proc.stdout:
    m = re.search(rb"out_time_ms=(\d+)", line)
    if m:
        elapsed_ms = int(m.group(1))
        job["progress"] = min(elapsed_ms / total_duration_ms, 1.0)
```

**Alternatives considered**: Parsing stderr `time=HH:MM:SS` — less reliable, mixes with other log output, requires line buffering workarounds.

---

## Decision 4: Single-Job Management (FastAPI)

**Decision**: Module-level async state dict + `asyncio.create_subprocess_exec` + `asyncio.create_task`. Conflict returns HTTP 409.

**Rationale**: `asyncio` subprocess is non-blocking and integrates naturally with FastAPI's event loop. No thread pool needed. A simple module-level dict is sufficient for a single-user local app; no persistence required since jobs are transient.

**Key pattern**:
```python
job_state = {"proc": None, "progress": 0.0, "status": "idle", "output_path": None}

# On new request: check status == "idle", else raise HTTPException(409)
# On cancel: job_state["proc"].kill() + cleanup output_path + reset state
```

**Alternatives considered**: Celery / Redis task queue — massively over-engineered for a single-user local app with one concurrent job.

---

## Decision 5: One-Time Download Token

**Decision**: In-memory `dict[str, Path]` token store. Token is consumed (`.pop()`) on first access. File deletion via FastAPI `BackgroundTasks` after `FileResponse` streams completely.

**Rationale**: Single-use token prevents accidental double-download, satisfies FR-010 (auto-delete after delivery), and requires zero persistence.

**Pattern**:
```python
tokens: dict[str, Path] = {}

def issue_token(path: Path) -> str:
    t = secrets.token_urlsafe(32)
    tokens[t] = path
    return t

@app.get("/api/downloads/{token}")
async def download(token: str, background_tasks: BackgroundTasks):
    path = tokens.pop(token, None)
    if not path or not path.exists():
        raise HTTPException(404)
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(path, media_type="video/mp4")
```

**Alternatives considered**: Serving via signed URL with expiry — unnecessary complexity for a LAN-only app with no CDN.
