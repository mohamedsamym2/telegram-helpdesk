@echo off
title Install Requirements
echo Installing necessary packages (FastAPI, Uvicorn, HTTPX, WebSockets)...
echo.
python -m pip install fastapi uvicorn httpx websockets
echo.
echo ============================================================
echo Installation completed! You can now start the server with run.bat
echo ============================================================
pause
