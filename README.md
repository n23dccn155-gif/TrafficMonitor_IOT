# TrafficMonitor IoT

Đồ án môn IoT: xem video giao thông bằng camera cố định, vẽ box, loại phương tiện và ID theo dõi. **Hiện tại đây là prototype tracking**, chưa phát hiện hay kết luận vi phạm giao thông. ID có thể đổi khi xe bị che hoặc detector bỏ sót.

## Cài và chạy trên Windows sau khi clone

Máy cần Python **3.12 64-bit**, Git và Internet cho lần cài thư viện/tải model đầu tiên. Các lệnh sau chạy trong PowerShell, từ **thư mục `TrafficMonitor_IoT`**:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe menu.py
```

Nếu Python đã là 3.12 nhưng `py -3.12` không có, thay bằng `python -m venv .venv`. Không cần kích hoạt môi trường ảo. Mặc định pip có thể cài PyTorch CPU; muốn dùng NVIDIA GPU, cài bản PyTorch CUDA theo [trang cài đặt chính thức](https://docs.pytorch.org/get-started/locally/) trước khi cài `requirements.txt`. Hai pipeline YOLO tự dùng CUDA khi `torch.cuda.is_available()` là `True`.

Lần đầu chọn thuật toán 1 hoặc 3, chương trình tải checkpoint chính thức vào `weights/`; các lần sau dùng lại bản đã tải. Nếu máy offline, lấy `yolo11s.pt` hoặc `yolov8n.pt` từ [Ultralytics assets](https://github.com/ultralytics/assets/releases) và đặt đúng tên trong `weights/`.

**Video không nằm trong Git.** Dán đường dẫn tới MP4 của bạn ở menu, hoặc chép `vd1.mp4`, `vd2.mp4`, `vd3.mp4` vào `data/raw/` để dùng phím tắt 1/2/3. Nếu chưa có video, mục chọn nhanh sẽ báo thiếu file và cho nhập lại. Video gốc của nhóm và bản PDF tham khảo được loại khỏi commit vì dung lượng và quyền chia sẻ chưa được xác minh.

Trong menu, chọn nguồn file → thuật toán → chất lượng 640/960/1280 px → có lưu MP4 hay không. File được đọc tuần tự, không bỏ frame. Cửa sổ có ảnh gốc bên trái, kết quả bên phải; **Space** tạm dừng, **N** đi một frame, **S** chụp ảnh, **Q/Esc** về menu. Mỗi lượt lưu `tracks.jsonl` và `summary.json` dưới `outputs/runs/`; MP4 chỉ được tạo nếu bạn chọn lưu. Chạy từ terminal desktop để cửa sổ OpenCV hiện trên màn hình của bạn.

## Chọn thuật toán

| Menu | Cách hoạt động | Khi nào nên dùng | Chi phí CPU và hạn chế |
| --- | --- | --- | --- |
| **1. YOLO11s chia 4 ô + ByteTrack** | Chia ảnh thành bốn vùng có chồng lấn, phát hiện xe ở mỗi vùng, gộp box rồi ghép ID. | Xem xét xe máy nhỏ ở góc camera cao khi tốc độ không quan trọng. | Bốn lượt suy luận bằng model lớn hơn mỗi frame; rất chậm trên CPU, vẫn có thể đổi ID. Đây là phương án **thử nghiệm**, chưa xác nhận bằng nhãn thật. |
| **2. TechGAR MOG2** | Repo TechGAR riêng trừ nền để tìm vùng chuyển động, rồi ghép quỹ đạo. | Baseline thị giác cổ điển; có thể xem motion mask. | Tốn nhiều xử lý ảnh ở độ phân giải cao; có thể mất xe đứng yên, không nhận biết loại xe. **Tùy chọn**, cần repo riêng. |
| **3. YOLOv8n + ByteTrack** | Một lượt suy luận bằng model nhỏ trên toàn frame, rồi ghép box thành ID. | **Khuyến nghị để bạn mới chạy thử**: ít phụ thuộc, tương đối nhanh và có loại xe. | Ở ảnh rộng có thể bỏ sót xe máy nhỏ; chưa đạt 30 FPS trên CPU thử nghiệm. |

`vd3` là 30 FPS, nên thời gian thực đòi hỏi tối đa ~33 ms cho **toàn bộ** một frame (giải mã, phát hiện, tracking, vẽ, hiển thị). Đã đo 45 frame đầu ở 640 px, chạy tuần tự trên CPU, không mở GUI/ghi MP4: lựa chọn 1 **3,79 FPS**, lựa chọn 2 **22,71 FPS**, lựa chọn 3 **10,83 FPS**. Đây là tốc độ, **không phải độ chính xác**; hạ độ phân giải có thể làm mất xe máy nhỏ. Xem [phân tích hiệu năng](docs/PERFORMANCE.md).

### TechGAR tùy chọn

Lựa chọn 2 gọi mã trong repo TechGAR cũ qua `single_camera.py`; dự án này **không chép thuật toán TechGAR**. Nếu bạn có repo đó, đặt biến `TECHGAR_ROOT` trỏ đến thư mục `backend/main_detect` chứa `src/techgar/motion_tracker.py`:

```powershell
$env:TECHGAR_ROOT = 'D:\duong-dan\TechGAR_Parking\TechGAR_Parking\backend\main_detect'
.\.venv\Scripts\python.exe menu.py
```

Không có repo TechGAR, lựa chọn 1 và 3 vẫn hoạt động; menu sẽ báo rõ khi chọn 2. Không cần cài Django để chạy vòng lặp camera. DroidCam hiện là nhánh thử nghiệm, chưa có bộ đệm frame mới nhất và cơ chế nối lại đáng tin cậy; dùng file MP4 để so sánh các thuật toán.

## Cấu trúc bản chia sẻ

- `menu.py`: điểm vào cho người dùng.
- `src/traffic_monitor/`: ba pipeline, hiển thị và tải model.
- `requirements.txt`: thư viện cài qua pip; `.venv/` không đưa lên Git.
- `weights/`, `data/raw/`, `outputs/`: cache model, video riêng và kết quả chạy; không đưa lên Git.
- `docs/`: kế hoạch, báo cáo thử nghiệm và [danh mục nguồn](docs/SOURCE_AUDIT.md). Các liên kết tới output/video trong báo cáo lịch sử chỉ tồn tại trên máy đã chạy thử.
- `run_*.cmd`: launcher tái lập thí nghiệm cũ, cần clip cục bộ và đôi khi cần TechGAR; không phải điểm vào chính.

## Giấy phép và dữ liệu

[Ultralytics công bố YOLO và weights theo AGPL-3.0 hoặc Enterprise](https://www.ultralytics.com/license); [Supervision dùng MIT](https://github.com/roboflow/supervision/blob/develop/LICENSE.md). Trước khi công bố repo hoặc dùng cho sản phẩm, nhóm cần xác định giấy phép dự án phù hợp; các clip YouTube không được tự động đưa lên Git vì chưa xác minh quyền tái phân phối. Số ID sinh ra không thay thế đánh giá bằng nhãn xe thật. Xem [kế hoạch](docs/IMPLEMENTATION_PLAN.md) và [danh mục clip](data/CLIP_CATALOG.md).
