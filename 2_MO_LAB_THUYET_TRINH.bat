@echo off
chcp 65001 >nul
title EduFlaw - Mo Lab Mo Phong Thuyet Trinh
echo =====================================================================
echo    🎓 EDUFLAW - MO TRANG MO PHONG LAB THUYET TRINH (NHOM 7)
echo =====================================================================
echo.
echo [*] Dang mo trang mo phong truc quan: demo/index.html ...
start "" "%~dp0demo\index.html"
echo.
echo =====================================================================
echo  [OK] Da mo trang Lab tren trinh duyet!
echo  -> Ban chi can bam nut hoac bam phim:
echo     1 - 4 : Chuyen qua lai giua cac bai A01, A03, A07, A10
echo     V     : Chay ban co Lo Hong (Vuln)
echo     S     : Chay ban Da Va (Secure)
echo     Enter : Gui yeu cau thu nghiem
echo =====================================================================
echo.
timeout /t 3 >nul
exit
