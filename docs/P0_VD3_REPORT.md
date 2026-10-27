# So sánh YOLO với TechGAR trên `vd3.mp4`

Ngày 27/10/2026. Người dùng xác nhận `vd3` được quay ở **tốc độ phát 1×**; dùng trực tiếp `data/raw/vd3.mp4`, không đổi timestamp. Clip có 1912 × 906, 30 FPS, 2.466 frame, 82,2 giây; vẫn là góc giao lộ đông xe máy. Chưa có URL nguồn/giấy phép hoặc nhãn xe đúng để đánh giá độ chính xác. Xem [danh mục clip](../data/CLIP_CATALOG.md).

## Xem kết quả

- Video ba ô cục bộ `outputs/vd3_comparison_180/comparison_h264.mp4`: hình gốc, YOLOv8n + ByteTrack, TechGAR `MotionVehicleTracker` trên **đúng cùng frame**.
- Ảnh `outputs/vd3_comparison_180/frame_120.jpg`; video YOLO `outputs/vd3_yolo_180/annotated.mp4`; video TechGAR `outputs/vd3_techgar_180/annotated.mp4`. Các file này [không có sau khi clone](LOCAL_ARTIFACTS.md).
- Mỗi thư mục output có `tracks.jsonl` và `summary.json`. ID do hai tracker cấp độc lập; ID số 5 của bên này không phải ID số 5 của bên kia.

Muốn chạy lại phép thử, cần có `data/raw/vd3.mp4` và repo TechGAR riêng (đặt `TECHGAR_ROOT` theo [README](../README.md)). Từ terminal IDE ở thư mục `TrafficMonitor_IoT`, chạy lần lượt:

```powershell
.\.venv\Scripts\python.exe src\traffic_monitor\yolo_camera.py --source data\raw\vd3.mp4 --output outputs\vd3_yolo_180 --width 640 --max-frames 180 --save-video
.\.venv\Scripts\python.exe src\traffic_monitor\single_camera.py --source data\raw\vd3.mp4 --output outputs\vd3_techgar_180 --width 640 --max-frames 180 --min-area 50 --min-width 6 --min-height 6 --min-displacement 4 --max-distance 70 --save-video
.\.venv\Scripts\python.exe src\traffic_monitor\compare_yolo_techgar.py --source data\raw\vd3.mp4 --yolo outputs\vd3_yolo_180\annotated.mp4 --techgar outputs\vd3_techgar_180\annotated.mp4 --output outputs\vd3_comparison_180\comparison.mp4 --max-frames 180 --panel-width 640
```

Ba lệnh trên tạo video so sánh `comparison.mp4`; file H.264 nêu ở phần trên là bản chuyển mã từ lần chạy cũ. TechGAR mất khoảng 100 giây cho đoạn này trên CPU của lần thử trước. Muốn quan sát trực tiếp cửa sổ khi từng chương trình chạy, thêm `--show` vào lệnh Python tương ứng theo [hướng dẫn debug](DEBUG_VIEWING.md).

Nếu muốn **hai cửa sổ debug xuất hiện lần lượt**, thêm `--show` vào hai lệnh xử lý đầu tiên ở trên; với TechGAR có thể thêm `--show-mask`. Cửa sổ phải được khởi chạy từ phiên Windows của bạn, vì cửa sổ do công cụ Codex mở có thể nằm trong desktop cách ly.

## Thiết lập so sánh

Đầu vào giống nhau: **180 frame đầu (6,0 giây)** của `vd3`, thu nhỏ về **640 × 303** cho xử lý; MP4 sau mã hóa có chiều cao chẵn 302 px. Chạy tuần tự trên cùng máy để tránh tranh CPU.

- YOLO: `yolov8n.pt` sẵn có trong TechGAR, Ultralytics 8.4.190, confidence 0,25, ByteTrack `bytetrack.yaml`, các lớp `car`, `motorcycle`, `bus`, `truck`, CPU.
- TechGAR: import trực tiếp `MotionVehicleTracker` của repo cũ, dùng MOG2/frame difference và Kalman/ghép track theo triển khai đó. Thử `min_area=50`, `min_width=min_height=6`, `min_displacement=4`, `max_distance=70`, `enable_multiscale_motion=True`, `reject_cast_shadows=True`; không sửa mã TechGAR.

| Chỉ số quan sát trên 180 frame | YOLO + ByteTrack | TechGAR MotionVehicleTracker |
| --- | ---: | ---: |
| Thời gian xử lý | 8,22 giây | 99,35 giây |
| Tốc độ xử lý | 21,91 FPS | 1,81 FPS |
| Box/track trung bình mỗi frame | 10,87 | 5,05 |
| ID khác nhau được xuất | 107 | 135 |
| Số frame trung vị mỗi ID xuất hiện | 3 | 3 |
| ID xuất hiện ít nhất 30 frame | 16 | 4 |

Đây là **số liệu output**, không phải số xe thật, precision/recall hoặc độ chính xác ID. YOLO có nhiều quan sát hơn (1.957 so với 909), nhưng vẫn bỏ sót nhiều xe máy nhỏ và có thể nhầm lớp. TechGAR ít box hơn và nhiều ID ngắn; góc quay rộng, xe máy nhỏ và đông gây khó cho trừ nền/ghép đối tượng. Ảnh frame 120 cho thấy cả hai chưa bao phủ phần lớn xe máy trong giao lộ. Cần gán nhãn một đoạn chuẩn và thử ROI/độ phân giải khác trước khi chọn pipeline chính hoặc bật quy tắc vi phạm.
