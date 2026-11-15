# ðŸ« Agent KitKat - Master All-in-One Launcher
# Starts Ollama check, Backend server, and Frontend dev server in separate windows

Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "ðŸ« AGENT KITKAT - AUTONOMOUS AI CAREER ASSISTANT" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 1. Verify Ollama
Write-Host "[1/3] Checking Ollama daemon..." -ForegroundColor Cyan
try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
    Write-Host "âœ… Ollama is online." -ForegroundColor Green
} catch {
    Write-Host "Starting Ollama serve..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 3
}

# 2. Launch Backend
Write-Host "[2/3] Starting Backend Server (FastAPI on port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start_backend.ps1"

Start-Sleep -Seconds 2

# 3. Launch Frontend
Write-Host "[3/3] Starting Frontend Dev Server (Vite on port 5173)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start_frontend.ps1"

Write-Host ""
Write-Host "ðŸŽ‰ Agent KitKat services are running!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "ðŸ’» Local Web Dashboard:   http://localhost:5173" -ForegroundColor White
Write-Host "ðŸ“¦ Production UI (FastAPI): http://127.0.0.1:8000/ui" -ForegroundColor White
Write-Host "ðŸ“– Interactive API Docs:  http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "ðŸ“± iPhone PWA Access:     http://172.20.10.4:5173" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "Press any key to exit this launcher window..."
Read-Host "Press Enter to close this window"

