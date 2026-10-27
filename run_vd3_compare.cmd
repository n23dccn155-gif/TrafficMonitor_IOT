@echo off
setlocal
set "PROJECT=%~dp0"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "SOURCE=%PROJECT%data\raw\vd3.mp4"
set "YOLO_OUTPUT=%PROJECT%outputs\vd3_yolo_180"
set "TECHGAR_OUTPUT=%PROJECT%outputs\vd3_techgar_180"
set "COMPARE_OUTPUT=%PROJECT%outputs\vd3_comparison_180"

if not exist "%PYTHON%" (
    echo Khong tim thay Python trong .venv: "%PYTHON%"
    exit /b 1
)
if not exist "%SOURCE%" (
    echo Khong tim thay vd3: "%SOURCE%"
    exit /b 1
)

echo [1/4] YOLOv8n + ByteTrack: 180 frame, rong 640 pixel.
"%PYTHON%" "%PROJECT%src\traffic_monitor\yolo_camera.py" --source "%SOURCE%" --output "%YOLO_OUTPUT%" --width 640 --max-frames 180 --save-video
if errorlevel 1 exit /b 1

echo [2/4] TechGAR MotionVehicleTracker: cung 180 frame va do phan giai.
"%PYTHON%" "%PROJECT%src\traffic_monitor\single_camera.py" --source "%SOURCE%" --output "%TECHGAR_OUTPUT%" --width 640 --max-frames 180 --min-area 50 --min-width 6 --min-height 6 --min-displacement 4 --max-distance 70 --save-video
if errorlevel 1 exit /b 1

echo [3/4] Ghep ba o RAW, YOLO, TechGAR theo frame index.
"%PYTHON%" "%PROJECT%src\traffic_monitor\compare_yolo_techgar.py" --source "%SOURCE%" --yolo "%YOLO_OUTPUT%\annotated.mp4" --techgar "%TECHGAR_OUTPUT%\annotated.mp4" --output "%COMPARE_OUTPUT%\comparison.mp4" --max-frames 180 --panel-width 640
if errorlevel 1 exit /b 1

echo [4/4] Nen H.264 cho de xem lai.
"%PYTHON%" -c "import imageio_ffmpeg,subprocess,sys; subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-hide_banner','-loglevel','error','-i',sys.argv[1],'-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-movflags','+faststart',sys.argv[2]],check=True)" "%COMPARE_OUTPUT%\comparison.mp4" "%COMPARE_OUTPUT%\comparison_h264.mp4"
if errorlevel 1 exit /b 1

echo Video so sanh: "%COMPARE_OUTPUT%\comparison_h264.mp4"
exit /b 0
