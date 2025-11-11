@echo off
REM Quick Start Script for Backend Server (Windows)
REM This starts only the backend API server on port 8001

echo ==================================
echo 🚀 Starting Backend Server
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
        echo ⚠️  Please edit .env and add your credentials:
        echo     - LIVEKIT_URL
        echo     - LIVEKIT_API_KEY
        echo     - LIVEKIT_API_SECRET
        echo     - OPENAI_API_KEY
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

REM Check if httpx is installed (needed for agent communication)
pip install httpx >nul 2>&1

echo.
echo ==================================
echo ✅ Starting Backend Server on port 8001
echo ==================================
echo.
echo 📍 Server will run at: http://localhost:8001
echo 📍 Health check: http://localhost:8001/health
echo.
echo 🛑 Press Ctrl+C to stop the server
echo ==================================
echo.

REM Start the server with auto-reload
echo.
echo 🔄 Server will auto-reload on file changes
python server.py

REM Deactivate virtual environment when done
deactivate

