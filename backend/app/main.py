import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .indexer import run_indexer_loop

app = FastAPI(title="Shinobi Light Viewer")


@app.on_event("startup")
async def startup() -> None:
    init_db(settings.db_path)
    asyncio.create_task(
        run_indexer_loop(settings.footage_dir, settings.scan_interval_seconds)
    )


from .api import monitors, chunks, jobs  # noqa: E402 — after app creation

app.include_router(monitors.router, prefix="/api")
app.include_router(chunks.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")

_frontend = Path(__file__).parent.parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
