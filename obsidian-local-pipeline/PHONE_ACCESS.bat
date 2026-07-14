@echo off
setlocal
cd /d "%~dp0"
title Obsidian Labs - Phone Access

echo.
echo =====================================
echo    Obsidian Labs - Phone Access
echo =====================================
echo.
echo This makes your dashboard reachable on your phone.
echo Make sure START.bat is already running first.
echo.

where ngrok >nul 2>&1
if errorlevel 1 (
  echo [X] ngrok is not installed. One-time setup:
  echo     1. Download it free:  https://ngrok.com/download
  echo     2. Make a free account, copy your authtoken from the ngrok dashboard.
  echo     3. Run once:  ngrok config add-authtoken YOUR_TOKEN
  echo        ^(open ngrok once and it will show you exactly this command^)
  echo     Then double-click this file again.
  echo.
  pause
  exit /b 1
)

echo Opening a secure tunnel to your backend on port 8502...
start "ngrok tunnel - keep open" cmd /k ngrok http 8502
echo Waiting for the tunnel to come up...
timeout /t 6 >nul

set "URL="
for /f "usebackq delims=" %%U in (`python -c "import urllib.request,json;d=json.load(urllib.request.urlopen('http://localhost:4040/api/tunnels'));print(next((t['public_url'] for t in d['tunnels'] if t['public_url'].startswith('https')),''))" 2^>nul`) do set "URL=%%U"

echo.
if defined URL (
  echo =====================================
  echo   YOUR PHONE URL:
  echo   %URL%
  echo =====================================
  echo %URL%| clip
  echo   ^(copied to your clipboard^)
  echo %URL%> phone_url.txt
  echo   ^(also saved to phone_url.txt^)
  echo.
  echo On your phone:
  echo   1. Open the dashboard.
  echo   2. Tap the settings / backend option.
  echo   3. Paste this URL and save.
) else (
  echo Could not read the URL automatically.
  echo Look in the "ngrok tunnel" window for the line that looks like:
  echo    Forwarding   https://xxxx.ngrok-free.app  -^>  http://localhost:8502
  echo Copy that https address and paste it into your phone dashboard's settings.
)
echo.
echo Keep the ngrok window open while using your phone. Its URL changes each time
echo you restart it, so re-run this and re-paste if you restart ngrok.
echo.
pause
