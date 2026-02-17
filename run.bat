@echo off
setlocal EnableDelayedExpansion

REM Add Ollama to PATH (Common local install location)
set "OLLAMA_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Ollama"
if exist "%OLLAMA_PATH%" set "PATH=%OLLAMA_PATH%;%PATH%"

REM Redirect Temp and Pip Cache to D: drive (Project Folder) to save C: space
if not exist "tmp" mkdir "tmp"
set "TEMP=%CD%\tmp"
set "TMP=%CD%\tmp"
set "PIP_CACHE_DIR=%CD%\tmp\pip_cache"

REM Kill any lingering Python/Streamlit processes to avoid venv file locks
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im streamlit.exe >nul 2>&1

REM Streamlit-only mode (frontend opens automatically)
set "STREAMLIT_ONLY=1"

REM Try to (re)create venv with preferred Python versions
set "USESYS=0"
REM Create venv if not exists
if not exist "venv" (
  py -3.11 -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" py -3.10 -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" py -3.9 -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" py -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" python -m venv venv >nul 2>&1
  if not exist "venv\Scripts\python.exe" set "USESYS=1"
) else (
  echo Using existing venv...
)

REM Activate venv if available
if "%USESYS%"=="0" (
  if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat" >nul 2>&1
  set "PATH=%CD%\venv\Scripts;%PATH%"
  set "PYTHONPATH=%CD%;%PYTHONPATH%"
)

REM Upgrade pip
if "%USESYS%"=="0" (
  venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
) else (
  python -m pip install --upgrade pip >nul 2>&1
)

REM Install dependencies from requirements.txt
echo Installing dependencies...
if "%USESYS%"=="0" (
  venv\Scripts\python.exe -m pip install -r requirements.txt
) else (
  python -m pip install -r requirements.txt
)

REM Launch Python entrypoint (opens browser automatically)
if "%USESYS%"=="0" (
  venv\Scripts\python.exe main.py
) else (
  python main.py
)
endlocal
