@echo off
REM Quick Start Script for Agent Worker (Windows)
REM This starts the LiveKit agent worker

echo ==================================
echo 🤖 Starting Agent Worker
echo ==================================

REM Check if .env exists
if not exist ".env" (
    echo.
    echo ❌ Error: .env file not found!
    echo.
    echo Creating .env from template...
    if exist "env.template" (
        copy env.template .env >nul
        echo ✅ Created .env file from env.template
        echo.
        echo ⚠️  Please edit .env and add your credentials.
        echo.
        pause
        exit /b 1
    ) else (
        echo Please create .env file manually with your credentials.
        echo.
        pause
        exit /b 1
    )
)

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing dependencies...
pip install -q -r requirements.txt

echo.
echo ==================================
echo ✅ Starting Agent Worker
echo ==================================
echo.
echo 🤖 Agent will connect to LiveKit
echo 📝 Logs will be saved to: agent.log
echo 📝 Also displayed in console below
echo.
echo 🛑 Press Ctrl+C to stop the agent
echo ==================================
echo.

REM Start the agent and save logs to file (also display in console)
REM Using PowerShell to tee output to both console and file
powershell -Command "python agent.py dev 2>&1 | Tee-Object -FilePath agent.log"

REM Alternative: If you want logs only in file (not console), use:
REM python agent.py dev > agent.log 2>&1

REM Deactivate virtual environment when done
deactivate

