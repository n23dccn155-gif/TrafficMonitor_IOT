# TrafficMonitor IoT

Đồ án thử nghiệm theo dõi phương tiện từ video của một camera cố định. Chương trình mở video, vẽ khung bao và ID, hiển thị quá trình xử lý trực tiếp và lưu kết quả để so sánh thuật toán. Hai lựa chọn YOLO có thể phân loại ô tô, xe máy, xe tải và xe buýt; lựa chọn trừ nền chỉ nhận biết vùng chuyển động.

**Hiện tại dự án mới làm phát hiện và theo dõi.** Chưa có chức năng kết luận đi ngược chiều, sai làn hoặc vượt đèn đỏ. ID có thể mất hay đổi khi xe nhỏ, bị che hoặc nhận diện sai; số ID không phải số xe thật.

## Cài đặt trên Windows

Cần Git, Python **3.13 64-bit** và Internet để cài thư viện. Hai lựa chọn YOLO còn cần Internet để tải model ở lần chạy đầu. Mở PowerShell hoặc terminal trong IDE:

```powershell
git clone https://github.com/n23dccn155-gif/TrafficMonitor_IOT.git
cd TrafficMonitor_IOT
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`python --version` nên hiển thị Python 3.13. Nếu máy chỉ nhận lệnh `py`, dùng `py -3.13 -m venv .venv` để tạo môi trường. Không cần kích hoạt `.venv` hoặc cài Django.

### Chuẩn bị video

Video không có trong GitHub; chủ dự án sẽ gửi qua kênh riêng. Chép các file được gửi vào `data/raw/` và giữ đúng tên `vd1.mp4`, `vd2.mp4`, `vd3.mp4`. Có thể dùng video khác bằng cách dán đường dẫn đầy đủ khi menu hỏi, kể cả đường dẫn Windows có dấu cách.

- `vd3.mp4` được quay khi nguồn phát ở **1×**; nên dùng để thử đầu tiên.
- `vd2.mp4` được quay khi nguồn phát ở **2×**; chỉ nên dùng để thử độ bền. Phát chậm lại không khôi phục các frame đã thiếu.
- `vd1.mp4` là một cảnh giao lộ có nhiều ô tô.

Sau khi chuẩn bị video, chạy:

```powershell
.\.venv\Scripts\python.exe menu.py
```

Chọn `1` để mở file, chọn nhanh `1` cho `vd3.mp4` hoặc dán đường dẫn video của bạn. Sau đó chọn thuật toán, độ rộng xử lý và có lưu MP4 hay không. Để chạy thử lần đầu trên CPU, chọn **thuật toán 3** và **độ rộng 3 (640 px)**. Muốn thử các phương pháp khác, chạy lại menu với cùng video và chọn 1 hoặc 2.

## Các lựa chọn trong menu

### Nguồn hình

| Số | Nguồn | Ghi chú |
| --- | --- | --- |
| **1** | Video trên máy | Chọn nhanh `vd3`, `vd2`, `vd1` trong `data/raw/` hoặc dán đường dẫn khác. Menu báo nếu không tìm thấy file. |
| **2** | DroidCam live | Nhập URL `http://`, `https://` hoặc `rtsp://`. Chức năng live còn thử nghiệm; chưa xử lý tốt việc bỏ frame cũ và kết nối lại. |

### Thuật toán

| Số | Cách xử lý | Khi nào dùng | Giới hạn |
| --- | --- | --- | --- |
| **1. YOLO11s chia ô + ByteTrack** | Chia frame thành bốn ô chồng lấn, phát hiện phương tiện rồi ghép box thành ID. | Thử quan sát xe máy nhỏ ở góc camera cao. | Chạy nhiều lượt suy luận mỗi frame nên rất chậm trên CPU. |
| **2. MOG2 + Kalman** | Trừ nền để lấy vùng chuyển động, dùng Kalman và phép gán cặp để giữ ID. | So sánh với cách xử lý ảnh không dùng model học sâu. | Không phân loại xe; có thể bám bóng, người hoặc gộp nhiều xe vào một box. |
| **3. YOLOv8n + ByteTrack** | Phát hiện trên toàn frame một lần rồi ghép box thành ID. | Lựa chọn khởi đầu, thường nhẹ hơn số 1. | Có thể bỏ sót xe máy nhỏ, nhất là khi giảm độ phân giải. |

ByteTrack dùng các box từ YOLO để nối ID qua các frame. MOG2 tìm vùng ảnh thay đổi so với nền; Kalman dự đoán vị trí khi mất quan sát ngắn. Ở lựa chọn 2, vị trí chỉ do dự đoán có màu tím và ký hiệu `P`. **Cả ba lựa chọn dùng mã trong repo này.** Model `yolo11s.pt` và `yolov8n.pt` được tải tự động vào `weights/` khi dùng lần đầu; lựa chọn 2 không cần model.

### Độ rộng và cửa sổ xem trực tiếp

Menu cho chọn **1280 px (1)**, **960 px (2)** hoặc **640 px (3)**. Độ rộng nhỏ thường xử lý nhanh hơn nhưng có thể bỏ sót xe nhỏ. Với file video, ba mức này vẫn đọc tuần tự mọi frame; nếu máy xử lý chậm hơn FPS gốc, cửa sổ sẽ cập nhật chậm. Câu hỏi lưu MP4 mặc định là **không**; nhập `y` khi cần xem lại video đã đánh dấu.

Cửa sổ đặt ảnh gốc bên trái, ảnh có box/ID bên phải. Phím **Space** tạm dừng/tiếp tục, **N** đi một frame khi tạm dừng, **S** lưu ảnh, **Q/Esc** đóng cửa sổ và về menu. Hãy chạy từ terminal trên desktop của bạn để nhìn thấy cửa sổ OpenCV.

## Kết quả và cấu trúc repo

Mỗi lượt chạy tạo `outputs/runs/run_.../` chứa `tracks.jsonl` (box, ID, thời gian theo frame) và `summary.json` (thống kê lượt chạy). Nếu chọn lưu video sẽ có `annotated.mp4`; ảnh chụp bằng S nằm trong `snapshots/`.

- `menu.py`: điểm vào chính cho người dùng.
- `src/traffic_monitor/`: mã của ba lựa chọn, cửa sổ debug và tải model.
- `requirements.txt`: các thư viện cần cài.
- `data/CLIP_CATALOG.md`: thông tin và nguồn của các video thử nghiệm.
- `docs/`: kế hoạch, báo cáo và số liệu của các thử nghiệm trước. Một số đường dẫn output trong báo cáo chỉ tồn tại trên máy đã chạy thử.

Video trong `data/raw/`, video dẫn xuất trong `data/derived/`, model trong `weights/`, kết quả trong `outputs/` và môi trường `.venv/` **không được đưa lên Git**. Khi cập nhật mã, chạy `git pull` trong thư mục dự án; nếu `requirements.txt` thay đổi, chạy lại lệnh `pip install -r requirements.txt` ở phần cài đặt.

Mã nguồn được phát hành theo [GNU AGPL-3.0](LICENSE). Giấy phép mã nguồn không cấp quyền phân phối lại các video gốc; xem [danh mục clip](data/CLIP_CATALOG.md).
