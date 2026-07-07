@echo off
echo === Hyperspec Setup ^& Run Script ===

REM 1. Build frontend if it doesn't exist
IF NOT EXIST "frontend\dist" (
    echo [1/3] Building frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
) ELSE (
    echo [1/3] Frontend already built. Skipping...
)

REM 2. Setup Python Virtual Environment
IF NOT EXIST "venv" (
    echo [2/3] Creating Python virtual environment...
    python -m venv venv
)

echo [3/3] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
call pip install -r requirements.txt

echo.
echo ===========================================================
echo    All set! Starting Hyperspec server on port 8080...      
echo    Open http://localhost:8080 in your browser.             
echo    Press Ctrl+C to stop the server.                        
echo ===========================================================
echo.

python app.py
pause
