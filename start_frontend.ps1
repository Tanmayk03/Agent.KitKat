# 🍫 Agent KitKat - Frontend Launcher
# Launches Vite development server on port 5173 with 0.0.0.0 host binding

Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "🍫 AGENT KITKAT - FRONTEND DEV SERVER LAUNCHER" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$scriptDir\frontend"

Write-Host "Starting Vite frontend with external LAN network exposure..." -ForegroundColor Cyan
npm run dev -- --host 0.0.0.0
