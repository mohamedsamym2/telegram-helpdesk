@echo off
title IT Support Helpdesk Server

echo ============================================================
echo          IT Support Helpdesk - Telegram Bot
echo ============================================================
echo.
echo  Starting local server...
echo.
echo  Open Dashboard in your browser:
echo  --^> http://localhost:8080
echo.
echo  Default Login Credentials:
echo    Username: admin
echo    Password: admin123
echo.
echo  For other devices on company LAN:
ipconfig | findstr /i "IPv4"
echo  Access via: http://[YOUR-IP]:8080
echo ============================================================
echo.

start "" "http://localhost:8080"
python server.py

pause
