#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

HOST="${NINEBOT_HOST:-127.0.0.1}"
PORT="${NINEBOT_PORT:-8000}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  BOOTSTRAP_PYTHON="$PYTHON_BIN"
elif command -v python3 >/dev/null 2>&1; then
  BOOTSTRAP_PYTHON="python3"
else
  BOOTSTRAP_PYTHON="python"
fi

resolve_venv_python() {
  if [[ -x ".venv/bin/python" ]]; then
    printf '%s\n' ".venv/bin/python"
    return
  fi

  if [[ -x ".venv/Scripts/python.exe" ]]; then
    printf '%s\n' ".venv/Scripts/python.exe"
    return
  fi

  return 1
}

if ! VENV_PYTHON="$(resolve_venv_python)"; then
  echo "[9Bot] Creating virtual environment..."
  "$BOOTSTRAP_PYTHON" -m venv ".venv"
  VENV_PYTHON="$(resolve_venv_python)"
fi

echo "[9Bot] Installing dependencies..."
"$VENV_PYTHON" -m pip install -r "requirements.txt"

echo "[9Bot] Starting server at http://${HOST}:${PORT}"
exec "$VENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
