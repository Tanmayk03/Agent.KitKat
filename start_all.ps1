# Agent KitKat - start everything and wait until it is really up.
#
#   start.bat  (double-click)  or  .\start_all.ps1 [-NoBrowser]
#
# Opens two windows (backend, frontend), waits for each to answer, then opens the app.
# The backend listens on this computer only; your phone connects through the frontend
# window and needs the access code (Settings > Phone access). Stop with stop.bat.

param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Wait-Url($url, $seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "  AGENT KITKAT" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Yellow

$venvPy = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy) -or -not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "Agent KitKat is not installed yet. Run install.bat first." -ForegroundColor Red
    exit 1
}

# 1. Ollama (optional: without it, drafts use simple templates)
Write-Host "[1/3] Local AI (Ollama)..." -ForegroundColor Cyan
$ollama = $false
try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null; $ollama = $true } catch { }
if (-not $ollama -and (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
    $ollama = Wait-Url "http://127.0.0.1:11434/api/tags" 15
}
if ($ollama) { Write-Host "      Ollama is running." -ForegroundColor Green }
else { Write-Host "      Ollama is not running; cover letters will use templates until you start it." -ForegroundColor Yellow }

# 2. Backend
Write-Host "[2/3] Backend (http://127.0.0.1:8000)..." -ForegroundColor Cyan
if (Wait-Url "http://127.0.0.1:8000/api/health" 1) {
    Write-Host "      Already running." -ForegroundColor Green
} else {
    Start-Process cmd.exe -ArgumentList "/k", "title Agent KitKat backend && set `"PYTHONUTF8=1`" && cd /d `"$root`" && `"$venvPy`" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
    if (Wait-Url "http://127.0.0.1:8000/api/health" 90) { Write-Host "      Backend is up." -ForegroundColor Green }
    else {
        Write-Host "      The backend did not start within 90 s. Check the backend window and storage\logs\agent_kitkat.log" -ForegroundColor Red
        exit 1
    }
}

# 3. Frontend (also serves your phone over Wi-Fi)
Write-Host "[3/3] Frontend (http://localhost:5173)..." -ForegroundColor Cyan
if (Wait-Url "http://localhost:5173/" 1) {
    Write-Host "      Already running." -ForegroundColor Green
} else {
    Start-Process cmd.exe -ArgumentList "/k", "title Agent KitKat frontend && cd /d `"$root\frontend`" && npm run dev"
    if (Wait-Url "http://localhost:5173/" 60) { Write-Host "      Frontend is up." -ForegroundColor Green }
    else {
        Write-Host "      The frontend did not start within 60 s. Check the frontend window." -ForegroundColor Red
        exit 1
    }
}

$phone = ""
try { $phone = (Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/network/info" -TimeoutSec 3).mobile_access_url } catch { }

Write-Host ""
Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "  Agent KitKat is running." -ForegroundColor Green
Write-Host "  On this computer: http://localhost:5173"
if ($phone) { Write-Host "  On your phone:    $phone  (pair it in Settings > Phone access)" }
Write-Host "  Logs:             storage\logs\agent_kitkat.log"
Write-Host "  Stop:             stop.bat"
Write-Host "==================================================" -ForegroundColor Yellow
if (-not $NoBrowser) { Start-Process "http://localhost:5173/" }
