#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
cd "$PROJECT_ROOT"

HOST="${NINEBOT_HOST:-127.0.0.1}"
PORT="${NINEBOT_PORT:-8000}"
FRONTEND_HOST="${NINEBOT_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${NINEBOT_FRONTEND_PORT:-5173}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  BOOTSTRAP_PYTHON="$PYTHON_BIN"
elif command -v python3 >/dev/null 2>&1; then
  BOOTSTRAP_PYTHON="python3"
else
  BOOTSTRAP_PYTHON="python"
fi

resolve_venv_python() {
  if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
    printf '%s\n' "$BACKEND_DIR/.venv/bin/python"
    return
  fi

  if [[ -x "$BACKEND_DIR/.venv/Scripts/python.exe" ]]; then
    printf '%s\n' "$BACKEND_DIR/.venv/Scripts/python.exe"
    return
  fi

  return 1
}

if ! VENV_PYTHON="$(resolve_venv_python)"; then
  echo "[9Bot] Creating backend virtual environment..."
  "$BOOTSTRAP_PYTHON" -m venv "$BACKEND_DIR/.venv"
  VENV_PYTHON="$(resolve_venv_python)"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[9Bot] npm is required to run the frontend."
  exit 1
fi

echo "[9Bot] Installing backend dependencies..."
"$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt"

echo "[9Bot] Installing frontend dependencies..."
npm install --prefix "$FRONTEND_DIR"

echo "[9Bot] Starting backend API at http://${HOST}:${PORT}"
(
  cd "$BACKEND_DIR"
  env NINEBOT_HOST="$HOST" NINEBOT_PORT="$PORT" "$VENV_PYTHON" -m app.main
) &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[9Bot] Starting frontend at http://${FRONTEND_HOST}:${FRONTEND_PORT}"
exec env VITE_API_BASE_URL="http://${HOST}:${PORT}/api" npm run dev --prefix "$FRONTEND_DIR" -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
