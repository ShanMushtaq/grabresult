@echo off
REM GrabResult one-command starter (Windows). Double-click to run.
cd /d "%~dp0"

if not exist ".venv" (
  echo First run: creating Python environment (one-time, ~1 minute)...
  py -3 -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)

echo Starting GrabResult at http://127.0.0.1:5000 ...
start "" http://127.0.0.1:5000
.venv\Scripts\python run.py
pause
