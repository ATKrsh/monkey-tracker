@echo off
echo ==========================================
echo   🐒 MONKEY TRACKER PRO — Setup Script
echo ==========================================
echo.

:: Detect Python launcher
where py >nul 2>&1
if not errorlevel 1 (
    set PYTHON=py
    goto :found_python
)
where python >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
    goto :found_python
)
echo [ERROR] Python not found. Please install Python 3.10+ from python.org
pause
exit /b 1

:found_python
%PYTHON% --version
echo.

echo [1/4] Creating virtual environment...
%PYTHON% -m venv .venv
call .venv\Scripts\activate.bat

echo [2/4] Upgrading pip...
%PYTHON% -m pip install --upgrade pip --quiet

echo [3/4] Installing dependencies (this may take a few minutes)...
pip install ultralytics PyQt6 opencv-python pyqtgraph numpy Pillow win11toast

echo [4/4] Creating data directory...
if not exist "data" mkdir data

echo.
echo ==========================================
echo   ✅ Setup complete!
echo   Run: run.bat   or   .venv\Scripts\python main.py
echo ==========================================
pause
