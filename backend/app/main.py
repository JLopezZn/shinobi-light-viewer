import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import settings
from .database import init_db
from .indexer import run_indexer_loop


def _is_client_disconnect(exc: BaseException) -> bool:
    """Return True if exc is (or wraps exclusively) client-disconnect errors.

    Starlette 0.20+ raises uvicorn's ClientDisconnected inside an anyio
    ExceptionGroup/BaseExceptionGroup.  We check by class name to avoid a
    hard import dependency on uvicorn internals or the exceptiongroup backport.
    """
    name = type(exc).__name__
    if name in ("ClientDisconnected", "BrokenPipeError", "ConnectionResetError"):
        return True
    if name in ("ExceptionGroup", "BaseExceptionGroup") and hasattr(exc, "exceptions"):
        return all(_is_client_disconnect(e) for e in exc.exceptions)
    return False


class _SuppressClientDisconnect:
    """Silences client-disconnect errors raised when a browser cancels a
    streaming HTTP request (e.g. video seek mid-transfer).
    These are not server errors and do not need a traceback in the logs."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        try:
            await self._app(scope, receive, send)
        except BaseException as exc:
            if not _is_client_disconnect(exc):
                raise


_fastapi = FastAPI(title="Shinobi Light Viewer")


@_fastapi.on_event("startup")
async def startup() -> None:
    init_db(settings.db_path)
    asyncio.create_task(
        run_indexer_loop(settings.footage_dir, settings.scan_interval_seconds)
    )


from .api import admin, chunks, jobs, monitors, video  # noqa: E402

_fastapi.include_router(monitors.router, prefix="/api")
_fastapi.include_router(chunks.router, prefix="/api")
_fastapi.include_router(video.router, prefix="/api")
_fastapi.include_router(jobs.router, prefix="/api")
_fastapi.include_router(admin.router, prefix="/api")

_frontend = Path(__file__).parent.parent.parent / "frontend"
if _frontend.exists():
    _fastapi.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")

# Wrap as the outermost ASGI app so uvicorn imports this name.
app = _SuppressClientDisconnect(_fastapi)
