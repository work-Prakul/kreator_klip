@echo off
echo ==================================================
echo         KreatorKlip MVP Setup Launcher
echo ==================================================
echo.

:: 1. CHECK FOR PYTHON
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.10+.
    pause
    exit /b 1
)
echo [OK] Python is installed.

:: 2. CHECK FOR FFMPEG
ffmpeg -version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] FFmpeg is not installed or not in PATH! Please install FFmpeg to run the Cutter Engine.
    pause
    exit /b 1
)
echo [OK] FFmpeg is installed.

:: 3. VIRTUAL ENVIRONMENT & PIP
echo.
echo Setting up Python Virtual Environment (venv)...
if not exist "venv\" (
    python -m venv venv
)

echo Activating environment and installing ML dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt


echo.
echo ==================================================
echo KreatorKlip Setup Complete. Ready for Highlight Execution!
echo ==================================================
pause
