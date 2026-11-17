@echo off
title TrafficMonitor IoT - Web Surveillance System
cd /d "%~dp0"
echo ========================================================
echo  KHOI DONG HE THONG GIAM SAT GIAO THONG TRAFFIC MONITOR IoT
echo ========================================================
echo Web Server dang khoi dong tai dia chi:
echo    http://127.0.0.1:8000/
echo.
echo Hay mo trinh duyet va truy cap http://127.0.0.1:8000/
echo Nhan Ctrl+C tren cua so nay neu muon dung server.
echo ========================================================
echo.

".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
pause
