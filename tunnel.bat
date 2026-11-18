@echo off
title SuperMart Mobile & Public Tunnel (Serveo)
echo ========================================================
echo Starting Mobile-Friendly Public Tunnel...
echo ========================================================
echo.
echo Forwarding port 8000 to public HTTPS...
echo Accessible from any mobile browser (Jio, Airtel, Vi, etc.)
echo.
ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:8000 serveo.net
pause
