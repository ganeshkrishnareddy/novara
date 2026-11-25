#!/usr/bin/env sh
# NOVARA — beginner-friendly local start (macOS / Linux / Termux).
# No PostgreSQL, Redis, Docker or hosted account required.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="$ROOT/apps/api"
VENV="$ROOT/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating a local Python environment..."
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -e "$API[dev]"

echo ""
echo "NOVARA is starting."
echo "Open http://localhost:8000 in your browser."
echo "Finish the first-run setup, then use the dashboard."
echo "Press Ctrl+C to stop."
echo ""

export PYTHONPATH="$API"
exec "$VENV/bin/python" -m uvicorn novara_core.main:app --app-dir "$API" --host 127.0.0.1 --port 8000
