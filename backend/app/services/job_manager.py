import asyncio
import secrets
import shutil
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

job_state: dict = {
    "status": "idle",
    "type": None,
    "progress": 0.0,
    "proc": None,
    "output_path": None,
    "error": None,
    "download_token": None,
}

tokens: dict[str, Path] = {}


def is_idle() -> bool:
    return job_state["status"] == "idle"


def start_job(job_type: str, output_path: Path, proc: asyncio.subprocess.Process) -> None:
    job_state.update({
        "status": "running",
        "type": job_type,
        "progress": 0.0,
        "proc": proc,
        "output_path": output_path,
        "error": None,
        "download_token": None,
    })


def update_progress(pct: float) -> None:
    job_state["progress"] = min(pct, 1.0)


def complete_job() -> str:
    token = secrets.token_urlsafe(32)
    tokens[token] = job_state["output_path"]
    job_state.update({
        "status": "done",
        "progress": 1.0,
        "proc": None,
        "download_token": token,
    })
    return token


def fail_job(error: str) -> None:
    _cleanup_output()
    job_state.update({
        "status": "failed",
        "proc": None,
        "error": error,
    })


def cancel_job() -> None:
    proc = job_state.get("proc")
    if proc:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    _cleanup_output()
    job_state.update({
        "status": "idle",
        "type": None,
        "progress": 0.0,
        "proc": None,
        "output_path": None,
        "error": None,
        "download_token": None,
    })


def _cleanup_output() -> None:
    path: Path | None = job_state.get("output_path")
    if path and path.exists():
        path.unlink(missing_ok=True)
    filelist = path.parent / "filelist.txt" if path else None
    if filelist and filelist.exists():
        filelist.unlink(missing_ok=True)


def consume_token(token: str) -> Optional[Path]:
    return tokens.pop(token, None)


def check_disk_space(estimated_bytes: int, cache_dir: Path) -> None:
    free = shutil.disk_usage(cache_dir).free
    required = int(estimated_bytes * 1.1)
    if free < required:
        req_mb = required // (1024 * 1024)
        free_mb = free // (1024 * 1024)
        raise HTTPException(
            status_code=507,
            detail=f"Insufficient disk space on SSD. Estimated {req_mb} MB required, {free_mb} MB available.",
        )
