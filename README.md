# TrafficMonitor IoT

Đồ án môn IoT thử nghiệm theo dõi phương tiện qua video từ một camera cố định. Chương trình phát hiện ô tô, xe máy và các phương tiện khác khi thuật toán hỗ trợ, vẽ khung bao, gán ID theo thời gian và hiển thị quá trình xử lý trong cửa sổ debug.

**Trạng thái hiện tại:** đây là bản thử nghiệm **phát hiện và theo dõi phương tiện**. Chương trình chưa phát hiện hay kết luận các lỗi đi ngược chiều, sai làn, vượt đèn đỏ. ID có thể đổi hoặc mất khi xe bị che khuất hay detector bỏ sót. Các thuật toán trong menu dùng để so sánh cách theo dõi, chưa được chứng minh chính xác cho mọi camera.

## Chạy thử trên Windows

Cần Python **3.13 64-bit** (phiên bản đã chạy thử), Git và kết nối Internet khi cài thư viện/tải model YOLO lần đầu. Kiểm tra `python --version` hiển thị 3.13, rồi mở PowerShell hoặc terminal trong IDE:

```powershell
git clone https://github.com/n23dccn155-gif/TrafficMonitor_IOT.git
cd TrafficMonitor_IOT
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe menu.py
```

Nếu máy chỉ nhận lệnh `py`, dùng `py -3.13 -m venv .venv` ở bước tạo môi trường. Các lần chạy sau chỉ cần mở terminal tại thư mục dự án và gọi `.\.venv\Scripts\python.exe menu.py`. Khi có mã mới, chạy `git pull` rồi cài lại `requirements.txt` bằng lệnh ở trên nếu file này thay đổi. Không cần kích hoạt môi trường ảo hay cài Django.

### Chuẩn bị video

Video **không có trong GitHub**; chủ dự án sẽ gửi clip qua kênh riêng. Chép các file nhận được vào `data/raw/` với tên `vd1.mp4`, `vd2.mp4`, `vd3.mp4` để dùng lựa chọn nhanh trong menu. `vd3.mp4` quay ở tốc độ 1× và là clip nên dùng để thử đầu tiên. `vd2.mp4` được quay từ nguồn phát 2×, chỉ nên dùng để thử độ bền của tracking, không dùng để đánh giá tốc độ chuyển động thật. Bạn cũng có thể dùng MP4 của mình ở bất kỳ thư mục nào: chọn nguồn file rồi dán đường dẫn đầy đủ, kể cả đường dẫn Windows có dấu cách hoặc dấu ngoặc kép.

Sau khi có video, chạy lại `menu.py` và chọn lần lượt:

```text
Nguồn:       1 → video file
Video:       1 → data/raw/vd3.mp4; hoặc dán đường dẫn MP4 của bạn
Thuật toán:  3 → YOLOv8n + ByteTrack, dễ chạy thử nhất
Độ rộng:    3 → 640 px để thử nhanh; chọn 2/1 nếu cần 960/1280 px
Lưu MP4:    Enter → không lưu; nhập y → lưu video debug
```

Lần đầu chạy thuật toán YOLO, chương trình tự tải `yolov8n.pt` hoặc `yolo11s.pt` vào `weights/`. Nếu tải không thành công, kiểm tra kết nối Internet rồi chạy lại. Cửa sổ OpenCV phải được chạy từ **terminal trên desktop của bạn**; cửa sổ có thể không xuất hiện nếu chạy qua một phiên terminal từ xa hoặc công cụ AI.

## Các lựa chọn trong `menu.py`

### Nguồn hình

- **1. Video file:** chọn nhanh `vd3`, `vd2`, `vd1` trong `data/raw/`, hoặc dán đường dẫn khác. Nếu file không tồn tại, menu yêu cầu nhập lại. Chương trình đọc tuần tự toàn bộ frame đến hết video, trừ khi bạn bấm Q/Esc.
- **2. DroidCam live:** nhập URL `http://`, `https://` hoặc `rtsp://` của camera. Đây là nhánh thử nghiệm; khả năng giữ frame mới nhất, đếm frame bị bỏ và kết nối lại chưa hoàn chỉnh. Nên dùng file MP4 để so sánh thuật toán. TechGAR ở lựa chọn thuật toán 2 hiện chỉ nhận file.

### Thuật toán

