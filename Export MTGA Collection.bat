@echo off
REM Double-click to export your MTG Arena collection.
REM Arena must be running and logged in. The daemon is auto-started if
REM mtga-tracker-daemon.exe is anywhere inside this folder.
cd /d "%~dp0"
set MTGA_PAUSE=1
python mtga_collection_export.py %*
if errorlevel 9009 (
  echo.
  echo Python not found. Install it from python.org and tick "Add python.exe to PATH".
  pause
)
