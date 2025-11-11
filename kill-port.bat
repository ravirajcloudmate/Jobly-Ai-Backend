@echo off
REM Kill process using port 8001
echo Finding process on port 8001...
netstat -ano | findstr :8001

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo.
    echo Killing process PID: %%a
    taskkill /PID %%a /F
    echo Process killed!
)

echo.
echo You can now start the server again with: python server.py
pause

