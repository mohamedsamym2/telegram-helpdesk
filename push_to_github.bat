@echo off
cd /d "%~dp0"
echo ====================================================
echo    Pushing IT Support HelpDesk to GitHub...
echo ====================================================
echo.
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] All files uploaded successfully to your GitHub repository!
) else (
    echo [NOTE] If this is your first time, a GitHub login window should appear.
)
echo.
pause
