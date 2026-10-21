@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open-project.ps1" %*
if errorlevel 1 (
  echo.
  echo Project could not open. Read the message above.
  pause
  exit /b 1
)
