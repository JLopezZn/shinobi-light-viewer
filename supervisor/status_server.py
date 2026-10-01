"""Lightweight status HTTP server for the Shinobi Light Viewer supervisor.

Runs in a daemon thread; stays alive even when the main app is down.
Endpoints:
  GET  /           — HTML status page (auto-refreshes every 5 s)
  GET  /api/status — JSON AppState
  POST /api/restart — manual restart (only effective when crash_capped)
"""

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from supervisor._state import crash_log, restart_event, state, state_lock
from supervisor.supervisor import STATUS_PORT

_STATE_COLORS = {
    "starting": "#f0a500",
    "running": "#22c55e",
    "restarting": "#f0a500",
    "crash_capped": "#ef4444",
}

_STATE_LABELS = {
    "starting": "Iniciando",
    "running": "En ejecución",
    "restarting": "Reiniciando",
    "crash_capped": "Caído (límite alcanzado)",
}


def _render_html() -> str:
    with state_lock:
        s = state.status
        branch = state.current_branch
        crash_count = state.crash_count
        window_start = state.crash_window_start
        events = list(crash_log)[-5:]

    color = _STATE_COLORS.get(s, "#888")
    label = _STATE_LABELS.get(s, s)
    restart_disabled = "" if s == "crash_capped" else "disabled"
    window_str = window_start.strftime("%H:%M:%S UTC") if window_start else "—"

    events_html = ""
    for ev in reversed(events):
        ts = ev.timestamp.strftime("%H:%M:%S")
        reason = ev.reason.replace("<", "&lt;").replace(">", "&gt;")[:200]
        restarted = "sí" if ev.restarted else "no"
        events_html += (
            f"<tr><td>{ts}</td><td>{ev.exit_code}</td>"
            f"<td style='font-family:monospace;font-size:11px'>{reason}</td>"
            f"<td>{restarted}</td></tr>"
        )

    crash_table = (
        f"<table>"
        f"<thead><tr><th>Hora</th><th>Código</th><th>Razón</th><th>Reiniciado</th></tr></thead>"
        f"<tbody>{events_html}</tbody></table>"
        if events_html
        else "<p style='color:#94a3b8'>Sin eventos.</p>"
    )

    hint = (
        '<p style="color:#94a3b8;font-size:12px;margin-top:8px">'
        'El botón se activa sólo cuando el estado es "Caído (límite alcanzado)".</p>'
        if s != "crash_capped"
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="5">
<title>Estado — Shinobi Light Viewer</title>
<style>
  body {{font-family:sans-serif;max-width:720px;margin:40px auto;padding:0 20px;
         background:#0f172a;color:#e2e8f0}}
  h1 {{font-size:1.4rem;margin-bottom:24px}}
  .badge {{display:inline-block;padding:4px 12px;border-radius:999px;font-weight:600;
           background:{color};color:#fff;font-size:1rem}}
  table {{width:100%;border-collapse:collapse;margin-top:16px;font-size:13px}}
  th,td {{text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
  th {{color:#94a3b8}}
  .meta {{color:#94a3b8;font-size:13px;margin:8px 0}}
  button {{margin-top:24px;padding:10px 24px;border:none;border-radius:6px;
           background:#ef4444;color:#fff;font-size:1rem;cursor:pointer}}
  button:disabled {{background:#475569;cursor:not-allowed}}
</style>
</head>
<body>
<h1>Shinobi Light Viewer — Estado del supervisor</h1>
<p>Estado: <span class="badge">{label}</span></p>
<p class="meta">Rama: <strong>{branch}</strong></p>
<p class="meta">Crashes en ventana: <strong>{crash_count}</strong>
  (inicio ventana: {window_str})</p>
<p class="meta"><em>Esta página se actualiza automáticamente cada 5 segundos.</em></p>
<h2 style="font-size:1rem;margin-top:24px">Últimos crashes</h2>
{crash_table}
<form method="POST" action="/api/restart">
  <button type="submit" {restart_disabled}>Reiniciar App</button>
</form>
{hint}
</body>
</html>"""


def _state_json() -> dict:
    with state_lock:
        s = state
        events = list(crash_log)

    def _dt(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    return {
        "state": s.status,
        "branch": s.current_branch,
        "crash_count": s.crash_count,
        "crash_window_start": _dt(s.crash_window_start),
        "last_crash_at": _dt(s.last_crash_at),
        "last_crash_reason": s.last_crash_reason,
        "pending_operation": s.pending_operation,
        "recent_crashes": [
            {
                "timestamp": _dt(ev.timestamp),
                "exit_code": ev.exit_code,
                "reason": ev.reason,
                "restarted": ev.restarted,
            }
            for ev in events
        ],
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default access log

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            body = json.dumps(_state_json()).encode()
            self._send(200, "application/json", body)
        elif self.path in ("/", ""):
            body = _render_html().encode()
            self._send(200, "text/html; charset=utf-8", body)
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        if self.path == "/api/restart":
            with state_lock:
                current = state.status
                if current == "crash_capped":
                    state.crash_count = 0
                    state.crash_window_start = None
                    state.status = "starting"

            if current == "crash_capped":
                restart_event.set()
                body = json.dumps({"status": "restarting"}).encode()
            else:
                body = json.dumps({"status": "already_running"}).encode()
            self._send(200, "application/json", body)
        else:
            self._send(404, "text/plain", b"Not found")


def serve() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", STATUS_PORT), _Handler)
    print(f"[status-server] Listening on port {STATUS_PORT}", flush=True)
    server.serve_forever()
