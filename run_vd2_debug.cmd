@echo off
setlocal
set "PROJECT=%~dp0"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "SCRIPT=%PROJECT%src\traffic_monitor\yolo_camera.py"
set "SOURCE=%PROJECT%data\derived\vd2_playback_1x_from_2x.mp4"
set "OUTPUT=%PROJECT%outputs\vd2_1x_live_debug"

if not exist "%PYTHON%" (
    echo Khong tim thay Python trong .venv: "%PYTHON%"
    exit /b 1
)
if not exist "%SOURCE%" (
    echo Khong tim thay video 1x: "%SOURCE%"
    exit /b 1
)

echo Dang chay YOLOv8n + ByteTrack tren vd2 phat 1x.
echo Cua so debug: RAW ben trai, box/ID ben phai. Space tam dung, N tung frame, Q thoat.
echo Ket qua duoc luu tai: "%OUTPUT%"
"%PYTHON%" "%SCRIPT%" --source "%SOURCE%" --output "%OUTPUT%" --width 960 --show --save-video %*
exit /b %ERRORLEVEL%
