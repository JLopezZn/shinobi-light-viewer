#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
BACKEND="$SCRIPT_DIR/backend"
ENV_FILE="$BACKEND/.env"

# ── Virtualenv ──────────────────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python3" ]; then
  echo "[setup] Creating virtualenv..."
  python3 -m venv "$VENV"
fi

# ── Dependencies ────────────────────────────────────────────────────────────
echo "[setup] Installing dependencies..."
"$VENV/bin/pip" install -q -r "$BACKEND/requirements.txt"

# ── .env ────────────────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "[setup] No .env found — copying from .env.example"
  cp "$BACKEND/.env.example" "$ENV_FILE"
  echo ""
  echo "  Edit $ENV_FILE and set FOOTAGE_DIR, DB_PATH, and CACHE_DIR"
  echo "  then re-run this script."
  echo ""
  exit 1
fi

# Load env vars from backend/.env
set -a
# shellcheck disable=SC1091
. "$ENV_FILE"
set +a

PORT="${PORT:-8080}"

echo "[start] Shinobi Light Viewer → http://localhost:$PORT"
cd "$BACKEND"
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT"
