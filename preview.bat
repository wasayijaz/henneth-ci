@echo off
REM Double-click to preview Henneth AI locally.
REM Serves the repo with local state/. Nothing goes to the cloud.
cd /d "%~dp0"
start "" "http://localhost:8877/dashboard/"
python scripts\serve.py
pause
