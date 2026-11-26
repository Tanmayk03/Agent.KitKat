@echo off
:: Agent KitKat - start the backend and frontend, wait until both answer, open the app.
:: First time? Run install.bat. Stop with stop.bat.
title Agent KitKat - Launcher
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1" %*
if errorlevel 1 (
    echo.
    echo Agent KitKat did not start. See the messages above.
)
pause
