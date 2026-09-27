from fastapi import APIRouter, HTTPException

from ..database import get_conn
from ..services.job_manager import is_idle

router = APIRouter()


@router.delete("/db", status_code=200)
def clear_db() -> dict:
    """Delete all indexed monitors and video chunks.

    Refused while an export job is running to avoid leaving the job manager
    with dangling references to monitors that no longer exist.
    """
    if not is_idle():
        raise HTTPException(
            status_code=409,
            detail="An export job is in progress. Cancel it before clearing the database.",
        )

    with get_conn() as conn:
        conn.execute("DELETE FROM video_chunks")
        conn.execute("DELETE FROM monitors")

    return {"status": "ok"}
