@echo off
echo ============================================================
echo    Starting Vite Frontend (React on :5173)
echo ============================================================
echo.

echo [1] Killing old Node processes...
taskkill /F /IM node.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul
echo     Done
echo.

if exist "C:\Program Files\nodejs" set PATH=C:\Program Files\nodejs;%PATH%
cd /d "%~dp0"

if not exist "node_modules" (
    echo [2] node_modules not found. Running npm install...
    call npm install
    echo.
) else (
    echo [2] node_modules already exists. Skipping npm install.
    echo     ^(If dependencies look broken, delete node_modules and rerun.^)
    echo.
)

echo ============================================================
echo [3] Starting Vite dev server...
echo     Frontend: http://localhost:5173
echo     Proxy /api and /socket.io -^> http://127.0.0.1:8000
echo ============================================================
echo.

call npm run dev

echo.
echo ============================================================
echo Vite dev server stopped.
echo ============================================================
pause
