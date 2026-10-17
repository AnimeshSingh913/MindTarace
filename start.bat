@echo off
setlocal
cd /d "%~dp0"
echo Starting MindTrace...

if /I "%1"=="mock" (
    set MINDTRACE_MOCK_LLM=true
    echo Mock mode: canned answers, Ollama not required.
) else (
    where ollama >nul 2>nul || echo [warning] Ollama not found on PATH. Install it, or run: start.bat mock
)

if not exist "frontend\node_modules\" (
    echo Installing frontend dependencies...
    call npm --prefix frontend install
)

python -c "import fastapi, uvicorn, httpx" 2>nul || (
    echo Installing backend dependencies...
    python -m pip install -r backend\requirements.txt
)

start "MindTrace API" cmd /k "cd /d "%~dp0backend" && python -m uvicorn mindtrace.main:app --reload --port 8000"
start "MindTrace Web" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo   API: http://127.0.0.1:8000/docs
echo   App: http://localhost:5173
endlocal
