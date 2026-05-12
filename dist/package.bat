@echo off
setlocal

:: ============================================================
:: package.bat
:: Assembles the final distribution folder from both build outputs.
::
:: Output structure:
::   dist\output\
::     TTPHLauncher.exe  (+ launcher native dlls)
::     launcher.json
::     game\
::       TTPHEngine.exe  (+ game dlls, config, astron, etc.)
::
:: Phase files and settings.json are NOT included — the launcher
:: downloads them from Azure on first run.
:: ============================================================

set LAUNCHER_PUBLISH=%~dp0..\TTPHLauncher\bin\Release\net8.0-windows\win-x64\publish
set GAME_DIST=%~dp0..\build\PrivacyStart.dist
set OUT=%~dp0output

:: --- Validate inputs -----------------------------------------
if not exist "%LAUNCHER_PUBLISH%\TTPHLauncher.exe" (
    echo ERROR: Launcher publish not found. Run:
    echo   dotnet publish TTPHLauncher -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
    exit /b 1
)

if not exist "%GAME_DIST%\TTPHEngine.exe" (
    echo ERROR: Game dist not found at %GAME_DIST%
    echo Run build.bat first.
    exit /b 1
)

:: --- Clean output --------------------------------------------
echo Cleaning output folder...
if exist "%OUT%" rd /s /q "%OUT%"
mkdir "%OUT%"
mkdir "%OUT%\game"

:: --- Copy launcher files to root -----------------------------
echo Copying launcher files...
xcopy /e /i /q "%LAUNCHER_PUBLISH%\*" "%OUT%\"

:: --- Copy game files to game\ --------------------------------
echo Copying game files...
xcopy /e /i /q "%GAME_DIST%\*" "%OUT%\game\"

:: --- Remove patcher-managed files from game\ -----------------
:: Phase files, settings.json, and TTPHEngine.exe are all downloaded
:: by the launcher from Azure on first run — don't ship them in the zip.
echo Removing patcher-managed files (launcher downloads these from Azure)...
for %%f in ("%OUT%\game\*.mf") do del "%%f"
if exist "%OUT%\game\settings.json" del "%OUT%\game\settings.json"
if exist "%OUT%\game\TTPHEngine.exe" del "%OUT%\game\TTPHEngine.exe"

:: --- Done ----------------------------------------------------
echo.
echo Distribution folder ready: %OUT%
echo.
echo Contents:
dir /b "%OUT%"
echo.
echo game\ contents:
dir /b "%OUT%\game"

endlocal
