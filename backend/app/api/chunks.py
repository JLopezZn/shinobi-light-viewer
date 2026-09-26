from fastapi import APIRouter, HTTPException, Query

from ..database import get_conn
from ..models import VideoChunkOut

router = APIRouter()


@router.get("/monitors/{monitor_id}/chunks", response_model=list[VideoChunkOut])
def get_chunks(
    monitor_id: int,
    from_ts: int = Query(..., description="Range start, Unix milliseconds"),
    to_ts: int = Query(..., description="Range end, Unix milliseconds"),
) -> list[VideoChunkOut]:
    with get_conn() as conn:
        monitor = conn.execute(
            "SELECT id FROM monitors WHERE id=?", (monitor_id,)
        ).fetchone()
        if not monitor:
            raise HTTPException(status_code=404, detail="Monitor not found.")

        rows = conn.execute(
            """SELECT * FROM video_chunks
               WHERE monitor_id=? AND start_ts <= ? AND end_ts >= ?
               ORDER BY start_ts""",
            (monitor_id, to_ts, from_ts),
        ).fetchall()
    return [VideoChunkOut(**dict(row)) for row in rows]
