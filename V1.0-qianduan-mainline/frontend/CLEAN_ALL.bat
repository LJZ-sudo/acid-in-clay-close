@echo off
echo ============================================================
echo    Cleaning All Processes (FastAPI + Vite)
echo ============================================================
echo.

echo [1] Killing Python processes (FastAPI / uvicorn)...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
echo     Done

echo [2] Killing Node processes (Vite)...
taskkill /F /IM node.exe >nul 2>&1
echo     Done

echo [3] Releasing common ports (8000 / 5173)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
echo     Done

echo.
echo ============================================================
echo Cleanup complete!
echo.
echo Now you can restart:
echo   1. Double-click START_BACKEND.bat
echo   2. Double-click START_FRONTEND.bat
echo   3. Open http://localhost:5173
echo ============================================================
pause
