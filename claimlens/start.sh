#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
FRONTEND="$SCRIPT_DIR/frontend"
VENV="$SCRIPT_DIR/.venv"
BACKEND_LOG="${TMPDIR:-/tmp}/claimlens-backend.log"
FRONTEND_LOG="${TMPDIR:-/tmp}/claimlens-frontend.log"

cleanup() {
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for port in 8000 5173; do
  if lsof -ti ":$port" >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop the existing service, then run ./start.sh again."
    exit 1
  fi
done

echo "ClaimLens AI"
echo "Setting up the local environment..."

if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi

if ! "$VENV/bin/python" -c "import fastapi, uvicorn, httpx, anthropic, dotenv" >/dev/null 2>&1; then
  "$VENV/bin/python" -m pip install -r "$BACKEND/requirements.txt"
fi

if [[ ! -f "$FRONTEND/node_modules/vite/bin/vite.js" ]] || [[ ! -d "$FRONTEND/node_modules/lucide-react" ]]; then
  (cd "$FRONTEND" && npm install)
fi

if [[ -f "$BACKEND/.env" ]]; then
  echo "Claude assist: configured from backend/.env"
else
  echo "Claude assist: optional key not configured (the deterministic extractor still works)"
fi

echo "Starting API and dashboard..."
(cd "$BACKEND" && exec "$VENV/bin/python" -m uvicorn main:app --host 127.0.0.1 --port 8000 >"$BACKEND_LOG" 2>&1) &
BACKEND_PID=$!
(cd "$FRONTEND" && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 >"$FRONTEND_LOG" 2>&1) &
FRONTEND_PID=$!

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && curl -fsS http://127.0.0.1:5173/ >/dev/null 2>&1; then
    echo
    echo "Dashboard: http://localhost:5173"
    echo "API docs:  http://localhost:8000/docs"
    echo "Press Ctrl+C once to stop both services."
    wait
    exit 0
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend failed to start:"
    tail -30 "$BACKEND_LOG"
    exit 1
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Frontend failed to start:"
    tail -30 "$FRONTEND_LOG"
    exit 1
  fi
  sleep 1
done

echo "Services did not become ready in 30 seconds."
echo "Backend log: $BACKEND_LOG"
echo "Frontend log: $FRONTEND_LOG"
exit 1
