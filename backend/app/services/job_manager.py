import secrets
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException

_state: dict = {
    "status": "idle",
    "type": None,
    "cameras": [],
    "error": None,
}


def is_idle() -> bool:
    return _state["status"] == "idle"


def get_state() -> dict:
    return _state


def get_overall_progress() -> float:
    cameras = _state["cameras"]
    if not cameras:
        return 0.0
    return min(c["progress"] for c in cameras)


def make_camera_entry(monitor_id: int, display_name: str) -> dict:
    return {
        "monitor_id": monitor_id,
        "display_name": display_name,
        "output_path": None,
        "filelist_path": None,
        "proc": None,
        "progress": 0.0,
        "download_token": None,
    }


def start_export(cameras: List[dict]) -> None:
    _state.update({
        "status": "running",
        "type": "export",
        "cameras": cameras,
        "error": None,
    })


def update_camera_progress(monitor_id: int, pct: float) -> None:
    for cam in _state["cameras"]:
        if cam["monitor_id"] == monitor_id:
            cam["progress"] = min(pct, 0.99)
            break


def complete_camera(monitor_id: int) -> str:
    token = secrets.token_urlsafe(32)
    for cam in _state["cameras"]:
        if cam["monitor_id"] == monitor_id:
            cam["download_token"] = token
            cam["progress"] = 1.0
            cam["proc"] = None
            break
    if all(c["download_token"] is not None for c in _state["cameras"]):
        _state["status"] = "done"
    return token


def fail_job(error: str) -> None:
    _cleanup_files()
    _state["status"] = "failed"
    _state["error"] = error
    for cam in _state["cameras"]:
        cam["proc"] = None


def cancel_job() -> None:
    for cam in _state["cameras"]:
        proc = cam.get("proc")
        if proc:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        cam["proc"] = None
    _cleanup_files()
    _reset()


def _cleanup_files() -> None:
    for cam in _state["cameras"]:
        out = cam.get("output_path")
        if out:
            p = Path(out)
            if p.exists():
                p.unlink(missing_ok=True)
        fl = cam.get("filelist_path")
        if fl:
            p = Path(fl)
            if p.exists():
                p.unlink(missing_ok=True)


def _reset() -> None:
    _state.update({
        "status": "idle",
        "type": None,
        "cameras": [],
        "error": None,
    })


def consume_token(token: str) -> Optional[Path]:
    for cam in _state["cameras"]:
        if cam.get("download_token") == token:
            cam["download_token"] = None
            path_str = cam.get("output_path")
            cam["output_path"] = None
            return Path(path_str) if path_str else None
    return None


def check_disk_space(estimated_bytes: int, cache_dir: Path) -> None:
    free = shutil.disk_usage(str(cache_dir)).free
    required = int(estimated_bytes * 1.1)
    if free < required:
        req_mb = required // (1024 * 1024)
        free_mb = free // (1024 * 1024)
        raise HTTPException(
            status_code=507,
            detail=f"Insufficient disk space on SSD. Estimated {req_mb} MB required, {free_mb} MB available.",
        )
