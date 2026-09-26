import asyncio
import re
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..database import get_conn
from ..models import CameraExportStatus, ExportJobRequest, JobStatusOut
from ..services import ffmpeg as ffmpeg_svc
from ..services.job_manager import (
    cancel_job,
    check_disk_space,
    complete_camera,
    consume_token,
    fail_job,
    get_overall_progress,
    get_state,
    is_idle,
    make_camera_entry,
    start_export,
    update_camera_progress,
)

router = APIRouter()


def _fetch_chunks(monitor_id: int, from_ts: int, to_ts: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM video_chunks
               WHERE monitor_id=? AND availability='available'
                 AND start_ts <= ? AND end_ts >= ?
               ORDER BY start_ts""",
            (monitor_id, to_ts, from_ts),
        ).fetchall()
    return [dict(row) for row in rows]


async def _monitor_camera(monitor_id: int, total_duration_ms: int) -> None:
    state = get_state()
    cam = next((c for c in state["cameras"] if c["monitor_id"] == monitor_id), None)
    if not cam or not cam.get("proc"):
        return

    proc = cam["proc"]
    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        if state["status"] != "running":
            break
        m = re.search(rb"out_time_ms=(\d+)", raw_line)
        if m and total_duration_ms > 0:
            elapsed_ms = int(m.group(1))
            update_camera_progress(monitor_id, elapsed_ms / total_duration_ms)

    rc = await proc.wait()
    if state["status"] == "running":
        if rc == 0:
            complete_camera(monitor_id)
        else:
            fail_job(f"FFmpeg exited with code {rc} for camera {monitor_id}")


@router.post("/jobs/export", status_code=202)
async def start_export_job(req: ExportJobRequest) -> dict:
    if not is_idle():
        raise HTTPException(
            status_code=409,
            detail="A job is already in progress. Cancel it or wait for it to complete.",
        )

    if not req.monitor_ids:
        raise HTTPException(status_code=422, detail="monitor_ids must not be empty.")
    if req.from_ts >= req.to_ts:
        raise HTTPException(status_code=422, detail="from_ts must be less than to_ts.")

    # Resolve monitor display names and chunks
    camera_entries = []
    all_chunks: list = []
    for mid in req.monitor_ids:
        with get_conn() as conn:
            mon = conn.execute(
                "SELECT id, display_name FROM monitors WHERE id=?", (mid,)
            ).fetchone()
        if not mon:
            raise HTTPException(status_code=422, detail=f"Monitor {mid} not found.")

        chunks = _fetch_chunks(mid, req.from_ts, req.to_ts)
        if not chunks:
            continue  # skip cameras with no footage (FR-020)

        cam = make_camera_entry(mid, mon["display_name"])
        camera_entries.append((cam, chunks))
        all_chunks.extend(chunks)

    if not camera_entries:
        raise HTTPException(
            status_code=422,
            detail="No available clips found in the selected time range for any of the requested cameras.",
        )

    total_bytes = ffmpeg_svc.compute_export_size(all_chunks)
    check_disk_space(total_bytes, settings.cache_dir)

    ts = int(time.time())
    cameras_state = []
    for cam, chunks in camera_entries:
        mid = cam["monitor_id"]
        output_path = settings.cache_dir / f"export_{mid}_{ts}.mp4"
        filelist = ffmpeg_svc.build_filelist(
            [c["file_path"] for c in chunks],
            settings.cache_dir,
            name=f"filelist_{mid}_{ts}.txt",
        )
        cam["output_path"] = str(output_path)
        cam["filelist_path"] = str(filelist)
        cameras_state.append((cam, chunks))

    start_export([c for c, _ in cameras_state])

    state = get_state()
    for cam_entry, chunks in cameras_state:
        mid = cam_entry["monitor_id"]
        output_path = cam_entry["output_path"]
        filelist_path = cam_entry["filelist_path"]

        from pathlib import Path
        cmd = ffmpeg_svc.concat_cmd(Path(filelist_path), Path(output_path))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # Store proc reference in state
        for sc in state["cameras"]:
            if sc["monitor_id"] == mid:
                sc["proc"] = proc
                break

        total_duration_ms = sum(c["duration_ms"] for c in chunks)
        asyncio.create_task(_monitor_camera(mid, total_duration_ms))

    return {
        "status": "running",
        "type": "export",
        "cameras": [
            {"monitor_id": c["monitor_id"], "display_name": c["display_name"]}
            for c in state["cameras"]
        ],
    }


@router.get("/jobs/current", response_model=JobStatusOut)
def get_current_job() -> JobStatusOut:
    state = get_state()
    return JobStatusOut(
        status=state["status"],
        type=state["type"],
        progress=get_overall_progress(),
        cameras=[
            CameraExportStatus(
                monitor_id=c["monitor_id"],
                display_name=c["display_name"],
                download_token=c.get("download_token"),
            )
            for c in state["cameras"]
        ],
        error=state["error"],
    )


@router.delete("/jobs/current")
def cancel_current_job() -> dict:
    if is_idle():
        raise HTTPException(status_code=404, detail="No job is currently running.")
    cancel_job()
    return {"status": "cancelled"}


@router.get("/downloads/{token}")
def download_file(token: str, background_tasks: BackgroundTasks) -> FileResponse:
    path = consume_token(token)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Download token not found or already used.")
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename=path.name,
    )
