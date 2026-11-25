@echo off
REM Turns off automatic exports: stops the watcher and removes it from Windows startup.
cd /d "%~dp0"
python mtga_auto_export.py --uninstall
echo.
pause
