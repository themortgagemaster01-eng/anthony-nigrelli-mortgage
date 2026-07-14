@echo off
setlocal
cd /d "%~dp0"
title Obsidian Labs

echo.
echo =====================================
echo     Obsidian Labs - Launcher
echo =====================================
echo.

REM --- 1. prerequisites ---------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
  echo [X] Python is not installed.
  echo     Install it from https://www.python.org/downloads/
  echo     IMPORTANT: on the first screen, tick "Add Python to PATH".
  echo     Then double-click this file again.
  echo.
  pause
  exit /b 1
)
where ollama >nul 2>&1
if errorlevel 1 (
  echo [X] Ollama is not installed.
  echo     Install it from https://ollama.com/download
  echo     Then double-click this file again.
  echo.
  pause
  exit /b 1
)

REM --- desktop shortcut (first run only) ---------------------------
if not exist ".shortcut_done" call :make_shortcut

REM --- 2. environment + packages (first run only) ------------------
if not exist "venv\Scripts\activate.bat" (
  echo [1/4] Creating the Python environment. First run only, one moment...
  python -m venv venv
)
call "venv\Scripts\activate.bat"

if not exist ".setup_done" (
  echo [2/4] Installing packages. First run, this takes a few minutes...
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt
  echo.
  echo [2/4] Downloading the local AI models. First run only, several GB...
  ollama pull qwen2.5:14b-instruct-q4_K_M
  ollama pull nomic-embed-text
  echo done> ".setup_done"
) else (
  echo [2/4] Packages and models already set up. Skipping.
)

REM --- 3. config + API key (first run only) -----------------------
if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo.
  echo [3/4] Paste your Google API key below, then press Enter.
  echo       It needs Places API + PageSpeed Insights API enabled.
  set /p GKEY=Key:
  python -c "import pathlib,re,os;p=pathlib.Path('.env');t=p.read_text(encoding='utf-8');t=re.sub(r'^GOOGLE_API_KEY=.*','GOOGLE_API_KEY='+os.environ.get('GKEY',''),t,flags=re.M);p.write_text(t,encoding='utf-8')"
  echo       Saved to .env
) else (
  echo [3/4] Config already exists. Skipping.
)

REM --- 4. launch ---------------------------------------------------
echo [4/4] Starting Ollama and the backend, then opening the dashboard...
start "Ollama" cmd /k ollama serve
timeout /t 2 >nul
start "Obsidian Backend" cmd /k "call venv\Scripts\activate.bat && uvicorn fastapi_backend:app --port 8502"
timeout /t 5 >nul
start "" "dashboard_leadflow.html"

echo.
echo =====================================
echo   All set.
echo   - Two windows opened: Ollama + Backend. Keep them open while you work.
echo   - The dashboard opened in your browser. Click "Run Pipeline" to begin.
echo   - Want it on your phone? Double-click PHONE_ACCESS.bat.
echo   - You can close THIS window now.
echo =====================================
echo.
pause
exit /b 0

REM ================= subroutines =================
:make_shortcut
set "VBS=%TEMP%\ol_shortcut.vbs"
> "%VBS%" echo Set oWS = CreateObject("WScript.Shell")
>> "%VBS%" echo sLink = oWS.SpecialFolders("Desktop") ^& "\Obsidian Labs.lnk"
>> "%VBS%" echo Set oLink = oWS.CreateShortcut(sLink)
>> "%VBS%" echo oLink.TargetPath = "%~f0"
>> "%VBS%" echo oLink.WorkingDirectory = "%~dp0"
>> "%VBS%" echo oLink.IconLocation = "%SystemRoot%\System32\SHELL32.dll, 43"
>> "%VBS%" echo oLink.Save
cscript //nologo "%VBS%" >nul 2>&1
del "%VBS%" >nul 2>&1
echo done> ".shortcut_done"
echo Created a "Obsidian Labs" shortcut on your Desktop.
goto :eof
