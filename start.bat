@echo off
setlocal

cd /d "%~dp0"

set "HOST=127.0.0.1"
if defined NINEBOT_HOST set "HOST=%NINEBOT_HOST%"

set "PORT=8000"
if defined NINEBOT_PORT set "PORT=%NINEBOT_PORT%"

set "BOOTSTRAP_PYTHON=python"
where py >nul 2>nul
if %errorlevel% equ 0 set "BOOTSTRAP_PYTHON=py -3"

if not exist ".venv\Scripts\python.exe" (
    echo [9Bot] Creating virtual environment...
    %BOOTSTRAP_PYTHON% -m venv ".venv"
    if errorlevel 1 goto :error
)

echo [9Bot] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
if errorlevel 1 goto :error

echo [9Bot] Starting server at http://%HOST%:%PORT%
".venv\Scripts\python.exe" -m uvicorn app.main:app --host "%HOST%" --port "%PORT%" --reload
if errorlevel 1 goto :error

goto :eof

:error
echo [9Bot] Startup failed.
exit /b 1
