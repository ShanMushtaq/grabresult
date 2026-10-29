#!/usr/bin/env bash
# GrabResult one-command starter (Mac / Linux).
# Creates a virtual environment on first run, installs dependencies,
# then starts the app and opens your browser.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "First run: creating Python environment (one-time, ~1 minute)..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi

echo "Starting GrabResult at http://127.0.0.1:5000 ..."
.venv/bin/python run.py &
APP_PID=$!

sleep 3
if command -v xdg-open >/dev/null; then xdg-open http://127.0.0.1:5000
elif command -v open >/dev/null; then open http://127.0.0.1:5000; fi

echo "GrabResult is running (process $APP_PID). Press Ctrl+C to stop."
wait $APP_PID
