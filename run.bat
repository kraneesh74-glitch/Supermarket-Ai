@echo off
title SuperMart AI Enquiry Agent Gateway
echo ========================================================
echo Starting SuperMart AI Enquiry Agent Gateway Server...
echo ========================================================
echo.
echo Local Web Chat Widget: http://127.0.0.1:8000  (or http://localhost:8000)
echo API Documentation:     http://127.0.0.1:8000/docs
echo WhatsApp Webhook URL:  http://127.0.0.1:8000/webhook/whatsapp
echo.

set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist %PYTHON_EXE% (
    set PYTHON_EXE=python
)

%PYTHON_EXE% -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
pause

