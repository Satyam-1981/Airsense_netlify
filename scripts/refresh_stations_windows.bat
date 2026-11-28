@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo AtmoIQ virtual environment not found. Create .venv and install requirements first.
  exit /b 1
)
".venv\Scripts\python.exe" backend\manage.py refresh_station_network
exit /b %ERRORLEVEL%
