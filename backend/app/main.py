import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import settings
from .database import init_db
from .indexer import run_indexer_loop


class _SuppressClientDisconnect:
    """Silences BrokenPipeError / ConnectionResetError raised when a browser
    cancels a streaming HTTP request (e.g. video seek mid-transfer).
    These are not server errors and do not need a traceback in the logs."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        try:
            await self._app(scope, receive, send)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client disconnected mid-stream — normal for range requests


_fastapi = FastAPI(title="Shinobi Light Viewer")


@_fastapi.on_event("startup")
async def startup() -> None:
    init_db(settings.db_path)
    asyncio.create_task(
        run_indexer_loop(settings.footage_dir, settings.scan_interval_seconds)
    )


from .api import chunks, jobs, monitors, video  # noqa: E402

_fastapi.include_router(monitors.router, prefix="/api")
_fastapi.include_router(chunks.router, prefix="/api")
_fastapi.include_router(video.router, prefix="/api")
_fastapi.include_router(jobs.router, prefix="/api")

_frontend = Path(__file__).parent.parent.parent / "frontend"
if _frontend.exists():
    _fastapi.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")

# Wrap as the outermost ASGI app so uvicorn imports this name.
app = _SuppressClientDisconnect(_fastapi)
