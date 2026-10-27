# P0 — đánh giá ban đầu `vd1.mp4`

Ngày 26/10/2026. Đây là **thử nghiệm kỹ thuật**, chưa có ground truth và chưa đo precision/recall/F1 của phát hiện hành vi.

## Clip

`data/raw/vd1.mp4`: 2554 × 1440, 30 FPS, 1.787 frame (59,57 giây). Góc camera cố định trên cao, ban ngày, nhiều ô tô. Nhìn thấy vạch đường và đèn, nhưng tín hiệu đèn nhỏ, khó xác định đèn nào áp dụng cho từng luồng xe từ một khung toàn cảnh. Chưa thấy xe máy trong các khung mẫu đã xem. URL nguồn đã được người dùng cung cấp; điều khoản tái phân phối chưa xác minh. Xem [`data/CLIP_CATALOG.md`](../data/CLIP_CATALOG.md).

## Hai phép chạy đối chứng đầu tiên

Cùng **120 frame đầu / 4 giây**, xử lý ở **960 × 541**. Số liệu dưới đây là thống kê output của tracker, **không phải số xe thật hoặc độ chính xác**.

| Chỉ số | TechGAR MOG2 + tracker | YOLOv8n + ByteTrack |
| --- | ---: | ---: |
| Thời gian xử lý 120 frame | 30,06 s | 16,17 s |
| Tốc độ xử lý quan sát được | 3,99 FPS | 7,42 FPS |
| ID đã xác nhận khác nhau | 41 | 47 |
| Số frame trung vị mỗi ID xuất hiện | 2 | 8 |
| ID xuất hiện ít nhất 30 frame | 2 | 18 |
| Xe/track có box ở frame 60 | 2 | 16 |
| Xe/track có box ở frame 110 | 3 | 17 |

Thông số MOG2: `min_area=100`, `min_width=9`, `min_height=9`, `min_confirm_displacement=6`, `max_distance=100`, multi-scale motion và lọc bóng đổ bật. YOLO dùng model `yolov8n.pt` có sẵn trong TechGAR, confidence `0.25`, chỉ giữ COCO `car`, `motorcycle`, `bus`, `truck`. Hai số tốc độ ở bảng được đo lại trong **cùng môi trường `.venv`** trên CPU, nhưng là phép thử ngắn chưa lặp nhiều lần nên chưa phải benchmark chuẩn.

Quan sát các frame 60 và 110 cho thấy MOG2 bỏ sót nhiều xe đang thấy rõ và đôi khi box bám vào vùng đường/đảo giao thông. YOLO có box trên nhiều xe hơn, kể cả xe đỗ dọc đường; vẫn có thể đổi ID, bỏ sót xe xa hoặc nhầm lớp. 47 ID trong 4 giây **không có nghĩa** có 47 xe. Không chọn pipeline chính dựa trên các số này trước khi có nhãn thủ công và ROI phù hợp.

## Bản chạy YOLO/ByteTrack trên toàn clip

Đã chạy đủ **1.787 frame / 59,57 giây** ở 960 × 541, CPU. Thời gian xử lý 126,86 giây, trung bình quan sát được 14,09 FPS (thấp hơn FPS nguồn là 30). Output nằm ở `outputs/vd1_yolo_full/annotated.mp4`, `tracks.jsonl`, `summary.json`.

Thống kê output: 369 ID khác nhau, trung vị 7 frame/ID; 102 ID xuất hiện ít nhất 30 frame. Có 25.566 quan sát gắn nhãn `car`, 703 `truck`, 436 `bus`, và **không có quan sát `motorcycle`**. Đây là số quan sát qua từng frame, không phải số phương tiện duy nhất. Quan sát các khung 446, 893 và 1750 thấy tracker bám được nhiều xe nhưng vẫn có ID duy trì qua những vị trí/xe khác nhau; không thể coi ID dài là bảo đảm đúng danh tính.

Kết quả này đủ để chọn YOLO/ByteTrack làm **ứng viên cho bước gán nhãn và hiệu chỉnh ROI**, chưa đủ để công bố độ chính xác phát hiện hành vi hoặc yêu cầu thời gian thực.

## File có thể xem trong workspace

- MOG2: `outputs/vd1_motion_probe/annotated.mp4`, `tracks.jsonl`, `summary.json`.
- YOLO/ByteTrack 4 giây: `outputs/vd1_yolo_probe/annotated.mp4`, `tracks.jsonl`, `summary.json`.
- YOLO/ByteTrack toàn clip: `outputs/vd1_yolo_full/annotated.mp4`, `tracks.jsonl`, `summary.json`.
- Chương trình: `src/traffic_monitor/single_camera.py` và `src/traffic_monitor/yolo_camera.py`. Chúng chỉ đọc mã/weights TechGAR, không sửa repo cũ.

Lệnh chạy lại từ thư mục môn học `IOT`:

```powershell
& 'IOT_CAM\TrafficMonitor_IoT\.venv\Scripts\python.exe' 'IOT_CAM\TrafficMonitor_IoT\src\traffic_monitor\single_camera.py' --source 'IOT_CAM\TrafficMonitor_IoT\data\raw\vd1.mp4' --output 'IOT_CAM\TrafficMonitor_IoT\outputs\vd1_motion_probe' --width 960 --max-frames 120 --min-area 100 --save-video

& 'IOT_CAM\TrafficMonitor_IoT\.venv\Scripts\python.exe' 'IOT_CAM\TrafficMonitor_IoT\src\traffic_monitor\yolo_camera.py' --source 'IOT_CAM\TrafficMonitor_IoT\data\raw\vd1.mp4' --output 'IOT_CAM\TrafficMonitor_IoT\outputs\vd1_yolo_probe' --width 960 --max-frames 120 --save-video

& 'IOT_CAM\TrafficMonitor_IoT\.venv\Scripts\python.exe' 'IOT_CAM\TrafficMonitor_IoT\src\traffic_monitor\yolo_camera.py' --source 'IOT_CAM\TrafficMonitor_IoT\data\raw\vd1.mp4' --output 'IOT_CAM\TrafficMonitor_IoT\outputs\vd1_yolo_full' --width 960 --save-video
```

Môi trường `.venv` của lượt đo cũ dùng `ultralytics==8.4.190` và PyTorch CPU. Danh sách phụ thuộc hiện dùng nằm trong [`requirements.txt`](../requirements.txt). Khi tạo môi trường mới trên máy khác, việc cài PyTorch có thể phải theo hướng dẫn phù hợp hệ điều hành/CPU/GPU.

## Tiếp theo

1. Chọn và gán nhãn thủ công một số đoạn xe đi qua giao lộ: loại xe, box/ID ổn định, chiều đi và vùng áp dụng. Đánh nhãn cả xe đỗ/đứng chờ để tránh báo ngược chiều sai.
2. Vẽ ROI đường, các vùng một chiều và hướng hợp lệ cho **cảnh này**. Quy tắc phải dựa trên tín hiệu thực tế của giao lộ; ở giai đoạn này chỉ kiểm tra quỹ đạo, chưa kết luận vi phạm.
3. Thử thời gian dài hơn và so sánh số xe bỏ sót, ID switches, FPS trên cùng đoạn. Nếu tracking đủ tin cậy, mới triển khai `WrongWayDetector`.
4. Cần thêm clip có xe máy và bối cảnh Việt Nam để đánh giá sản phẩm dự kiến; `vd1` chỉ là clip khởi đầu.
