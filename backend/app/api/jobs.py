import asyncio
import re
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..database import get_conn
from ..models import ExportRequest, JobStatusOut, TimelapseRequest
from ..services import ffmpeg as ffmpeg_svc
from ..services.job_manager import (
    cancel_job,
    check_disk_space,
    complete_job,
    consume_token,
    fail_job,
    is_idle,
    job_state,
    start_job,
    update_progress,
)

router = APIRouter()


def _resolve_chunks(monitor_id: int, from_ts: int, to_ts: int) -> list[dict]:
    with get_conn() as conn:
        monitor = conn.execute(
            "SELECT id FROM monitors WHERE id=?", (monitor_id,)
        ).fetchone()
        if not monitor:
            raise HTTPException(status_code=404, detail="Monitor not found.")
        rows = conn.execute(
            """SELECT * FROM video_chunks
               WHERE monitor_id=? AND availability='available'
                 AND start_ts <= ? AND end_ts >= ?
               ORDER BY start_ts""",
            (monitor_id, to_ts, from_ts),
        ).fetchall()
    if not rows:
        raise HTTPException(
            status_code=422,
            detail="No available clips found in the selected time range.",
        )
    return [dict(row) for row in rows]


async def _monitor_job(proc: asyncio.subprocess.Process, total_duration_ms: int) -> None:
    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        m = re.search(rb"out_time_ms=(\d+)", raw_line)
        if m and total_duration_ms > 0:
            elapsed_ms = int(m.group(1))
            update_progress(elapsed_ms / total_duration_ms)

    rc = await proc.wait()
    if rc == 0:
        complete_job()
    else:
        fail_job(f"FFmpeg exited with code {rc}")


@router.post("/jobs/export", status_code=202)
async def start_export(req: ExportRequest) -> dict:
    if not is_idle():
        raise HTTPException(
            status_code=409,
            detail="A job is already in progress. Cancel it or wait for it to complete.",
        )

    chunks = _resolve_chunks(req.monitor_id, req.from_ts, req.to_ts)
    estimated_bytes = sum(c["file_size_bytes"] for c in chunks)
    check_disk_space(estimated_bytes, settings.cache_dir)

    total_duration_ms = sum(c["duration_ms"] for c in chunks)
    output_path = settings.cache_dir / f"export_{int(time.time())}.mp4"
    filelist = ffmpeg_svc.build_filelist([c["file_path"] for c in chunks], settings.cache_dir)
    cmd = ffmpeg_svc.concat_cmd(filelist, output_path)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    start_job("export", output_path, proc)
    asyncio.create_task(_monitor_job(proc, total_duration_ms))
    return {"status": "running", "type": "export"}


@router.post("/jobs/timelapse", status_code=202)
async def start_timelapse(req: TimelapseRequest) -> dict:
    if not is_idle():
        raise HTTPException(
            status_code=409,
            detail="A job is already in progress. Cancel it or wait for it to complete.",
        )

    chunks = _resolve_chunks(req.monitor_id, req.from_ts, req.to_ts)
    total_source_ms = sum(c["duration_ms"] for c in chunks)
    speed = ffmpeg_svc.compute_speed(total_source_ms)
    estimated_bytes = int(sum(c["file_size_bytes"] for c in chunks) / speed)
    check_disk_space(estimated_bytes, settings.cache_dir)

    output_path = settings.cache_dir / f"timelapse_{int(time.time())}.mp4"
    filelist = ffmpeg_svc.build_filelist([c["file_path"] for c in chunks], settings.cache_dir)
    cmd = ffmpeg_svc.timelapse_cmd(filelist, output_path, speed)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    start_job("timelapse", output_path, proc)
    # timelapse duration after speed-up
    output_duration_ms = int(total_source_ms / speed)
    asyncio.create_task(_monitor_job(proc, output_duration_ms))
    return {"status": "running", "type": "timelapse"}


@router.get("/jobs/current", response_model=JobStatusOut)
def get_current_job() -> JobStatusOut:
    return JobStatusOut(
        status=job_state["status"],
        type=job_state["type"],
        progress=job_state["progress"],
        download_token=job_state["download_token"],
        error=job_state["error"],
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
    filename = "export.mp4" if "export" in path.name else "timelapse.mp4"
    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename=filename,
    )
