@echo off
title Launch SuperMart AI Agent + Public Tunnel
echo ========================================================
echo Launching SuperMart Server & Cloudflare Edge Tunnel...
echo ========================================================
echo.

start "SuperMart Server" cmd /k "%~dp0run.bat"
timeout /t 3 /nobreak >nul
start "Cloudflare Tunnel" cmd /k "%~dp0tunnel.bat"

echo Both services launched in separate windows!
echo Keep both windows open while testing.
