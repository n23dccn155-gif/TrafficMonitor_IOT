# TrafficMonitor IoT — theo dõi phương tiện từ video

Đồ án môn IoT dùng camera cố định để phát hiện phương tiện, vẽ box và gán ID theo thời gian. **Phiên bản hiện tại chỉ thử nghiệm tracking**: chưa phát hiện đi ngược chiều, sai làn hay vượt đèn đỏ, và không dùng để kết luận vi phạm. ID có thể đổi khi xe bị che hoặc detector bỏ sót.

## Bắt đầu trên Windows

Khuyến nghị Python **3.12 64-bit** và cần Internet cho lần cài thư viện/tải model đầu tiên. Mở PowerShell rồi chạy:

```powershell
git clone https://github.com/n23dccn155-gif/TrafficMonitor_IOT.git
cd TrafficMonitor_IOT
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe menu.py
```

Nếu Python đã là 3.12 nhưng lệnh `py -3.12` không có, dùng `python -m venv .venv`. Không cần kích hoạt môi trường ảo. Để cập nhật mã về sau, chạy `git pull` **trong thư mục vừa clone**. Không chép `.venv` từ máy khác sang.

Mặc định pip có thể cài PyTorch CPU. Nếu có NVIDIA GPU và muốn dùng CUDA, cài PyTorch theo [hướng dẫn chính thức](https://docs.pytorch.org/get-started/locally/) **trước** lệnh cài `requirements.txt`; hai pipeline YOLO tự dùng CUDA khi `torch.cuda.is_available()` trả `True`. Lần đầu chọn thuật toán 1 hoặc 3, chương trình tải checkpoint chính thức vào `weights/`; các lần sau dùng lại bản đã tải. Nếu máy offline, lấy `yolo11s.pt` hoặc `yolov8n.pt` từ [Ultralytics assets](https://github.com/ultralytics/assets/releases) và đặt đúng tên trong `weights/`.

### Chuẩn bị video và xem debug

**Repo không chứa video.** Khi menu hỏi nguồn, chọn file rồi dán đường dẫn MP4 trên máy của bạn, kể cả đường dẫn có dấu cách. Các phím tắt `1`, `2`, `3` trong bước chọn file chỉ hoạt động nếu bạn tự đặt `vd3.mp4`, `vd2.mp4`, `vd1.mp4` tương ứng trong `data/raw/`; nhấn Enter cũng chọn `vd3.mp4`. Nếu file chưa có, menu báo lỗi và cho nhập lại.

Chọn tiếp thuật toán → độ rộng xử lý 640/960/1280 px → có lưu MP4 debug hay không (mặc định **không**). Với **file video**, cả ba mức chất lượng đều đọc tuần tự mọi frame; cửa sổ có thể cập nhật chậm hơn tốc độ phát gốc nếu CPU không xử lý kịp. Ảnh gốc ở bên trái, box/ID ở bên phải; **Space** tạm dừng/tiếp tục, **N** đi một frame khi đang tạm dừng, **S** lưu ảnh và **Q/Esc** đóng cửa sổ để về menu. Chạy từ terminal desktop của bạn để cửa sổ OpenCV hiện trên màn hình.

Mỗi lượt tạo thư mục riêng dưới `outputs/runs/` với `tracks.jsonl` (box, ID và timestamp theo frame), `summary.json` (số frame và FPS xử lý), ảnh chụp nếu nhấn **S**, và `annotated.mp4` nếu đã chọn lưu. `outputs/`, video, model weights và `.venv/` đều bị Git bỏ qua; bạn của bạn sẽ tự tạo output trên máy họ.

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

Không có repo TechGAR, lựa chọn 1 và 3 vẫn hoạt động; menu sẽ báo rõ khi chọn 2. Không cần cài Django để chạy vòng lặp camera. **DroidCam còn thử nghiệm**: chưa có bộ đệm chỉ giữ frame mới nhất, thống kê frame bị bỏ hay cơ chế nối lại đáng tin cậy; hãy dùng file MP4 để so sánh thuật toán.

## Cấu trúc bản chia sẻ

- `menu.py`: điểm vào cho người dùng.
- `src/traffic_monitor/`: ba pipeline, hiển thị và tải model.
- `requirements.txt`: thư viện cài qua pip; `.venv/` không đưa lên Git.
- `weights/`, `data/raw/`, `outputs/`: cache model, video riêng và kết quả chạy; không đưa lên Git.
- `docs/`: kế hoạch, báo cáo thử nghiệm và [danh mục nguồn](docs/SOURCE_AUDIT.md). Các liên kết tới output/video trong báo cáo lịch sử chỉ tồn tại trên máy đã chạy thử.
- `run_*.cmd`: launcher tái lập thí nghiệm cũ, cần clip cục bộ và đôi khi cần TechGAR; người mới chỉ cần chạy `menu.py`.

## Giấy phép và dữ liệu

Mã nguồn dự án được phát hành theo [GNU AGPL-3.0](LICENSE). [Ultralytics công bố YOLO và weights theo AGPL-3.0 hoặc Enterprise](https://www.ultralytics.com/license); [Supervision dùng MIT](https://github.com/roboflow/supervision/blob/develop/LICENSE.md). Giấy phép mã nguồn **không** cấp quyền tái phân phối các clip YouTube, nên video gốc không được đưa lên Git. Số ID sinh ra không thay thế đánh giá bằng nhãn xe thật. Xem [kế hoạch](docs/IMPLEMENTATION_PLAN.md) và [danh mục clip](data/CLIP_CATALOG.md).
