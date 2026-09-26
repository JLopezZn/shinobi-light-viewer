from typing import List, Optional

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


class IndexerStatusOut(BaseModel):
    last_scan_at: Optional[int] = None
    next_scan_in_seconds: Optional[int] = None
    total_monitors: int
    total_chunks: int
    unavailable_chunks: int


class CameraExportStatus(BaseModel):
    monitor_id: int
    display_name: str
    download_token: Optional[str] = None


class JobStatusOut(BaseModel):
    status: str
    type: Optional[str] = None
    progress: float = 0.0
    cameras: List[CameraExportStatus] = []
    error: Optional[str] = None


class ExportJobRequest(BaseModel):
    monitor_ids: List[int]
    from_ts: int
    to_ts: int
