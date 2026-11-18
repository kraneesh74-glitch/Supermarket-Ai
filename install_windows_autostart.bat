@echo off
title Install SuperMart Daily Auto-Start
echo ========================================================
echo Installing SuperMart to Windows Startup...
echo ========================================================
echo.

set SCRIPT_PATH=%~dp0auto_start_service.bat
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_DIR%\SuperMartAI.bat

echo Copying startup launcher to Windows Startup folder...
copy /y "%SCRIPT_PATH%" "%SHORTCUT_PATH%" >nul

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] SuperMart AI is now configured to start automatically
    echo every time you log in to your computer!
    echo.
    echo Installed to: %SHORTCUT_PATH%
) else (
    echo [ERROR] Failed to install to Startup folder.
)
echo.
pause
