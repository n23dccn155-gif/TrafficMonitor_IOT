# File cục bộ ngoài Git

`data/raw/` giữ `vd1.mp4`–`vd3.mp4` gốc; `data/derived/` có bản `vd2` đổi timestamp. `weights/` giữ hai checkpoint tải từ Ultralytics. `outputs/` là kết quả chạy; `.venv/` là môi trường Python. Các thư mục này bị `.gitignore` loại khỏi bản chia sẻ. PDF 27 MB ở `references/papers/` cũng giữ tại máy để đọc, còn nguồn tải chính thức đã ghi trong [SOURCE_AUDIT.md](SOURCE_AUDIT.md).

Các báo cáo P0 mô tả kết quả đã chạy trên máy tác giả. Liên kết tương đối tới video/ảnh trong `outputs/` là **bằng chứng cục bộ**, không phải file bạn mới clone sẽ có. Người nhận repo phải tự cung cấp video và chạy `menu.py` để tạo output mới.

## Giữ lại ở máy tác giả

- `outputs/vd3_comparison_180/comparison_h264.mp4` và `frame_120.jpg`: so sánh YOLO/TechGAR trên `vd3`.
- `outputs/vd2_classical_compare_300/comparison_h264.mp4`, frame debug và summary: so sánh MOG2/FrameDiff.
- `outputs/vd2_1x_yolo_probe_300/compare_raw_vs_debug.mp4` và summary: mẫu video `vd2`.
- `outputs/vd1_yolo_full/`: lượt xử lý đủ clip `vd1`, dùng làm số liệu lịch sử.
- `outputs/runs/`: lượt chạy menu của người dùng, không dọn tự động.

Các MP4 chưa nén trùng với bản H.264, video debug `vd2` dài có thể tạo lại và output smoke/probe ngắn đã được dọn để giảm dung lượng. Không sửa hay xóa repo TechGAR cũ.
