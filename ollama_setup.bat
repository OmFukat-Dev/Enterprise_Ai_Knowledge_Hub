@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  Ollama Setup for Enterprise AI Knowledge Hub
echo ============================================================
echo.

REM ── Step 1: Set writable model storage path ─────────────────────────────────
REM The D:\ollama_models path has no write permissions.
REM We redirect to C:\Users\%USERNAME%\AppData\Local\Ollama\models instead.
set "MODELS_DIR=C:\Users\%USERNAME%\AppData\Local\Ollama\models"
set "OLLAMA_MODELS=%MODELS_DIR%"
set "OLLAMA_HOST=127.0.0.1:11434"

if not exist "%MODELS_DIR%" (
    mkdir "%MODELS_DIR%" >nul 2>&1
    echo [OK] Created models directory: %MODELS_DIR%
) else (
    echo [OK] Models directory exists: %MODELS_DIR%
)

REM ── Step 2: Write env var permanently to Windows user registry ───────────────
powershell -Command "[System.Environment]::SetEnvironmentVariable('OLLAMA_MODELS', '%MODELS_DIR%', 'User')" >nul 2>&1
echo [OK] OLLAMA_MODELS set permanently in Windows user environment.

REM ── Step 3: Stop any running Ollama that has wrong path ─────────────────────
echo Stopping existing Ollama processes...
taskkill /F /IM ollama.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul

REM ── Step 4: Find Ollama executable ──────────────────────────────────────────
set "OLLAMA_EXE="
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe"
) else (
    for /f "tokens=*" %%i in ('where ollama 2^>nul') do set "OLLAMA_EXE=%%i"
)

if "%OLLAMA_EXE%"=="" (
    echo.
    echo [ERROR] Ollama is not installed or not on PATH.
    echo Download Ollama from: https://ollama.com/download
    echo.
    pause
    exit /b 1
)
echo [OK] Found Ollama: %OLLAMA_EXE%

REM ── Step 5: Start Ollama serve with correct env ──────────────────────────────
echo Starting Ollama server with OLLAMA_MODELS=%MODELS_DIR% ...
start "Ollama Server" /B "%OLLAMA_EXE%" serve

REM Wait for server to be ready
echo Waiting for Ollama to start...
ping -n 6 127.0.0.1 >nul

REM ── Step 6: Pull the model ───────────────────────────────────────────────────
echo.
echo Pulling llama3 model (this may take a while on first run)...
"%OLLAMA_EXE%" pull llama3

if errorlevel 1 (
    echo.
    echo [WARN] llama3 failed. Trying llama3.2 instead...
    "%OLLAMA_EXE%" pull llama3.2
    if errorlevel 1 (
        echo.
        echo [WARN] llama3.2 also failed. Trying mistral (smaller model)...
        "%OLLAMA_EXE%" pull mistral
    ) else (
        REM Update .env to use llama3.2
        powershell -Command "(Get-Content .env) -replace 'LLM_MODEL=llama3$','LLM_MODEL=llama3.2' | Set-Content .env"
        echo [OK] Set LLM_MODEL=llama3.2 in .env
    )
) else (
    echo [OK] llama3 pulled successfully!
)

echo.
echo ── Available models ────────────────────────────────────────
"%OLLAMA_EXE%" list

echo.
echo ============================================================
echo  Setup complete! Now run the application:
echo    python main.py
echo ============================================================
echo.
pause
endlocal
