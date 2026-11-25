@echo off
REM Turns on automatic exports: starts with Windows, and starts now.
REM While MTG Arena is open, your collection is exported every 15 minutes.
cd /d "%~dp0"
python mtga_auto_export.py --install
if errorlevel 9009 echo Python not found. Install it from python.org and tick "Add python.exe to PATH".
echo.
pause
