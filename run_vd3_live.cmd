@echo off
setlocal
set "PROJECT=%~dp0"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "SOURCE=%PROJECT%data\raw\vd3.mp4"

if not exist "%PYTHON%" (
    echo Khong tim thay Python trong .venv: "%PYTHON%"
    exit /b 1
)
if not exist "%SOURCE%" (
    echo Khong tim thay vd3: "%SOURCE%"
    exit /b 1
)

echo [1/2] Mo cua so YOLOv8n + ByteTrack. Space tam dung, N tung frame, Q thoat.
"%PYTHON%" "%PROJECT%src\traffic_monitor\yolo_camera.py" --source "%SOURCE%" --output "%PROJECT%outputs\vd3_yolo_live" --width 640 --max-frames 180 --show --save-video %*
if errorlevel 1 exit /b 1

echo [2/2] Mo cua so TechGAR va MOG2 mask. Space tam dung, N tung frame, Q thoat.
"%PYTHON%" "%PROJECT%src\traffic_monitor\single_camera.py" --source "%SOURCE%" --output "%PROJECT%outputs\vd3_techgar_live" --width 640 --max-frames 180 --min-area 50 --min-width 6 --min-height 6 --min-displacement 4 --max-distance 70 --show --show-mask --save-video %*
exit /b %ERRORLEVEL%
