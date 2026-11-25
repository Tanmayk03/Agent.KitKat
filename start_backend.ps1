# 🍫 Agent KitKat - Backend Launcher
# Launches the FastAPI backend on port 8000.
# Default: listens on 127.0.0.1 only. Your iPhone reaches the API through the Vite dev
# server proxy (http://<laptop-ip>:5173). Use -Lan only if you need direct LAN access
# to port 8000 (e.g. the /ui production build from your phone).
param([switch]$Lan)

Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "🍫 AGENT KITKAT - BACKEND SERVER LAUNCHER" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Check Ollama
Write-Host "[1/2] Checking local Ollama AI daemon (http://127.0.0.1:11434)..." -ForegroundColor Cyan
try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
    $modelNames = $res.models | ForEach-Object { $_.name }
    Write-Host "✅ Ollama is running. Models available: $($modelNames -join ', ')" -ForegroundColor Green
    if ($modelNames -notcontains "qwen2.5:1.5b") {
        Write-Warning "Model 'qwen2.5:1.5b' not found in Ollama. Pulling model..."
        ollama pull qwen2.5:1.5b
    }
} catch {
    Write-Warning "⚠️ Ollama is not running on http://127.0.0.1:11434!"
    Write-Host "Starting Ollama in background..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 3
}

# Run FastAPI backend with Uvicorn
$bindHost = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
Write-Host "[2/2] Launching Agent KitKat FastAPI Backend on ${bindHost}:8000..." -ForegroundColor Cyan
if ($Lan) { Write-Warning "LAN mode: anyone on this Wi-Fi can reach the API (no login yet). Use only on a trusted network." }
Write-Host "Endpoints:" -ForegroundColor White
Write-Host "  - API & Swagger Docs: http://127.0.0.1:8000/docs" -ForegroundColor Gray
Write-Host "  - Health Check:       http://127.0.0.1:8000/api/health" -ForegroundColor Gray
Write-Host "  - Built Frontend UI:  http://127.0.0.1:8000/ui" -ForegroundColor Gray
Write-Host ""

& "$scriptDir\venv\Scripts\uvicorn.exe" backend.main:app --host $bindHost --port 8000 --reload
