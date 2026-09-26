import asyncio
import re
import time
from pathlib import Path

from .database import get_conn
from .services.ffmpeg import probe_duration_ms

_CHUNK_PATTERN = re.compile(
    r"(?P<group_key>[^/]+)/(?P<monitor_id>[^/]+)/\d{4}-\d{2}-\d{2}/(?P<filename>[^/]+\.mp4)$"
)

_indexer_state: dict = {
    "last_scan_at": None,
    "next_scan_in_seconds": None,
}


def get_indexer_state() -> dict:
    return _indexer_state


def scan_once(footage_dir: Path) -> None:
    now_ms = int(time.time() * 1000)
    now_s = time.time()

    scanned_paths: set[str] = set()

    for mp4_file in footage_dir.rglob("*.mp4"):
        try:
            stat = mp4_file.stat()
        except OSError:
            continue

        if stat.st_mtime > now_s - 60:
            continue

        rel = mp4_file.relative_to(footage_dir).as_posix()
        m = _CHUNK_PATTERN.match(rel)
        if not m:
            continue

        group_key = m.group("group_key")
        monitor_id = m.group("monitor_id")
        display_name = f"{group_key}/{monitor_id}"
        file_path = str(mp4_file)
        scanned_paths.add(file_path)

        with get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO monitors
                   (group_key, monitor_id, display_name, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (group_key, monitor_id, display_name, now_ms, now_ms),
            )
            conn.execute(
                "UPDATE monitors SET last_seen_at=? WHERE group_key=? AND monitor_id=?",
                (now_ms, group_key, monitor_id),
            )

            row = conn.execute(
                "SELECT id FROM monitors WHERE group_key=? AND monitor_id=?",
                (group_key, monitor_id),
            ).fetchone()
            if not row:
                continue
            db_monitor_id = row["id"]

            existing = conn.execute(
                "SELECT id FROM video_chunks WHERE file_path=?", (file_path,)
            ).fetchone()

            if not existing:
                try:
                    duration_ms = probe_duration_ms(file_path)
                except Exception:
                    duration_ms = int((stat.st_mtime - stat.st_ctime) * 1000)
                    if duration_ms <= 0:
                        duration_ms = 0

                start_ts = int(stat.st_ctime * 1000)
                end_ts = start_ts + duration_ms

                conn.execute(
                    """INSERT OR IGNORE INTO video_chunks
                       (monitor_id, file_path, start_ts, end_ts, duration_ms,
                        file_size_bytes, availability, indexed_at, last_verified_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'available', ?, ?)""",
                    (db_monitor_id, file_path, start_ts, end_ts, duration_ms,
                     stat.st_size, now_ms, now_ms),
                )
            else:
                conn.execute(
                    "UPDATE video_chunks SET last_verified_at=?, availability='available' WHERE file_path=?",
                    (now_ms, file_path),
                )

    with get_conn() as conn:
        available_paths = conn.execute(
            "SELECT file_path FROM video_chunks WHERE availability='available'"
        ).fetchall()
        for row in available_paths:
            path = row["file_path"]
            if not Path(path).exists():
                conn.execute(
                    "UPDATE video_chunks SET availability='unavailable' WHERE file_path=?",
                    (path,),
                )

        unavailable_paths = conn.execute(
            "SELECT file_path FROM video_chunks WHERE availability='unavailable'"
        ).fetchall()
        for row in unavailable_paths:
            if row["file_path"] in scanned_paths:
                conn.execute(
                    "UPDATE video_chunks SET availability='available', last_verified_at=? WHERE file_path=?",
                    (now_ms, row["file_path"]),
                )

    _indexer_state["last_scan_at"] = now_ms


async def run_indexer_loop(footage_dir: Path, interval_seconds: int) -> None:
    while True:
        try:
            scan_once(footage_dir)
        except Exception as exc:
            print(f"[indexer] scan error: {exc}")

        _indexer_state["next_scan_in_seconds"] = interval_seconds
        for remaining in range(interval_seconds, 0, -1):
            _indexer_state["next_scan_in_seconds"] = remaining
            await asyncio.sleep(1)
