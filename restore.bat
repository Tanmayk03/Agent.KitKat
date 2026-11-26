@echo off
:: Agent KitKat - restore a backup.
:: Usage: restore.bat                 (lists backups, then asks which one)
::        restore.bat <backup.zip>
:: Stop Agent KitKat first (stop.bat). Your current data is saved as a "pre-restore" backup.
cd /d "%~dp0"
call .\venv\Scripts\activate.bat
set "BACKUP=%~1"
if "%BACKUP%"=="" (
    python -m backend.maintenance.backup list
    echo.
    set /p "BACKUP=Backup file name to restore: "
)
if "%BACKUP%"=="" (
    echo Nothing chosen.
    pause
    exit /b 1
)
python -m backend.maintenance.backup restore "%BACKUP%"
pause
