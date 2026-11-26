@echo off
:: Agent KitKat - make a backup of your database, resumes, applications and screenshots.
:: Safe while Agent KitKat is running. Backups go to storage\backups\
cd /d "%~dp0"
call .\venv\Scripts\activate.bat
python -m backend.maintenance.backup create --label manual
echo.
python -m backend.maintenance.backup list
pause
