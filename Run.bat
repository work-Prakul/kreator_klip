@echo off
echo ==================================================
echo         KreatorKlip (Flet) Setup Launcher
echo ==================================================

:: 1. CHECK FOR PYTHON
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)
echo [OK] Python is installed.

:: 2. VIRTUAL ENVIRONMENT
if not exist "venv\" (
    echo Creating Python Virtual Environment...
    python -m venv venv
)

echo Activating environment...
call venv\Scripts\activate.bat

echo Installing Flet and Machine Learning dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Launching KreatorKlip...
python main.py

pause
