# TrafficMonitor IoT

Hệ thống giám sát vi phạm giao thông thông minh từ camera cố định phục vụ đồ án IoT.  
Tích hợp: **Xử lý video AI (YOLO/ByteTrack/MOG2) ➔ Django Web giám sát ➔ Canvas Editor quy ước tĩnh ➔ Bộ quy tắc vi phạm (Rule Engine) ➔ Tín hiệu đèn ngã tư ➔ Trích xuất ảnh bằng chứng (toàn cảnh + crop) ➔ Phê duyệt vi phạm**.

---

## 1. Cấu trúc tổng thể

```text
TrafficMonitor_IoT/
├── manage.py                          # Lệnh điều hành Django
├── requirements.txt                   # Phụ thuộc thị giác máy tính & AI
├── requirements-web.txt               # Phụ thuộc Django Web & PySerial
├── pytest.ini                         # Cấu hình kiểm thử tự động
├── menu.py                            # Menu CLI tương tác trực tiếp
├── run_web.bat                        # Khởi chạy Web giám sát
├── run_menu.bat                       # Khởi chạy menu console OpenCV
├── arduino/
│   └── traffic_signal/traffic_signal.ino   # Firmware đèn sa bàn (Arduino Uno)
├── docs/
│   ├── WEB_API_CONTRACT.md            # Hợp đồng API và chuẩn dữ liệu chung
│   ├── INTERSECTION_CONTROL_SPEC.md   # Quy tắc điều khiển pha đèn ngã tư
│   ├── ARDUINO_UNO_WEB_CONTROL.md     # Nạp sketch và kết nối Uno qua USB
│   └── *.md                           # Kế hoạch, hướng dẫn và báo cáo
├── web/                               # Dự án Django
│   ├── traffic_web/                   # Cấu hình project (settings, urls)
│   ├── monitor/                       # App: models, views, REST APIs
│   │   └── services/                  # Video Range 206, Evidence, Job, DroidCam
│   ├── templates/dashboard.html       # Màn hình giám sát, hai cột 68/32
│   └── static/                        # CSS dark mode, JS player/editor/signal
├── src/traffic_monitor/
│   ├── techgar_motion/                # Motion tracker + descriptor + occlusion
│   └── traffic_rules/                 # Module Python thuần Rule Engine
│       ├── geometry.py                # Điểm trong đa giác, cắt vạch, vector góc
│       ├── rules/                     # Ngược chiều, Lấn phân cách, Vượt đèn đỏ
│       ├── engine.py                  # Bộ phối hợp & khóa 1 event / lượt đi
│       └── signal_controller.py       # Sinh timeline đèn an toàn (vàng → cả hai đỏ 3s)
└── tests/                             # Test backend, rule, Arduino, live
```

---

## 2. Yêu cầu

- Windows 10/11, Python **3.12 hoặc 3.13** 64-bit.
- Internet khi dùng model lần đầu (tự tải `yolov8n.pt`, `yolo11s.pt` vào `weights/`).
- Nếu xử lý MP4, cần tự cung cấp `vd3.mp4` (hoặc `vd1.mp4`, `vd2.mp4`) vì video mẫu **không nằm trong repo**. Chế độ DroidCam không cần video mẫu.
- Arduino Uno R3 + cáp USB — *tùy chọn*, chỉ cần khi muốn điều khiển đèn sa bàn thật.

---

## 3. Cài đặt từ bản clone sạch

```powershell
cd TrafficMonitor_IoT
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.12.0 torchvision==0.27.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe -c "import torch, torchvision; from torchvision.ops import nms; print(torch.__version__, torchvision.__version__)"
```

