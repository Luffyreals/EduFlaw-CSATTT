@echo off
chcp 65001 >nul
title EduFlaw - Khoi chay Web Demo
echo =====================================================================
echo    🎓 EDUFLAW - KHOI CHAY HE THONG WEB DEMO (NHOM 7 - PTIT)
echo =====================================================================
echo.
cd /d "%~dp0src"

if not exist ".venv\Scripts\python.exe" (
    echo [!] Chua tim thay .venv, dang chay setup tu dong...
    powershell -ExecutionPolicy Bypass -File .\setup.ps1 -SkipTests
)

echo [*] Dang khoi dong Web Server tai http://127.0.0.1:5000 ...
start "" ".venv\Scripts\python.exe" run.py

echo [*] Dang mo trinh duyet Web...
timeout /t 2 >nul
start "" "http://127.0.0.1:5000"

echo.
echo =====================================================================
echo  [OK] Server da duoc bat va trinh duyet da mo trang dang nhap!
echo  -> Ban co the bam vao 3 nut 'Dang nhap Demo 1-Click' tren giao dien
echo     de vao thang tai khoan Master, Giang vien hoac Sinh vien.
echo =====================================================================
echo.
echo Cua so nay dang giu may chu hoat dong.
echo Khi thuyet trinh xong, ban co the dong cua so nay de tat server.
echo.
pause
