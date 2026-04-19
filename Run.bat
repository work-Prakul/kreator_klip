@echo off
echo ==================================================
echo         KreatorKlip (Flet) Setup Launcher
echo ==================================================

:: 1. VIRTUAL ENVIRONMENT
if not exist "venv\" (
    echo Creating Python Virtual Environment...
    python -m venv venv
)

echo Installing dependencies into virtual environment...
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Launching KreatorKlip with the virtual environment Python...
.\venv\Scripts\python.exe main.py

pause