| Số | Cách làm | Khi nào dùng | Đánh đổi |
| --- | --- | --- | --- |
| **1. YOLO11s chia 4 ô + ByteTrack** | Chia ảnh thành các ô chồng lấn, nhận diện từng ô rồi ghép box thành ID. | Thử nhận diện xe máy nhỏ ở góc camera cao. | Chạy nhiều lượt YOLO cho mỗi frame nên **rất nặng CPU**; vẫn có thể bỏ sót hoặc đổi ID. |
| **2. TechGAR Motion Tracker** | Adapter gọi bộ theo dõi chuyển động dùng MOG2 trong **dự án cũ riêng của chủ repo**, rồi gán ID. | Đối chứng với phương pháp thị giác máy tính truyền thống nếu có repo TechGAR. | Repo này **không chứa mã TechGAR**; người chỉ clone TrafficMonitor sẽ không chạy được số 2. Không phân loại xe và có thể nhầm bóng/dao động nền. |
| **3. YOLOv8n + ByteTrack** | Một lượt YOLO trên toàn frame rồi ghép các box thành ID. | **Lựa chọn khởi đầu cho người mới**: tự tải model, ít phụ thuộc ngoài repo, thường nhanh hơn số 1. | Xe máy quá nhỏ có thể bị bỏ sót; CPU thường không đạt tốc độ video gốc. |

YOLO là phương pháp thị giác máy tính dùng mạng học sâu để tìm phương tiện. ByteTrack ghép các box giữa các frame để giữ ID. TechGAR dùng phát hiện chuyển động từ ảnh nền, nên có thể nhẹ CPU hơn nhưng không tự biết vật thể là xe gì. **Số ID được tạo ra không phải số xe đúng**; cần đối chiếu với video và nhãn thủ công để đánh giá.

Nếu bạn **đã có riêng** dự án TechGAR, đặt biến `TECHGAR_ROOT` trỏ tới thư mục `backend\main_detect` có file `src\techgar\motion_tracker.py`, rồi mới chọn thuật toán 2:

```powershell
$env:TECHGAR_ROOT = 'D:\duong-dan\TechGAR_Parking\backend\main_detect'
.\.venv\Scripts\python.exe menu.py
```

Nếu không có dự án đó, cứ chọn **1 hoặc 3**; không cần cài hay tìm TechGAR để chạy phần chính.

### Độ rộng, cửa sổ và kết quả

Menu có mức xử lý **1280, 960, 640 px**. Giảm độ rộng giúp bớt phép tính nhưng xe nhỏ khó nhận ra hơn. Với video file, các mức này **không bỏ frame có chủ ý**; hình có thể trông giật vì máy xử lý một frame lâu hơn thời gian phát của video. Chọn `y` ở câu hỏi lưu MP4 sẽ tốn thêm thời gian mã hóa và dung lượng đĩa.

Cửa sổ hiện ảnh gốc bên trái và ảnh có box/ID bên phải. Phím **Space** tạm dừng/tiếp tục, **N** đi một frame khi tạm dừng, **S** lưu ảnh, **Q** hoặc **Esc** đóng cửa sổ và quay lại menu.

Mỗi lượt chạy tạo một thư mục `outputs/runs/run_.../` với `tracks.jsonl` (quan sát theo frame) và `summary.json` (thống kê lượt chạy). Nếu chọn lưu video sẽ có thêm `annotated.mp4`; ảnh bấm S nằm trong `snapshots/`. `outputs/`, `weights/`, môi trường `.venv/` và video riêng đều không được đưa lên Git.

## Báo cáo và phép thử chuyên sâu

Để xem box/ID, chạy `menu.py`. Nếu cần tái lập phép thử cổ điển MOG2/FrameDiff hoặc so sánh YOLO với TechGAR, xem [hướng dẫn debug](docs/DEBUG_VIEWING.md), [báo cáo thuật toán cổ điển](docs/CLASSICAL_COMPARISON.md) và [báo cáo `vd3`](docs/P0_VD3_REPORT.md). Những phép thử đó có thể cần video dẫn xuất hoặc repo TechGAR riêng.

Tài liệu trong `docs/` ghi lại kế hoạch và kết quả trước đây, có thể nhắc tới output cục bộ không có sau khi clone. Xem thêm [phân tích hiệu năng](docs/PERFORMANCE.md) và [kế hoạch triển khai](docs/IMPLEMENTATION_PLAN.md).

## Mã nguồn, dữ liệu và giấy phép

Mã chính nằm trong `src/traffic_monitor/`; `requirements.txt` khóa các phụ thuộc Python. Mã dự án được phát hành theo [GNU AGPL-3.0](LICENSE). Model Ultralytics có điều khoản giấy phép riêng; xem [Ultralytics Licensing](https://www.ultralytics.com/license). Giấy phép mã nguồn không cấp quyền phân phối lại video gốc: các clip được chia sẻ riêng cần tuân theo điều khoản của nguồn video. Xem [danh mục clip](data/CLIP_CATALOG.md).
