from fastapi import APIRouter

from ..database import get_conn
from ..indexer import get_indexer_state
from ..models import IndexerStatusOut, MonitorOut

router = APIRouter()


@router.get("/monitors", response_model=list[MonitorOut])
def list_monitors() -> list[MonitorOut]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM monitors ORDER BY display_name"
        ).fetchall()
    return [MonitorOut(**dict(row)) for row in rows]


@router.get("/indexer/status", response_model=IndexerStatusOut)
def indexer_status() -> IndexerStatusOut:
    state = get_indexer_state()
    with get_conn() as conn:
        total_monitors = conn.execute("SELECT COUNT(*) FROM monitors").fetchone()[0]
        total_chunks = conn.execute("SELECT COUNT(*) FROM video_chunks").fetchone()[0]
        unavailable_chunks = conn.execute(
            "SELECT COUNT(*) FROM video_chunks WHERE availability='unavailable'"
        ).fetchone()[0]
    return IndexerStatusOut(
        last_scan_at=state["last_scan_at"],
        next_scan_in_seconds=state["next_scan_in_seconds"],
        total_monitors=total_monitors,
        total_chunks=total_chunks,
        unavailable_chunks=unavailable_chunks,
    )
