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

if not defined PORT set PORT=8080

echo [start] Shinobi Light Viewer -^> http://localhost:%PORT%
cd /d "%BACKEND%"
"%VENV%\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port %PORT%
