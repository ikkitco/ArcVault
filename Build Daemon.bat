@echo off
REM Builds mtga-tracker-daemon from the source in the "daemon" folder.
cd /d "%~dp0daemon"
if not exist "src\mtga-tracker-daemon\mtga-tracker-daemon.csproj" (
  echo Can't find daemon\src\mtga-tracker-daemon\mtga-tracker-daemon.csproj
  echo Put the mtga-tracker-daemon source code in a folder called "daemon" next to this file.
  pause
  exit /b 1
)
where dotnet >nul 2>nul
if not "%errorlevel%"=="0" goto nosdk

REM Is there any SDK at all? (a runtime-only install has dotnet.exe but no SDKs)
set "SDKS="
for /f "delims=" %%s in ('dotnet --list-sdks 2^>nul') do set "SDKS=1"
if not defined SDKS goto nosdk

echo Installed .NET SDKs:
dotnet --list-sdks
echo.
echo Stopping any running daemon (Windows won't replace a running .exe)...
taskkill /im mtga-tracker-daemon.exe /f >nul 2>nul
echo Building... (first build downloads packages, takes a minute)
dotnet publish src\mtga-tracker-daemon -c Release -r win-x64 --self-contained
if not "%errorlevel%"=="0" (
  echo.
  echo BUILD FAILED - copy the error text above and send it over.
  pause
  exit /b 1
)
echo.
if exist "src\mtga-tracker-daemon\bin\Release\net8.0\win-x64\publish\mtga-tracker-daemon.exe" (
  echo SUCCESS: daemon built. You can now run "Export MTGA Collection.bat".
) else (
  echo Build finished but the exe isn't where expected - search the daemon folder for mtga-tracker-daemon.exe
)
pause
exit /b 0

:nosdk
echo No .NET SDK is installed (you may only have the .NET runtime, which can't build code).
echo.
echo Install the .NET 8 SDK, then run this file again. Easiest way - in a terminal:
echo     winget install Microsoft.DotNet.SDK.8
echo Or download "SDK 8.0.x - Windows x64 installer" from https://dotnet.microsoft.com/download/dotnet/8.0
echo.
echo After installing, CLOSE this window and open a new one so dotnet is picked up.
pause
exit /b 1
