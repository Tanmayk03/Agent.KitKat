# Agent KitKat - Master Launcher

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "==============================================" -ForegroundColor Yellow
Write-Host "       AGENT KITKAT - AI CAREER ASSISTANT" -ForegroundColor Yellow
Write-Host "==============================================" -ForegroundColor Yellow

# 1. Check Ollama
Write-Host "[1/3] Checking Ollama..." -ForegroundColor Cyan

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 | Out-Null
    Write-Host "Ollama is online." -ForegroundColor Green
}
catch {
    Write-Host "Starting Ollama..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 5
}

# 2. Start Backend
Write-Host "[2/3] Starting Backend..." -ForegroundColor Cyan

if (-not (Test-Path "$scriptDir\start_backend.ps1")) {
    throw "start_backend.ps1 was not found."
}

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "$scriptDir\start_backend.ps1"
)

Start-Sleep -Seconds 2

# 3. Start Frontend
Write-Host "[3/3] Starting Frontend..." -ForegroundColor Cyan

if (-not (Test-Path "$scriptDir\start_frontend.ps1")) {
    throw "start_frontend.ps1 was not found."
}

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "$scriptDir\start_frontend.ps1"
)

Write-Host ""
Write-Host "Agent KitKat startup commands launched." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:5173" -ForegroundColor White
Write-Host "API Docs:  http://127.0.0.1:8000/docs" -ForegroundColor White

Read-Host "Press Enter to close this launcher"
