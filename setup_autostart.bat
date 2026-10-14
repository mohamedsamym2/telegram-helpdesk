@echo off
chcp 65001 > nul
title Configure Auto-Start on Windows Boot

echo ============================================================
echo   تفعيل التشغيل التلقائي لسيرفر الدعم الفني مع إقلاع الويندوز
echo ============================================================
echo.

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET_VBS=%~dp0start_background.vbs"
set "SHORTCUT_PATH=%STARTUP_DIR%\TelegramHelpDesk.lnk"

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT_PATH%');$s.TargetPath='wscript.exe';$s.Arguments='\"%TARGET_VBS%\"';$s.WorkingDirectory='%~dp0';$s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo [OK] تم تفعيل التشغيل التلقائي بنجاح!
    echo من الآن فصاعدا، سيعمل السيرفر في الخلفية تلقائيا بمجرد تشغيل الكمبيوتر.
) else (
    echo [!] حدث خطأ أثناء التفعيل، يرجى المحاولة كمسؤول.
)

echo.
pause
