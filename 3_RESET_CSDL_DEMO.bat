@echo off
chcp 65001 >nul
title EduFlaw - Reset CSDL Demo Tinh Gon
echo =====================================================================
echo    🎓 EDUFLAW - RESET CSDL SANG BO DEMO TINH GON (NHOM 7)
echo =====================================================================
echo.
cd /d "%~dp0src"
".venv\Scripts\python.exe" reset_db_demo.py
echo.
pause
