# Xem quá trình debug video

Các link video trong tài liệu này trỏ tới [output cục bộ, không đưa lên Git](LOCAL_ARTIFACTS.md). Sau khi clone, hãy cung cấp MP4 của bạn và chạy `menu.py` để tạo output mới.

Chạy `menu.py` từ terminal IDE để chọn video và thuật toán. Cửa sổ có **ảnh gốc bên trái, box/ID bên phải** và dòng FPS nguồn/FPS xử lý phía dưới. Ba preset của menu đều xử lý đủ frame file; preset 640 px chỉ giảm độ phân giải. Mặc định chỉ lưu `tracks.jsonl` và `summary.json`; chọn ghi MP4 khi menu hỏi nếu cần phát lại mượt ở FPS gốc. Xem [giải thích tốc độ](PERFORMANCE.md).

Hai chương trình P0 vẫn có tùy chọn `--show` để mở cùng cửa sổ. `annotated.mp4` chỉ được tạo khi thêm `--save-video`; `tracks.jsonl` và `summary.json` luôn được lưu. Cửa sổ do công cụ Codex khởi chạy có thể nằm trong phiên desktop cách ly, nên **không hiện trên màn hình của bạn**. Muốn nhìn thấy cửa sổ OpenCV, chạy trong terminal IDE của bạn.

Từ thư mục môn học `IOT`, mở cửa sổ debug cho **toàn bộ `vd2` bản phát 1×**:

```powershell
& '.\IOT_CAM\TrafficMonitor_IoT\run_vd2_debug.cmd'
```

Muốn chỉ chạy 300 frame đầu, thêm `--max-frames 300`. Launcher gọi YOLOv8n + ByteTrack, mở cửa sổ ngay trong phiên desktop hiện tại và lưu kết quả vào `outputs/vd2_1x_live_debug/`. Bản 1× nằm tại `data/derived/vd2_playback_1x_from_2x.mp4`; nếu chỉ muốn xem video đã xử lý mà chưa tự chạy GUI, mở [video so sánh 20 giây đầu](../outputs/vd2_1x_yolo_probe_300/compare_raw_vs_debug.mp4).

Để so sánh **thị giác máy tính cổ điển không dùng YOLO** trên `vd2` với ba ô RAW, MOG2 + Kalman và FrameDiff + Kalman:

```powershell
& '.\IOT_CAM\TrafficMonitor_IoT\run_classical_vd2.cmd'
```

Launcher mặc định chạy 300 frame. Xem [video ba ô đã xuất](../outputs/vd2_classical_compare_300/comparison_h264.mp4) và [giải thích, kết quả](CLASSICAL_COMPARISON.md). Box tím có chữ `P` là vị trí Kalman dự đoán khi frame hiện tại không có blob ghép được.

Với `vd3` quay ở 1×, [video so sánh YOLO và TechGAR đã xuất](../outputs/vd3_comparison_180/comparison_h264.mp4). Muốn chạy lại cả hai và ghép video, dùng `run_vd3_compare.cmd`. Muốn xem **cửa sổ YOLO rồi cửa sổ TechGAR xuất hiện lần lượt**, chạy `run_vd3_live.cmd` từ terminal IDE. Có thể chạy từng chương trình riêng bằng hai lệnh sau:

```powershell
& '.\IOT_CAM\TrafficMonitor_IoT\.venv\Scripts\python.exe' '.\IOT_CAM\TrafficMonitor_IoT\src\traffic_monitor\yolo_camera.py' --source '.\IOT_CAM\TrafficMonitor_IoT\data\raw\vd3.mp4' --output '.\IOT_CAM\TrafficMonitor_IoT\outputs\vd3_yolo_live' --width 640 --max-frames 180 --show
& '.\IOT_CAM\TrafficMonitor_IoT\.venv\Scripts\python.exe' '.\IOT_CAM\TrafficMonitor_IoT\src\traffic_monitor\single_camera.py' --source '.\IOT_CAM\TrafficMonitor_IoT\data\raw\vd3.mp4' --output '.\IOT_CAM\TrafficMonitor_IoT\outputs\vd3_techgar_live' --width 640 --max-frames 180 --min-area 50 --min-width 6 --min-height 6 --min-displacement 4 --max-distance 70 --show --show-mask
```

TechGAR có thêm cửa sổ mặt nạ MOG2. Cả hai script lưu `tracks.jsonl`, `summary.json` khi kết thúc hoặc nhấn Q; thêm `--save-video` để lưu `annotated.mp4`.

Để xem TechGAR MOG2 và **motion mask** trên `vd1`:

```powershell
& 'IOT_CAM\TrafficMonitor_IoT\.venv\Scripts\python.exe' 'IOT_CAM\TrafficMonitor_IoT\src\traffic_monitor\single_camera.py' --source 'IOT_CAM\TrafficMonitor_IoT\data\raw\vd1.mp4' --output 'IOT_CAM\TrafficMonitor_IoT\outputs\vd1_live_debug' --width 960 --max-frames 120 --min-area 100 --show --show-mask
```

Điều khiển trong cửa sổ: **Space** tạm dừng/tiếp tục, **N** bước một frame khi đang tạm dừng, **Q** hoặc **Esc** dừng và lưu phần đã xử lý.

Ở kết quả: khung **xanh** là box xe/track, `ID` là mã theo dõi, vệt **vàng** là quỹ đạo điểm tiếp xúc mặt đường. YOLO còn ghi `car`, `motorcycle`, `bus`, `truck`; MOG2 chỉ ghi loại `unknown`. Motion mask thể hiện vùng thay đổi mà TechGAR dùng để đề xuất đối tượng. **Chưa có cảnh báo vi phạm** trong hai chương trình này.

Muốn xem ngay file đã xuất trước đó mà không chạy lại:

```powershell
Start-Process -FilePath 'IOT_CAM\TrafficMonitor_IoT\outputs\vd1_yolo_full\annotated.mp4'
Start-Process -FilePath 'IOT_CAM\TrafficMonitor_IoT\outputs\vd1_motion_probe\annotated.mp4'
Start-Process -FilePath 'IOT_CAM\TrafficMonitor_IoT\outputs\vd2_live_debug\compare_raw_vs_debug.mp4'
```

Với `vd2` phát 2×, đừng kết luận sai/đúng từ tốc độ biểu kiến. Bản 1× chỉ thay timestamp, giữ nguyên 2.737 frame đã quay; nó không lấy lại frame bị bỏ qua khi nguồn chạy 2×. `video_timestamp_ms` thuộc **timeline của bản 1× được suy ra**, chưa phải đồng hồ thực của giao lộ. Cần gán nhãn một vài quỹ đạo trước khi dùng cho `WrongWayDetector`.

Kết quả đã xem và số liệu của `vd2` nằm trong [báo cáo P0 của `vd2`](P0_VD2_REPORT.md). File so sánh gốc/kết quả chỉ có 300 frame đầu để dễ xem; file `vd1_yolo_full/annotated.mp4` đã xử lý toàn bộ `vd1`.
