@echo off
REM Script to view agent logs

echo ==================================
echo 📋 Agent Log Viewer
echo ==================================
echo.

if not exist "agent.log" (
    echo ❌ No agent.log file found!
    echo.
    echo This means either:
    echo   1. The agent hasn't been started yet
    echo   2. The agent was started before logging to file was enabled
    echo.
    echo 💡 To enable logging:
    echo   - Run: start-agent.bat
    echo   - Logs will be saved to agent.log
    echo.
    pause
    exit /b 1
)

echo 📄 Showing last 50 lines of agent.log:
echo ==================================
echo.

powershell -Command "Get-Content agent.log -Tail 50"

echo.
echo ==================================
echo.
echo 💡 To view live logs, run:
echo    powershell -Command "Get-Content agent.log -Wait -Tail 20"
echo.
pause
