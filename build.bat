@echo off
setlocal enabledelayedexpansion
title TTPHEngine Build
cd /d "%~dp0"

echo ============================================================
echo  Toontown Porkheffley ^| TTPHEngine Build Script
echo ============================================================
echo.

:: ------------------------------------------------------------
:: Locate Python
:: Prefer Nuitka-Python if present (better codegen), fall back
:: to the dev venv which works fine for a first build.
:: ------------------------------------------------------------
set "PYTHON="

if exist "Nuitka-Python\output\python.exe" (
    set "PYTHON=Nuitka-Python\output\python.exe"
    echo [Python] Using Nuitka-Python: !PYTHON!
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    echo [Python] Nuitka-Python not found, using venv: !PYTHON!
    echo [Hint]   For a production build, download Nuitka-Python and place
    echo          it at Nuitka-Python\output\python.exe
) else (
    echo [ERROR] No Python found. Expected either:
    echo           Nuitka-Python\output\python.exe
    echo           .venv\Scripts\python.exe
    goto error
)

:: Check nuitka is installed
"%PYTHON%" -c "import nuitka" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Nuitka is not installed in this Python environment.
    echo         Run:  "%PYTHON%" -m pip install nuitka
    goto error
)

echo.

:: ------------------------------------------------------------
:: Step 1: Generate PrivacyMatters.py
:: Embeds config/private_client.prc and config/ttph.dc into
:: source so the exe doesn't need loose config files at runtime.
:: ------------------------------------------------------------
echo [1/4] Generating PrivacyMatters.py...
cd "dist\startup-modules\PrivacyMatters"
"%~dp0%PYTHON%" create-PrivacyMatters.py
if errorlevel 1 (
    cd /d "%~dp0"
    echo [ERROR] create-PrivacyMatters.py failed.
    goto error
)
cd /d "%~dp0"
echo       Done.
echo.

:: ------------------------------------------------------------
:: Step 2: Copy PrivacyStart.py to the project root
:: Nuitka compiles whatever .py is in the working directory.
:: PrivacyStart.py is gitignored at the root since it contains
:: the generated PrivacyMatters import.
:: ------------------------------------------------------------
echo [2/4] Copying PrivacyStart.py to project root...
copy /Y "dist\startup-modules\PrivacyStart.py" "PrivacyStart.py" >nul
if errorlevel 1 (
    echo [ERROR] Could not copy PrivacyStart.py.
    goto error
)
echo       Done.
echo.

:: ------------------------------------------------------------
:: Step 3: Generate files.py (hidden imports)
:: Nuitka can't trace Panda3D's dynamic module loading, so we
:: generate a file that explicitly imports everything. Nuitka
:: compiles it all in via --include-module=files.
:: ------------------------------------------------------------
echo [3/4] Generating files.py (hidden imports)...
if exist "files.py" del "files.py"
cd "dist\startup-modules\Find Hidden Imports"
"%~dp0%PYTHON%" create-files.py
if errorlevel 1 (
    cd /d "%~dp0"
    echo [ERROR] create-files.py failed.
    goto error
)
cd /d "%~dp0"
echo       Done.
echo.

:: ------------------------------------------------------------
:: Pre-Step: Locate VC++ runtime DLLs for bundling
::
:: concrt140.dll / msvcp140.dll / vcruntime140.dll are part of
:: the Visual C++ Redistributable. Nuitka needs to find them on
:: the build machine to bundle them into the standalone output.
::
:: Search order:
::   1. System32 (present if VC++ Redist is installed system-wide)
::   2. VS2022 redist tree  (present if VS2022 is installed)
::   3. VS2019 redist tree  (present if VS2019 is installed)
::
:: If none of these work, print the redist download link and
:: continue anyway — the exe still works on machines that already
:: have the runtime installed (most Windows PCs do).
:: ------------------------------------------------------------
echo [Pre] Locating VC++ runtime DLLs for bundling...
set "VCRT_FLAGS="

:: 1. Check System32 first (fastest path)
if exist "%SystemRoot%\System32\concrt140.dll" (
    echo       Found in System32 — will be auto-bundled by Nuitka.
    goto vcrt_done
)

:: 2. Search VS2022 installation for the x64 CRT redist folder
set "VCRT_DIR="
for /f "delims=" %%d in ('dir /b /s /ad "C:\Program Files\Microsoft Visual Studio\2022" 2^>nul ^| findstr /i "x64.*VC143\|VC143.*x64"') do (
    if exist "%%d\concrt140.dll" (
        set "VCRT_DIR=%%d"
        goto vcrt_found
    )
)

:: 3. Search VS2019 as fallback
for /f "delims=" %%d in ('dir /b /s /ad "C:\Program Files (x86)\Microsoft Visual Studio\2019" 2^>nul ^| findstr /i "x64.*VC142\|VC142.*x64"') do (
    if exist "%%d\concrt140.dll" (
        set "VCRT_DIR=%%d"
        goto vcrt_found
    )
)

