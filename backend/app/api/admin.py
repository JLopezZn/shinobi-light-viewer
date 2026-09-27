import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from ..config import settings
from ..database import get_conn
from ..services import docker_manager
from ..services.docker_manager import ContainerStatus
from ..services.job_manager import is_idle

router = APIRouter()


def require_admin_token(x_admin_token: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.delete("/db", status_code=200, dependencies=[Depends(require_admin_token)])
def clear_db() -> dict:
    """Delete all indexed monitors and video chunks."""
    if not is_idle():
        raise HTTPException(
            status_code=409,
            detail="An export job is in progress. Cancel it before clearing the database.",
        )

    with get_conn() as conn:
        conn.execute("DELETE FROM video_chunks")
        conn.execute("DELETE FROM monitors")

    return {"status": "ok"}


@router.get("/admin/docker/status", dependencies=[Depends(require_admin_token)])
def docker_status() -> dict:
    status = docker_manager.get_container_status(settings.shinobi_container)
    return _status_response(status)


@router.post("/admin/docker/stop", dependencies=[Depends(require_admin_token)])
def docker_stop() -> dict:
    try:
        status = docker_manager.stop_container(settings.shinobi_container)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop container: {e}")
    return _status_response(status)


@router.post("/admin/docker/start", dependencies=[Depends(require_admin_token)])
def docker_start() -> dict:
    try:
        status = docker_manager.start_container(settings.shinobi_container)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to start container: {e}")
    return _status_response(status)


@router.post("/admin/docker/restart", dependencies=[Depends(require_admin_token)])
def docker_restart() -> dict:
    try:
        status = docker_manager.restart_container(settings.shinobi_container)
    except RuntimeError as e:
        msg = str(e)
        # Determine phase by checking state after failure
        current_after = docker_manager.get_container_status(settings.shinobi_container)
        if current_after.status == "stopped":
            raise HTTPException(
                status_code=500,
                detail=f"Restart aborted: container stopped but failed to start: {msg}",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Restart aborted: failed to stop container: {msg}",
        )
    return _status_response(status)


def _status_response(status: ContainerStatus) -> dict:
    out: dict = {"status": status.status, "container": status.container}
    if status.message:
        out["message"] = status.message
    return out
