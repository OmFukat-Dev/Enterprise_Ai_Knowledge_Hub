@echo off
setlocal EnableDelayedExpansion

REM Optional local Ollama path
set "OLLAMA_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Ollama"
if exist "%OLLAMA_PATH%" set "PATH=%OLLAMA_PATH%;%PATH%"

REM FIX: Redirect Ollama model storage to a writable user folder.
REM Default (D:\ollama_models) is on a protected drive and causes "Access is denied".
set "OLLAMA_MODELS=C:\Users\%USERNAME%\AppData\Local\Ollama\models"
set "OLLAMA_HOME=C:\Users\%USERNAME%\AppData\Local\Ollama"
if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%" >nul 2>&1

REM Keep temporary/cache files in project folder
if not exist "tmp" mkdir "tmp"
set "TEMP=%CD%\tmp"
set "TMP=%CD%\tmp"
set "PIP_CACHE_DIR=%CD%\tmp\pip_cache"

REM Frontend-only by default. Set STREAMLIT_ONLY=0 to run API + frontend orchestration from main.py.
REM Change default to run BOTH backend (FastAPI) and frontend (Streamlit) together.
if "%STREAMLIT_ONLY%"=="" set "STREAMLIT_ONLY=0"
REM Ensure Streamlit uses the API when available
if "%DIRECT_MODE%"=="" set "DIRECT_MODE=0"

REM Create virtual env if missing
set "USESYS=0"
if not exist "venv\Scripts\python.exe" (
  py -3.12 -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" py -3.11 -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" py -3.10 -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" py -3.9 -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" python -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" set "USESYS=1"
)

REM Validate binary wheels in venv; if broken (e.g., cp313 artifacts in cp312 env), rebuild venv
if "%USESYS%"=="0" (
  venv\Scripts\python.exe -c "import numpy, pydantic_core, grpc" >nul 2>&1
  if errorlevel 1 (
    echo Existing venv has incompatible binaries. Rebuilding clean environment...
    taskkill /F /IM streamlit.exe >NUL 2>&1
    taskkill /F /IM python.exe >NUL 2>&1
    rmdir /S /Q venv >NUL 2>&1
    py -3.12 -m venv venv >nul 2>&1
    if not exist "venv\Scripts\python.exe" py -3.11 -m venv venv >nul 2>&1
    if not exist "venv\Scripts\python.exe" py -3.10 -m venv venv >nul 2>&1
    if not exist "venv\Scripts\python.exe" py -3.9 -m venv venv >nul 2>&1
    if not exist "venv\Scripts\python.exe" set "USESYS=1"
  )
)

REM Activate venv if present
if "%USESYS%"=="0" (
  call "venv\Scripts\activate.bat" >nul 2>&1
  set "PATH=%CD%\venv\Scripts;%PATH%"
  set "PYTHONPATH=%CD%;%PYTHONPATH%"
)

REM Ensure project root is always on PYTHONPATH (required for src.* imports)
if "%PYTHONPATH%"=="" set "PYTHONPATH=%CD%"

echo Installing dependencies...
if "%USESYS%"=="0" (
  venv\Scripts\python.exe -m pip install --upgrade pip
  venv\Scripts\python.exe -m pip install -r requirements.txt
  venv\Scripts\python.exe main.py
) else (
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  python main.py
)

endlocal
