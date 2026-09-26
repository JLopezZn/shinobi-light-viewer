import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_DB_PATH: Optional[Path] = None


def init_db(db_path: Path) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS monitors (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                group_key     TEXT    NOT NULL,
                monitor_id    TEXT    NOT NULL,
                display_name  TEXT    NOT NULL,
                first_seen_at INTEGER NOT NULL,
                last_seen_at  INTEGER NOT NULL,
                UNIQUE(group_key, monitor_id)
            );

            CREATE TABLE IF NOT EXISTS video_chunks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id       INTEGER NOT NULL REFERENCES monitors(id),
                file_path        TEXT    NOT NULL UNIQUE,
                start_ts         INTEGER NOT NULL,
                end_ts           INTEGER NOT NULL,
                duration_ms      INTEGER NOT NULL,
                file_size_bytes  INTEGER NOT NULL,
                availability     TEXT    NOT NULL DEFAULT 'available',
                indexed_at       INTEGER NOT NULL,
                last_verified_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_monitor_time
                ON video_chunks(monitor_id, start_ts, end_ts);
        """)


@contextmanager
def get_conn():
    if _DB_PATH is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
