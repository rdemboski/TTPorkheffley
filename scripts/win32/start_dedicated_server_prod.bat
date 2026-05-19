@echo off
title Toontown Porkheffley Dedicated Server [PROD]
cd ../../

rem Read the contents of PPYTHON_PATH into %PPYTHON_PATH%:
set /P PPYTHON_PATH=<PPYTHON_PATH

%PPYTHON_PATH% -O -m toontown.toonbase.DedicatedServerStart
pause