:: Not found anywhere
echo       WARNING: concrt140.dll not found. The exe will require
echo       the VC++ Redistributable on the target machine.
echo       To fix: install it from https://aka.ms/vs/17/release/vc_redist.x64.exe
echo       then re-run this script.
echo.
goto vcrt_done

:vcrt_found
echo       Found VC++ redist at: !VCRT_DIR!
:: Pass each CRT DLL explicitly so Nuitka bundles them
for %%f in (concrt140.dll msvcp140.dll msvcp140_1.dll msvcp140_2.dll vcruntime140.dll vcruntime140_1.dll) do (
    if exist "!VCRT_DIR!\%%f" (
        set "VCRT_FLAGS=!VCRT_FLAGS! --include-data-files=!VCRT_DIR!\%%f=%%f"
    )
)
echo       Will bundle: concrt140 msvcp140 vcruntime140 (and variants).

:vcrt_done
echo.

:: ------------------------------------------------------------
:: Step 4: Run Nuitka
::
:: --standalone          Bundle Python runtime — no install needed on player machines
:: --python-flag=-O      Strip assert statements and docstrings (smaller output)
:: --include-module=files Force all game modules in via the generated files.py
:: --lto=no              LTO disabled — it greatly increases linker memory use and
::                       can cause C1002 "out of heap space" on large codebases.
::                       Re-enable once you have a working build if you want the
::                       size/speed benefit.
:: --low-memory          Splits large generated C files into smaller chunks so
::                       MSVC doesn't exhaust its heap on a single translation unit.
:: --output-dir=build    Write output to build\ instead of cluttering the root
:: --windows-console-mode=disable  Hide the terminal window when the game runs
:: --jobs=N              Parallel C compilation — uses all CPU cores
::
:: Omitting --msvc so Nuitka auto-detects the highest MSVC available.
:: The original command used --msvc=14.2 (VS2019); VS2022 is 14.3+.
:: ------------------------------------------------------------
:: Limit parallel jobs to half the CPU count.
:: Each MSVC instance needs significant heap for large generated C files.
:: Using all cores simultaneously causes C1002 "out of heap space" on
:: modules like Quests.py and OZSafeZoneLoader.py.
set /a BUILD_JOBS=%NUMBER_OF_PROCESSORS% / 2
if %BUILD_JOBS% LSS 1 set BUILD_JOBS=1

echo [4/4] Running Nuitka (this takes 10-30 minutes)...
echo       Using %BUILD_JOBS% of %NUMBER_OF_PROCESSORS% CPU cores to keep MSVC heap usage stable.
echo       Grab a coffee. Nuitka is compiling ~1000 Python files to C.
echo.

"%PYTHON%" -m nuitka ^
    --standalone ^
    --python-flag=-O ^
    --include-module=files ^
    --lto=no ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico="resources\phase_3\etc\icon.ico" ^
    --output-dir=build ^
    --jobs=%BUILD_JOBS% ^
    %VCRT_FLAGS% ^
    PrivacyStart.py

if errorlevel 1 (
    echo.
    echo [ERROR] Nuitka compilation failed. See output above.
    goto error
)

:: ------------------------------------------------------------
:: Post-process: rename exe to TTPHEngine.exe and clean up
:: linker artifacts that aren't needed at runtime.
:: ------------------------------------------------------------
echo.
echo [Post] Renaming exe...
if exist "build\PrivacyStart.dist\PrivacyStart.exe" (
    move /Y "build\PrivacyStart.dist\PrivacyStart.exe" "build\PrivacyStart.dist\TTPHEngine.exe" >nul
)
if exist "build\PrivacyStart.dist\PrivacyStart.exp" del "build\PrivacyStart.dist\PrivacyStart.exp"
if exist "build\PrivacyStart.dist\PrivacyStart.lib" del "build\PrivacyStart.dist\PrivacyStart.lib"

:: ------------------------------------------------------------
:: Write default settings.json
:: ToontownSettings reads this from the working directory. Without it,
:: auto-start-server defaults to True and the client tries to spin up
:: a local dedicated server instead of connecting to the game server.
:: ------------------------------------------------------------
echo [Post] Writing default settings.json...
(
    echo {
    echo   "game": {
    echo     "auto-start-server": false,
    echo     "mongodb-client": false,
    echo     "smoothanimations": true,
    echo     "elections": false,
    echo     "retro-rewritten": false
    echo   }
    echo }
) > "build\PrivacyStart.dist\settings.json"
echo       Done.

echo.
echo ============================================================
echo  Build complete!
echo  Output: build\PrivacyStart.dist\TTPHEngine.exe
echo ============================================================
echo.
echo Next steps:
echo   1. Copy phase_*.mf files into build\PrivacyStart.dist\
echo      (or point launcher.json CdnBaseUrl at your CDN and let
echo       the launcher download them automatically)
echo   2. Point TTPHLauncher's GameExecutable at TTPHEngine.exe
echo   3. Run TTPHEngine.exe --game  to test directly, or use
echo      the launcher which sets TTR_PLAYCOOKIE + TTR_GAMESERVER
echo.
goto end

:error
echo.
echo ============================================================
echo  BUILD FAILED
echo ============================================================
pause
exit /b 1

:end
pause
