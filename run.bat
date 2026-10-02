@echo off
title PoshanScan Backend Server
echo ========================================================
echo         Starting PoshanScan FastAPI Backend...
echo ========================================================
echo.
cd /d "%~dp0"

:: Check if seed data exists or initialize
if not exist "poshanscan.db" (
    echo [INFO] Database not found. Running seed script...
    python seed.py
    echo.
)

echo [INFO] Server starting at http://127.0.0.1:8000
echo [INFO] API Docs available at http://127.0.0.1:8000/docs
echo.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
