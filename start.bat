@echo off
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set VENV=%SCRIPT_DIR%.venv
set BACKEND=%SCRIPT_DIR%backend
set ENV_FILE=%BACKEND%\.env

:: ── Virtualenv ──────────────────────────────────────────────────────────────
if not exist "%VENV%\Scripts\python.exe" (
    echo [setup] Creating virtualenv...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [error] Failed to create virtualenv. Is Python 3.10+ installed and on PATH?
        pause
        exit /b 1
    )
)

:: ── Dependencies ────────────────────────────────────────────────────────────
echo [setup] Installing dependencies...
"%VENV%\Scripts\pip.exe" install -q -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
    echo [error] pip install failed.
    pause
    exit /b 1
)

:: ── .env ────────────────────────────────────────────────────────────────────
if not exist "%ENV_FILE%" (
    echo [setup] No .env found -- copying from .env.example
    copy "%BACKEND%\.env.example" "%ENV_FILE%" >nul
    echo.
    echo   Edit %ENV_FILE% and set FOOTAGE_DIR, DB_PATH, and CACHE_DIR
    echo   then re-run this script.
    echo.
    pause
    exit /b 1
)

:: Load env vars from backend\.env (skip comment lines)
for /f "usebackq tokens=* eol=#" %%L in ("%ENV_FILE%") do (
    set "%%L"
)

if not defined PORT set PORT=8090
if not defined SHINOBI_CONTAINER set SHINOBI_CONTAINER=shinobi

:: ── Wait for Shinobi container ────────────────────────────────────────────────
echo [docker] Waiting for Shinobi container '%SHINOBI_CONTAINER%'...
set /a MAX_WAIT=120
set /a INTERVAL=5
set /a elapsed=0
set /a iterations=0

:wait_loop
docker inspect --format={{.State.Status}} %SHINOBI_CONTAINER% 2>nul | findstr /c:"running" >nul
if %errorlevel%==0 (
    echo [docker] Shinobi container is running.
    goto :shinobi_ready
)
if !elapsed! geq %MAX_WAIT% (
    echo [docker] Timeout: Shinobi container did not start within %MAX_WAIT%s. Aborting.
    pause
    exit /b 1
)
echo [docker] Not running yet (!elapsed!s elapsed). Retrying in %INTERVAL%s...
timeout /t %INTERVAL% /nobreak >nul
set /a elapsed+=INTERVAL
goto :wait_loop

:shinobi_ready
if not defined STATUS_PORT set /a STATUS_PORT=%PORT%+1
echo [start] Shinobi Light Viewer -^> http://localhost:%PORT%
echo [start] Status page           -^> http://localhost:%STATUS_PORT%
"%VENV%\Scripts\python.exe" "%SCRIPT_DIR%supervisor\supervisor.py"
