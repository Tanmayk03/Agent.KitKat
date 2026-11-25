@echo off
title Agent KitKat - Launcher
echo ==================================================
echo   AGENT KITKAT - LOCAL AUTONOMOUS CAREER ASSISTANT
echo ==================================================
echo.

:: 1. Check Ollama
echo [1/3] Checking Ollama AI status...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Ollama is not responding at http://127.0.0.1:11434
    echo Please make sure Ollama is running and has model 'qwen2.5:1.5b' loaded.
    echo.
) else (
    echo [OK] Ollama is active.
)

:: 2. Launch FastAPI Backend in a new terminal
echo [2/3] Launching FastAPI Backend on port 8000...
start "Agent KitKat Backend (Port 8000)" cmd /k "cd /d "%~dp0" && .\venv\Scripts\activate.bat && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: 3. Launch Vite Frontend dev server in a new terminal
echo [3/3] Launching React Frontend on port 5173...
start "Agent KitKat Frontend (Port 5173)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: Wait 3 seconds then open browser
timeout /t 3 /nobreak >nul
start http://localhost:5173/

echo.
echo ==================================================
echo   Agent KitKat is running!
echo   Frontend: http://localhost:5173/
echo   Backend:  http://127.0.0.1:8000/docs
echo ==================================================
pause
