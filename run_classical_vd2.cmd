@echo off
setlocal
set "PROJECT=%~dp0"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "SCRIPT=%PROJECT%src\traffic_monitor\classical_compare.py"
set "SOURCE=%PROJECT%data\derived\vd2_playback_1x_from_2x.mp4"
set "OUTPUT=%PROJECT%outputs\vd2_classical_live"

if not exist "%PYTHON%" (
    echo Khong tim thay Python trong .venv: "%PYTHON%"
    exit /b 1
)
if not exist "%SOURCE%" (
    echo Khong tim thay video 1x: "%SOURCE%"
    exit /b 1
)

echo Chay thi giac may tinh co dien tren vd2: MOG2 va FrameDiff, ca hai dung Kalman.
echo Cua so gom 3 o: RAW, MOG2 + Kalman, FrameDiff + Kalman.
echo Space tam dung, N tung frame, Q thoat.
"%PYTHON%" "%SCRIPT%" --source "%SOURCE%" --output "%OUTPUT%" --width 960 --show %*
exit /b %ERRORLEVEL%
