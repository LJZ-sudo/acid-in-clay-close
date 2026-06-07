@echo off
echo ============================================================
echo    Starting FastAPI Backend (uvicorn on :8000)
echo ============================================================
echo.

echo [1] Killing old Python / uvicorn processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul
echo     Done

REM frontend\..\  ->  V1.0-qianduan-mainline\
cd /d "%~dp0.."

echo [2] Cleaning Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc >nul 2>&1
echo     Done
echo.

echo [3] Workdir: %CD%
echo.

echo ============================================================
echo [4] Starting uvicorn (backend_api.main:app, port 8000)...
echo     Health check: http://127.0.0.1:8000/health
echo     API docs:     http://127.0.0.1:8000/docs
echo ============================================================
echo.

python -m uvicorn backend_api.main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo ============================================================
echo FastAPI backend stopped.
echo ============================================================
pause
