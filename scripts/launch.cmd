@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0.."
title Hanoi Signal - %~1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "%~dp0launch.py" %~1 %2 %3
    goto finished
)

py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3.11 "%~dp0launch.py" %~1 %2 %3
    goto finished
)

py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0launch.py" %~1 %2 %3
    goto finished
)

python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    python "%~dp0launch.py" %~1 %2 %3
    goto finished
)

echo Python 3.11 or later was not found.
echo Install Python with pip and the Python launcher, then double-click again.
pause
exit /b 1

:finished
if errorlevel 1 (
    echo.
    echo Startup failed. Read the message above before closing this window.
    pause
    exit /b 1
)
exit /b 0
