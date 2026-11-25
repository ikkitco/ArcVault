@echo off
setlocal
REM ArcVault build (installer plan, steps 3 and 4).
REM Makes dist\ArcVault: ArcVault.exe (every part of ArcVault in one exe) + the reader + the page,
REM then packs it into dist\ArcVault-Setup-<version>.exe with Inno Setup.
REM Your normal ArcVault folder isn't changed.
cd /d "%~dp0"
set "VER=0.5.1"
set "OUT=%~dp0dist\ArcVault"
echo.
echo ==== ArcVault build %VER% ====
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install it from python.org and tick "Add python.exe to PATH".
  goto fail
)
python --version

echo.
echo [1/5] Build tools (Nuitka) and ArcVault's components...
python -m pip install --upgrade nuitka ordered-set zstandard pywebview pystray pillow
if errorlevel 1 goto fail

echo.
echo [2/5] The reader (mtga-tracker-daemon, from your fork in the daemon folder)...
if not exist "daemon\src\mtga-tracker-daemon\mtga-tracker-daemon.csproj" (
  echo The daemon folder is missing. Clone your mtga-tracker-daemon fork into it first.
  goto fail
)
where dotnet >nul 2>nul
if errorlevel 1 (
  echo No .NET SDK found. In a terminal:  winget install Microsoft.DotNet.SDK.8
  goto fail
)
taskkill /im mtga-tracker-daemon.exe /f >nul 2>nul
if exist "build\daemon" rmdir /s /q "build\daemon"
dotnet publish daemon\src\mtga-tracker-daemon -c Release -r win-x64 --self-contained -o build\daemon
if errorlevel 1 goto fail

echo.
echo [3/5] Compiling ArcVault.exe with Nuitka.
echo       The first time, Nuitka may ask to download a C compiler - this script says yes.
echo       First build: 5-20 minutes. Later builds are quicker.
python -m nuitka --mode=standalone --assume-yes-for-downloads ^
  --windows-console-mode=attach ^
  --windows-icon-from-ico=brand\arcvault.ico ^
  --enable-plugin=pywebview ^
  --include-module=arcvault_app --include-module=mtga_auto_export --include-module=mtga_collection_export ^
  --include-module=mtga_site_exports --include-module=arcvault_migrate ^
  --include-data-files=ArcVault.html=ArcVault.html ^
  --include-data-files=brand\arcvault.ico=brand\arcvault.ico ^
  --company-name=iKkitco --product-name=ArcVault --file-description=ArcVault ^
  --file-version=%VER% --product-version=%VER% ^
  --output-dir=build --output-filename=ArcVault.exe ^
  arcvault.py
if errorlevel 1 goto fail

echo.
echo [4/5] Putting it together in dist\ArcVault...
taskkill /im ArcVault.exe /f >nul 2>nul
if exist "%OUT%" rmdir /s /q "%OUT%"
robocopy "build\arcvault.dist" "%OUT%" /e /nfl /ndl /njh /njs /np >nul
if errorlevel 8 goto fail
robocopy "build\daemon" "%OUT%\daemon" /e /nfl /ndl /njh /njs /np >nul
if errorlevel 8 goto fail
REM the marker that makes this copy use Documents\ArcVault and AppData (installed mode)
type nul > "%OUT%\arcvault.installed"
copy /y "README.md" "%OUT%\README.md" >nul
copy /y "daemon\LICENSE" "%OUT%\daemon\LICENSE-mtga-tracker-daemon.txt" >nul
REM ArcVault's own licence (GPL v3), the third-party notices, and the licence files of every
REM bundled Python part (collected from this PC's Python packages into licenses\)
copy /y "LICENSE" "%OUT%\LICENSE.txt" >nul
copy /y "THIRD_PARTY_NOTICES.md" "%OUT%\THIRD_PARTY_NOTICES.md" >nul
python tools\collect_licences.py "%OUT%\licenses"
if errorlevel 1 goto fail
REM Microsoft's WebView2 bootstrapper, also kept inside the program so ArcVault can offer a repair
REM if WebView2 is broken on a PC.
if not exist "installer\MicrosoftEdgeWebview2Setup.exe" (
  echo Downloading Microsoft's WebView2 bootstrapper...
  curl -L -s -o "installer\MicrosoftEdgeWebview2Setup.exe" "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
  if errorlevel 1 goto fail
)
mkdir "%OUT%\redist" >nul 2>nul
copy /y "installer\MicrosoftEdgeWebview2Setup.exe" "%OUT%\redist\MicrosoftEdgeWebview2Setup.exe" >nul
if not exist "%OUT%\ArcVault.exe" goto fail
if not exist "%OUT%\daemon\mtga-tracker-daemon.exe" goto fail

echo.
echo [5/5] Packing the installer with Inno Setup...
set "ISCC="
for %%p in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist %%p set "ISCC=%%~p"
)
if not defined ISCC (
  for /f "delims=" %%p in ('where iscc 2^>nul') do set "ISCC=%%p"
)
if not defined ISCC (
  echo Inno Setup isn't installed, so no installer this time - dist\ArcVault is still ready.
  echo To get the installer:  winget install JRSoftware.InnoSetup   then run build.bat again.
  goto done
)
REM Microsoft's WebView2 bootstrapper (about 2 MB; Microsoft allows shipping it). The installer only
REM runs it on PCs that don't have WebView2 yet.
if not exist "installer\MicrosoftEdgeWebview2Setup.exe" (
  echo Downloading Microsoft's WebView2 bootstrapper...
  curl -L -s -o "installer\MicrosoftEdgeWebview2Setup.exe" "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
  if errorlevel 1 goto fail
)
if exist "dist\ArcVault-Setup-%VER%.exe" del /q "dist\ArcVault-Setup-%VER%.exe"
"%ISCC%" /Q /DAppVersion=%VER% "installer\ArcVault.iss"
if errorlevel 1 goto fail
if not exist "dist\ArcVault-Setup-%VER%.exe" goto fail
echo Installer: dist\ArcVault-Setup-%VER%.exe

:done
echo.
echo ==== SUCCESS ====
echo   dist\ArcVault                    the program (test it with ARCVAULT_SANDBOX, see the chat)
if exist "dist\ArcVault-Setup-%VER%.exe" echo   dist\ArcVault-Setup-%VER%.exe   the installer
echo.
pause
exit /b 0

:fail
echo.
echo ==== BUILD STOPPED ====
echo Copy everything above (or the last screenful) and send it over.
echo If Nuitka says it needs a C compiler / Visual Studio, install the free Build Tools:
echo     winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
echo then run build.bat again.
echo.
pause
exit /b 1
