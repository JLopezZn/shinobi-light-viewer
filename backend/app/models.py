from typing import Optional

from pydantic import BaseModel


class MonitorOut(BaseModel):
    id: int
    group_key: str
    monitor_id: str
    display_name: str
    first_seen_at: int
    last_seen_at: int


class VideoChunkOut(BaseModel):
    id: int
    monitor_id: int
    file_path: str
    start_ts: int
    end_ts: int
    duration_ms: int
    file_size_bytes: int
    availability: str


class JobStatusOut(BaseModel):
    status: str
    type: Optional[str] = None
    progress: float = 0.0
    download_token: Optional[str] = None
    error: Optional[str] = None


class IndexerStatusOut(BaseModel):
    last_scan_at: Optional[int]
    next_scan_in_seconds: Optional[int]
    total_monitors: int
    total_chunks: int
    unavailable_chunks: int


class ExportRequest(BaseModel):
    monitor_id: int
    from_ts: int
    to_ts: int


class TimelapseRequest(BaseModel):
    monitor_id: int
    from_ts: int
    to_ts: int
