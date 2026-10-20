@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m hostel_cooling serve
) else (
  python -m hostel_cooling serve
)
pause
