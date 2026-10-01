#!/usr/bin/env python3
"""Process supervisor for Shinobi Light Viewer.

Spawns uvicorn as a managed subprocess, implements crash-cap logic,
and hosts a lightweight status HTTP server on a secondary port.
"""

import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Ensure repo root is in sys.path so the 'supervisor' package is importable ──
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from supervisor._state import (  # noqa: E402
    AppState,
    CrashEvent,
    crash_log,
    restart_event,
    state,
    state_lock,
)

# ── Constants ──────────────────────────────────────────────────────────────────
CRASH_LIMIT = 5
CRASH_WINDOW_SECONDS = 120
BACKOFF_SECONDS = 2
EXIT_CODE_INTENTIONAL = 42

# ── Environment ────────────────────────────────────────────────────────────────
SCRIPT_DIR = _REPO_ROOT
BACKEND = Path(os.environ.get("BACKEND", str(SCRIPT_DIR / "backend")))
VENV = Path(os.environ.get("VENV", str(SCRIPT_DIR / ".venv")))
PORT = int(os.environ.get("PORT", "8090"))
STATUS_PORT = int(os.environ.get("STATUS_PORT", str(PORT + 1)))

if sys.platform == "win32":
    UVICORN = VENV / "Scripts" / "uvicorn.exe"
else:
    UVICORN = VENV / "bin" / "uvicorn"


def _detect_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(SCRIPT_DIR),
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _on_process_exit(exit_code: int, stderr_excerpt: str) -> bool:
    """Update shared state after process exits. Returns True if supervisor should restart."""
    with state_lock:
        if exit_code == EXIT_CODE_INTENTIONAL:
            state.crash_count = 0
            state.crash_window_start = None
            state.current_branch = _detect_branch()
            state.status = "restarting"
            return True

        if exit_code in (0,) or exit_code < 0:
            state.status = "restarting"
            return True

        now = datetime.now(timezone.utc)
        if (
            state.crash_window_start is None
            or (now - state.crash_window_start).total_seconds() > CRASH_WINDOW_SECONDS
        ):
            state.crash_window_start = now
            state.crash_count = 0

        state.crash_count += 1
        state.last_crash_at = now
        state.last_crash_reason = stderr_excerpt[:500]

        will_restart = state.crash_count < CRASH_LIMIT
        crash_log.append(CrashEvent(
            timestamp=now,
            exit_code=exit_code,
            reason=stderr_excerpt[:500],
            restarted=will_restart,
        ))

        if state.crash_count >= CRASH_LIMIT:
            state.status = "crash_capped"
            print(
                f"[supervisor] Crash cap reached ({CRASH_LIMIT} crashes). "
                "Stopping auto-restart. Use status page to recover.",
                flush=True,
            )
            return False

        state.status = "restarting"
        return True


def watchdog_loop() -> None:
    """Main loop: spawn uvicorn, monitor exit, apply crash-cap logic."""
    with state_lock:
        state.current_branch = _detect_branch()

    while True:
        with state_lock:
            state.status = "starting"

        print(f"[supervisor] Starting app on port {PORT}...", flush=True)
        try:
            proc = subprocess.Popen(
                [str(UVICORN), "app.main:app", "--host", "0.0.0.0", "--port", str(PORT)],
                cwd=str(BACKEND),
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            print(f"[supervisor] Failed to spawn uvicorn: {e}", flush=True)
            time.sleep(BACKOFF_SECONDS)
            continue

        with state_lock:
            state.status = "running"

        stderr_lines: list = []

        def _read_stderr():
            for line in proc.stderr:
                sys.stderr.write(line)
                sys.stderr.flush()
                stderr_lines.append(line)

        t = threading.Thread(target=_read_stderr, daemon=True)
        t.start()

        exit_code = proc.wait()
        t.join(timeout=2)

        stderr_excerpt = "".join(stderr_lines[-10:])
        print(f"[supervisor] Process exited with code {exit_code}", flush=True)

        should_restart = _on_process_exit(exit_code, stderr_excerpt)

        if not should_restart:
            print("[supervisor] Waiting for manual restart...", flush=True)
            restart_event.wait()
            restart_event.clear()
            with state_lock:
                state.status = "starting"
            print("[supervisor] Manual restart triggered.", flush=True)
            continue

        if exit_code not in (EXIT_CODE_INTENTIONAL, 0) and exit_code >= 0:
            time.sleep(BACKOFF_SECONDS)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from supervisor.status_server import serve as status_serve

    status_thread = threading.Thread(
        target=status_serve,
        daemon=True,
        name="status-server",
    )
    status_thread.start()
    print(f"[supervisor] Status page: http://localhost:{STATUS_PORT}", flush=True)

    watchdog_loop()
