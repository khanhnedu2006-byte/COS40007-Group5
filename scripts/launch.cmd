@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0.."
title Hanoi Signal - %~1

rem Choose this computer's Python, not a virtual environment copied from another PC.
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

python3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    python3 "%~dp0launch.py" %~1 %2 %3
    goto finished
)

rem A working local environment is a fallback when Python is not on PATH.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
    if not errorlevel 1 (
        ".venv\Scripts\python.exe" "%~dp0launch.py" %~1 %2 %3
        goto finished
    )
)

echo Python 3.11 or later was not found.
echo Python 3.14 is supported. Install 64-bit Python with pip and add it to PATH.
echo You can also install the Python launcher, then double-click again.
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
