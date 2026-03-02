@echo off
setlocal EnableDelayedExpansion

echo ---------------------------------------------------
echo Enterprise AI Knowledge Hub - BACKEND STARTING
echo ---------------------------------------------------

REM 1. Set Environment Variables
set "PYTHONPATH=%CD%"
set "PYTHONUTF8=1"
set "OLLAMA_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Ollama"
if exist "%OLLAMA_PATH%" set "PATH=%OLLAMA_PATH%;%PATH%"

REM 2. Check Virtual Environment
if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Creating...
    py -3.12 -m venv venv >nul 2>&1
    if not exist "venv\Scripts\python.exe" py -3.11 -m venv venv >nul 2>&1
    if not exist "venv\Scripts\python.exe" py -3.10 -m venv venv >nul 2>&1
    if not exist "venv\Scripts\python.exe" py -3.9 -m venv venv >nul 2>&1
)

REM 3. Activate and Install
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment could not be created or found.
    pause
    exit /b 1
)

echo Activating environment...
call "venv\Scripts\activate.bat"

REM 3.5 Ensure Ollama server is running (prevents "Ollama is not running" chat failures)
set "LLM_MODEL=llama3"
if exist ".env" (
    for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$m=(Get-Content .env | Where-Object {$_ -match '^LLM_MODEL='} | Select-Object -First 1); if($m){$m.Split('=')[1].Trim()} else {'llama3'}"`) do (
        set "LLM_MODEL=%%i"
    )
)

powershell -NoProfile -Command "try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Ollama is not running. Starting Ollama server...
    where ollama >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        start "Ollama Server" /B ollama serve
        timeout /t 3 >nul
    ) else (
        echo [WARN] Ollama executable not found on PATH.
        echo        Install from https://ollama.com/download
    )
)

REM Re-check Ollama after attempting startup
powershell -NoProfile -Command "try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARN] Ollama is still not reachable at http://127.0.0.1:11434
    echo        Run manually: ollama serve
) else (
    ollama list | findstr /I /C:"%LLM_MODEL%" >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [WARN] Model "%LLM_MODEL%" is not downloaded.
        echo        Run: ollama pull %LLM_MODEL%
    )
)

REM Quick dependency check to avoid reinstall on every run
echo Checking dependencies...
python -c "import fastapi, uvicorn" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Dependencies missing. Installing...
    python -m pip install --disable-pip-version-check --upgrade-strategy only-if-needed -r requirements.txt
) else (
    echo Dependencies already satisfied.
)

REM 4. Run Backend
echo.
echo Starting FastAPI backend on http://127.0.0.1:8000
echo Visit http://127.0.0.1:8000/api/docs for API documentation
echo.
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --log-level info

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Backend failed to start.
    pause
)

endlocal
