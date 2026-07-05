@echo off
setlocal
echo ============================================================
echo    EIS Agent Platform - One-click launch (backend + frontend)
echo ============================================================
echo.
echo  This opens TWO windows:
echo    - FastAPI backend  (uvicorn :8000)
echo    - Vite frontend    (React  :5173, proxies /api + /socket.io -^> :8000)
echo  Both must stay open. Close either window to stop that server.
echo.

REM --- 1) Launch backend in its own window ---------------------------------
echo [1] Launching backend window (START_BACKEND.bat)...
start "EIS Backend :8000" cmd /k "%~dp0START_BACKEND.bat"

REM --- 2) Wait for backend /health to come up -----------------------------
echo [2] Waiting for backend health at http://127.0.0.1:8000/health ...
set /a _tries=0
:waithealth
set /a _tries+=1
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8000/health 2>nul | findstr "200" >nul
if %errorlevel%==0 goto healthy
if %_tries% GEQ 40 (
    echo     [warn] backend not healthy after ~40s; launching frontend anyway.
    goto launchfe
)
timeout /t 1 /nobreak >nul
goto waithealth
:healthy
echo     Backend healthy.

REM --- 3) Launch frontend in its own window -------------------------------
:launchfe
echo [3] Launching frontend window (START_FRONTEND.bat)...
start "EIS Frontend :5173" cmd /k "%~dp0START_FRONTEND.bat"

REM --- 4) Wait for the dev server, then open the browser ------------------
echo [4] Waiting for frontend at http://127.0.0.1:5173 ...
set /a _tries=0
:waitfe
set /a _tries+=1
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:5173 2>nul | findstr /r "200 304" >nul
if %errorlevel%==0 goto feup
if %_tries% GEQ 60 (
    echo     [warn] frontend not detected after ~60s; open http://127.0.0.1:5173 manually.
    goto done
)
timeout /t 1 /nobreak >nul
goto waitfe
:feup
echo     Frontend up. Opening browser...
start "" http://127.0.0.1:5173

:done
echo.
echo ============================================================
echo  Launched. Backend + Frontend run in their own windows.
echo  Tip: in the UI, the top bar should show "WebSocket connected".
echo       "Controller offline" is normal until you connect the
echo       hardware controller on the Control page.
echo ============================================================
echo.
echo (This launcher window can be closed; the two servers keep running.)
pause
endlocal
