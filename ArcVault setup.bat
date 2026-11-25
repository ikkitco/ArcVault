@echo off
REM One-time setup for the ArcVault window: installs pywebview, pystray and pillow and adds ArcVault shortcuts.
cd /d "%~dp0"
echo Installing the ArcVault window components (pywebview, pystray, pillow)...
python -m pip install --upgrade pywebview pystray pillow
if errorlevel 9009 (
  echo Python not found. Install it from python.org and tick "Add python.exe to PATH".
  goto end
)
if errorlevel 1 (
  echo.
  echo The install failed - copy the messages above to Claude.
  goto end
)
echo.
python arcvault_app.py --shortcut
echo.
echo Done. Opening ArcVault...
start "" "%~dp0ArcVault.lnk"
:end
echo.
pause
