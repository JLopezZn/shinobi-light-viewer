"""Shared mutable supervisor state — imported by both supervisor.py and status_server.py."""

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CrashEvent:
    timestamp: datetime
    exit_code: int
    reason: str  # truncated to 500 chars
    restarted: bool


@dataclass
class AppState:
    status: str = "starting"  # starting | running | restarting | crash_capped
    current_branch: str = "unknown"
    crash_count: int = 0
    crash_window_start: Optional[datetime] = None
    last_crash_at: Optional[datetime] = None
    last_crash_reason: Optional[str] = None
    pending_operation: Optional[str] = None  # None | "update" | "switch"


state = AppState()
crash_log: deque = deque(maxlen=20)
state_lock = threading.Lock()
restart_event = threading.Event()
