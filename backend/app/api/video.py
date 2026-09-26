import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..database import get_conn

router = APIRouter()

_CHUNK_SIZE = 2 * 1024 * 1024  # 2 MB read buffer — fewer iterations per stream


def _stream_file(path: str, start: int, end: int):
    try:
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(_CHUNK_SIZE, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data
    except OSError:
        # File disappeared mid-stream (HDD disconnected, file rotated out, etc.).
        # Ending the generator gives the client a truncated-but-not-crashed response.
        return


@router.get("/video/{chunk_id}")
async def stream_video(chunk_id: int, request: Request):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT file_path, availability FROM video_chunks WHERE id=?",
            (chunk_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found.")
    if row["availability"] == "unavailable":
        raise HTTPException(status_code=410, detail="Chunk file is no longer available on disk.")

    file_path = row["file_path"]
    try:
        size = os.path.getsize(file_path)
    except OSError:
        raise HTTPException(status_code=410, detail="Chunk file is no longer available on disk.")

    range_header = request.headers.get("range")
    start = 0
    end = size - 1
    status_code = 200

    if range_header:
        try:
            byte_range = range_header.replace("bytes=", "").strip()
            parts = byte_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else size - 1
            end = min(end, size - 1)
        except (ValueError, IndexError):
            raise HTTPException(status_code=416, detail="Invalid Range header.")
        status_code = 206

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Content-Range": f"bytes {start}-{end}/{size}",
        # Chunks are immutable once Shinobi writes them — cache aggressively so
        # re-seeks and chunk transitions are served from the browser's disk cache.
        "Cache-Control": "public, max-age=86400, immutable",
    }

    return StreamingResponse(
        _stream_file(file_path, start, end),
        status_code=status_code,
        media_type="video/mp4",
        headers=headers,
    )
