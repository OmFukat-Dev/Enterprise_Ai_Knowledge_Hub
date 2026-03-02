@echo off
setlocal EnableDelayedExpansion

echo ---------------------------------------------------
echo Enterprise AI Knowledge Hub - FRONTEND STARTING
echo ---------------------------------------------------

REM 1. Set Environment Variables
set "PYTHONPATH=%CD%"
set "PYTHONUTF8=1"
set "PIP_DEFAULT_TIMEOUT=120"
set "OLLAMA_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Ollama"
if exist "%OLLAMA_PATH%" set "PATH=%OLLAMA_PATH%;%PATH%"

set "OLLAMA_MODELS=C:\Users\%USERNAME%\AppData\Local\Ollama\models"
set "OLLAMA_HOME=C:\Users\%USERNAME%\AppData\Local\Ollama"
if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%" >nul 2>&1

if not exist "tmp" mkdir "tmp"
set "TEMP=%CD%\tmp"
set "TMP=%CD%\tmp"
set "PIP_CACHE_DIR=%CD%\tmp\pip_cache"

set "DIRECT_MODE=0"

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

REM Quick dependency check to avoid reinstall on every run
echo Checking dependencies...
python -m pip show streamlit >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Dependencies missing. Installing...
    python -m pip install --disable-pip-version-check --upgrade-strategy only-if-needed -r requirements.txt
) else (
    echo Dependencies already satisfied.
)

REM 4. Run Frontend
echo.
echo Starting Streamlit frontend on http://127.0.0.1:8501
echo Ensure the backend is running in another terminal!
echo.
python -m streamlit run "frontend\dashboard.py" ^
  --server.port=8501 ^
  --server.address=127.0.0.1 ^
  --server.enableCORS=false ^
  --server.enableXsrfProtection=false ^
  --server.maxUploadSize=200 ^
  --server.fileWatcherType=none

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Frontend failed to start.
    pause
)

endlocal
