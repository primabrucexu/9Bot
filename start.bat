@echo off
setlocal

cd /d "%~dp0"

set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

set "HOST=127.0.0.1"
if defined NINEBOT_HOST set "HOST=%NINEBOT_HOST%"

set "PORT=8000"
if defined NINEBOT_PORT set "PORT=%NINEBOT_PORT%"

set "FRONTEND_HOST=127.0.0.1"
if defined NINEBOT_FRONTEND_HOST set "FRONTEND_HOST=%NINEBOT_FRONTEND_HOST%"

set "FRONTEND_PORT=5173"
if defined NINEBOT_FRONTEND_PORT set "FRONTEND_PORT=%NINEBOT_FRONTEND_PORT%"

set "BOOTSTRAP_PYTHON=python"
where py >nul 2>nul
if %errorlevel% equ 0 set "BOOTSTRAP_PYTHON=py -3"

if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    echo [9Bot] Creating backend virtual environment...
    %BOOTSTRAP_PYTHON% -m venv "%BACKEND_DIR%\.venv"
    if errorlevel 1 goto :error
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [9Bot] npm is required to run the frontend.
    goto :error
)

echo [9Bot] Installing backend dependencies...
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 goto :error

echo [9Bot] Installing frontend dependencies...
npm install --prefix "%FRONTEND_DIR%"
if errorlevel 1 goto :error

echo [9Bot] Starting backend API at http://%HOST%:%PORT%
start "9Bot Backend" cmd /c "cd /d ""%BACKEND_DIR%"" && set NINEBOT_HOST=%HOST% && set NINEBOT_PORT=%PORT% && ""%BACKEND_DIR%\.venv\Scripts\python.exe"" -m app.main"
if errorlevel 1 goto :error

echo [9Bot] Starting frontend at http://%FRONTEND_HOST%:%FRONTEND_PORT%
set "VITE_API_BASE_URL=http://%HOST%:%PORT%/api"
npm run dev --prefix "%FRONTEND_DIR%" -- --host %FRONTEND_HOST% --port %FRONTEND_PORT%
if errorlevel 1 goto :error

goto :eof

:error
echo [9Bot] Startup failed.
exit /b 1
