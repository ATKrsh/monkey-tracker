@echo off
:: Quick launcher for Monkey Tracker Pro
where py >nul 2>&1
if not errorlevel 1 (
    py main.py
    goto :eof
)
where python >nul 2>&1
if not errorlevel 1 (
    python main.py
    goto :eof
)
echo [ERROR] Python not found.
pause