Lệnh trên dùng bản PyTorch CPU để có cặp `torch`/`torchvision` tương thích. Nếu chạy CUDA, chọn lệnh cài đúng phiên bản GPU trên [trang cài đặt PyTorch](https://pytorch.org/get-started/locally/) trước khi cài các requirements. Không tạo venv với `--system-site-packages`: nó có thể lấy nhầm `torchvision` của Python toàn máy và báo `operator torchvision::nms does not exist`.

Nếu dùng MP4, chép video vào thư mục dữ liệu (thay đường dẫn ví dụ bằng file của bạn):

```powershell
Copy-Item -LiteralPath 'C:\duong-dan-cua-ban\vd3.mp4' -Destination .\data\raw\
```

Khởi tạo cơ sở dữ liệu:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

---

## 4. Chạy kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Nếu đã chép `vd3.mp4`: **55 passed**. Nếu chỉ dùng camera trực tiếp và chưa có video mẫu: **54 passed, 1 skipped**.

---

## 5. Cách chạy

### 5.1. Web giám sát (chính)

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

hoặc nhấp đúp **`run_web.bat`**, rồi mở **`http://127.0.0.1:8000/`**.

Giao diện chạy theo 3 bước:

1. **Chọn nguồn** — tải file MP4 lên / chọn video trong `data/raw/`, hoặc nhập URL DroidCam live (`http://<IP>:4747/video`).
2. **Vẽ quy ước tĩnh** — trên một frame chụp, vẽ *vùng Đường A*, *tim Đường A*, *Stop A1*, *Stop A2* và tương tự cho Đường B. Editor tự chia làn, suy ra chiều xe và tạo vùng giữa ngã tư.
3. **Giám sát tự động** — bấm **Lưu và Chạy** ở bước vẽ. Với MP4 mẫu, web chạy nhận diện, phát video kèm box/ID và có thể quét lỗi sai chiều/lấn làn; không chấm vượt đèn đỏ vì video không có lịch sử pha đèn đồng bộ. Nút **Quét Vi Phạm** dùng để quét lại. Với DroidCam, web nhận diện trực tiếp và dùng pha đèn hiện tại để xét vượt đèn đỏ. Bảng đèn nằm bên phải; danh sách vi phạm có ảnh toàn cảnh và ảnh crop để duyệt.

Web ưu tiên bản nhận diện **YOLOv8n** hoàn chỉnh cho MP4. Bản MOG2 cũ vẫn chọn được để so sánh chuyển động, nhưng nhãn xe của MOG2 là `unknown` vì nó không phân loại ô tô/xe máy.

YOLOv8n phát hiện tốt hơn với xe thật. Xe mô hình nhỏ có thể không được nhận ra dù camera và web chạy đúng; cần thử trên clip sa bàn và huấn luyện model với ảnh xe mô hình nếu muốn đánh giá vi phạm đáng tin cậy.

### 5.2. Menu console OpenCV

```powershell
.\.venv\Scripts\python.exe menu.py
```

hoặc nhấp đúp **`run_menu.bat`**. Chọn nguồn (video file hoặc DroidCam) → chọn thuật toán (YOLO11s chia ô / MOG2 + Kalman / YOLOv8n + ByteTrack) → chọn preset tốc độ → mở cửa sổ OpenCV trực tiếp.

### 5.3. Kết nối Arduino Uno (tùy chọn)

Chi tiết đầy đủ xem [`docs/ARDUINO_UNO_WEB_CONTROL.md`](docs/ARDUINO_UNO_WEB_CONTROL.md). Tóm tắt:

1. Dây: đường A đỏ/vàng/xanh ở **D2/D3/D4**, đường B ở **D5/D6/D7**, mỗi LED một điện trở hạn dòng, chung GND.
2. Mở `arduino/traffic_signal/traffic_signal.ino` trong Arduino IDE → chọn **Arduino Uno** + đúng cổng COM → **Upload**.
3. Đóng Serial Monitor / Arduino IDE, cắm Uno vào máy đang chạy Django.
4. Trên Web, vào bảng **Đèn giao thông**, chọn cổng COM của Uno → **Kết nối** → điều khiển chu kỳ hoặc bấm bóng đèn để đổi pha.

---

## 6. Biến môi trường (tùy chọn)

Web chạy được ngay với mặc định local. Khi muốn đổi:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `TRAFFIC_SECRET_KEY` | giá trị dev local | Khóa ký phiên Django |
| `TRAFFIC_DEBUG` | `1` | `1` bật debug, `0` tắt |
| `TRAFFIC_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Danh sách host, phân cách bằng dấu phẩy |

---

## 7. File không nằm trong repo

Các file nặng hoặc sinh ra lúc chạy bị `.gitignore`, không đẩy lên Git:

| Thư mục | Nội dung | Lý do |
|---|---|---|
| `data/raw/`, `data/derived/` | Video mẫu MP4 | Hàng trăm MB |
| `outputs/` | Kết quả chạy, ảnh chứng cứ, media | Sinh ra lúc chạy |
| `weights/` | `yolov8n.pt`, `yolo11s.pt` | Tự tải lại được |
| `db.sqlite3` | Cơ sở dữ liệu SQLite | Máy nào tự `migrate` |
| `.venv/`, `__pycache__/`, `.pytest_cache/` | Môi trường & cache | Máy nào tự tạo |

---

## 8. Luồng vận hành chi tiết trên Web

1. **Phát video và phủ box/ID** — chọn hoặc tải MP4, vẽ quy ước đường rồi bấm **Lưu và Chạy**. Web tự chạy YOLOv8n + ByteTrack, nạp box/ID và quỹ đạo lên canvas; có thể tua video nhờ HTTP Range 206.

2. **Canvas Editor** — vẽ quy ước đường trên frame chụp; phần vẽ là quy ước để xét luật, không huấn luyện AI. Box YOLO không có ID chỉ dùng kiểm tra, không dùng chấm vi phạm; chỉ xe có ID ByteTrack và độ tin cậy đủ cao mới vào bộ quy tắc.

3. **Bảng đèn tín hiệu** — Đường A và Đường B hiển thị trạng thái; hệ thống không cho cả hai cùng xanh. Chuyển tab **Thủ công** để bấm đèn hoặc nút **Cả hai đỏ**; tab **Tự động** cho phép đặt thời gian xanh/vàng. Đèn chạy độc lập khi xem MP4 mẫu; chỉ pha đèn đồng bộ với camera trực tiếp được dùng để chấm vượt đèn đỏ.

4. **Chấm vi phạm & bằng chứng** — mỗi xe chỉ phát đúng **1 event cho mỗi loại lỗi** trong một lượt đi; tự trích 1 ảnh toàn cảnh (bbox đỏ + nhãn ID) và 1 ảnh crop; bấm event để tua video về mốc vi phạm; người giám sát chuyển trạng thái duyệt.
