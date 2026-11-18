@echo off
title SuperMart 24/7 Background Service
cd /d "%~dp0"

echo ========================================================
echo Starting SuperMart AI Gateway in Background...
echo ========================================================

set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist %PYTHON_EXE% (
    set PYTHON_EXE=python
)

:: Start Uvicorn Server in background
start "SuperMart Server" /min cmd /c "%PYTHON_EXE% -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000"

:: Wait 3 seconds for server to bind
timeout /t 3 /nobreak >nul

:: Start Cloudflare tunnel in background
start "Cloudflare Tunnel" /min cmd /c ""%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:8000 --logfile "%~dp0logs\tunnel.log""

echo SuperMart AI is now running in the background!
echo Local Address: http://127.0.0.1:8000
echo Tunnel logs:   %~dp0logs\tunnel.log
