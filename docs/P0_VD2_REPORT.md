# P0 — đánh giá ban đầu `vd2.mp4`

Ngày 26/10/2026. Đây là phép thử detector/tracker trên video người dùng cung cấp; **chưa gán nhãn thủ công** và chưa kết luận hành vi vi phạm.

## Clip và thời gian

Nguồn: [Intersection in Vietnam. Intense traffic, rush hour](https://www.youtube.com/watch?v=Kv2Z_NHz9KE&t=206s), người đăng hiển thị qua YouTube oEmbed: **Третій канал**. File trong `data/raw/` có 2552 × 1310, 30 FPS, 2.737 frame, 91,23 giây. Người dùng cho biết lượt quay đã phát ở **2×**; khung cuối có biểu tượng `2x`. Vì vậy timestamp trong JSONL tính từ đầu **file đã quay**, không phải mốc `t=206s` trên YouTube hoặc đồng hồ thực của giao lộ. Phát chậm lại để xem không khôi phục được các frame đã thiếu do phát 2×.

Cảnh là giao lộ Việt Nam từ trên cao, đông xe máy, nhiều xe che nhau. Có vạch qua đường và đèn, nhưng chưa xác minh đèn nào áp dụng cho từng hướng. Clip này sát bối cảnh đồ án hơn `vd1`, đồng thời là bài thử khó cho detection/ID. Xem [danh mục clip](../data/CLIP_CATALOG.md) để biết checksum và tình trạng quyền sử dụng.

## So sánh cùng 120 frame đầu

Cả hai chạy ở 960 × 493 trên CPU, cùng môi trường `.venv`. MOG2 dùng cấu hình thử `min_area=100`, `min_width=9`, `min_height=9`, `min_confirm_displacement=6`, `max_distance=100`. YOLO dùng model `yolov8n.pt` có sẵn, confidence 0,25 và ByteTrack.

| Thống kê output | TechGAR MOG2 | YOLOv8n + ByteTrack |
| --- | ---: | ---: |
| Thời gian xử lý 120 frame | 211,38 giây | 10,27 giây |
| Tốc độ xử lý quan sát được | 0,57 FPS | 11,68 FPS |
| ID khác nhau đã xuất | 148 | 193 |
| Số frame trung vị mỗi ID xuất hiện | 3 | 3 |
| ID xuất hiện ít nhất 30 frame | 11 | 22 |
| Box ở frame 60 | 17 | 20 |
| Box ở frame 110 | 11 | 20 |

Các số ID/box **không phải** số xe thật hoặc độ chính xác. Ở cảnh đông, ID có thể đứt/đổi nhiều lần; tốc độ xử lý cũng có thể thay đổi khi ROI, độ phân giải và mức tải máy thay đổi.

Quan sát video debug: MOG2 có vài box đúng trên xe máy nhưng bỏ sót phần lớn dòng xe, quỹ đạo/ID dễ gãy và xử lý rất chậm. YOLO có thêm nhãn `motorcycle`, song bỏ sót nhiều xe máy nhỏ/che khuất và có một box sai rất lớn trên tòa nhà bên trái cùng một box `bus` trên vùng cửa hàng. Đây là lỗi detector/miền dữ liệu và vùng quan sát; chỉ phát chậm video không sửa được. **Chưa dùng output này để bật cảnh báo ngược chiều, lấn làn hay vượt đèn đỏ.**

## Xem debug

- [Video 1× so sánh hình gốc và box/ID](../outputs/vd2_1x_yolo_probe_300/compare_raw_vs_debug.mp4) — 300 frame đầu, thời lượng 20 giây. [Video chỉ có box/ID](../outputs/vd2_1x_yolo_probe_300/annotated.mp4) và [JSONL](../outputs/vd2_1x_yolo_probe_300/tracks.jsonl) ở cùng thư mục.
- [Video so sánh gốc bên trái và kết quả YOLO bên phải](../outputs/vd2_live_debug/compare_raw_vs_debug.mp4) — 300 frame đầu (10 giây), được tạo để xem lại. Nếu trình đọc Markdown không phát video, mở file trong Explorer hoặc player.
- [Video YOLO có box/ID/quỹ đạo](../outputs/vd2_live_debug/annotated.mp4), [video MOG2](../outputs/vd2_motion_probe/annotated.mp4).
- JSONL và summary nằm cùng thư mục output; `outputs/` không được đưa vào Git.
- [Lệnh chạy cửa sổ debug trực tiếp](DEBUG_VIEWING.md): `--show`, **Space**, **N**, **Q**; MOG2 còn có `--show-mask`.

## Kiểm tra bản phát 1× (27/10/2026)

Đã tạo `data/derived/vd2_playback_1x_from_2x.mp4` bằng cách nhân đôi timestamp trong luồng H.264, không mã hóa lại. Bản này có 2.737 frame như raw, khoảng 15 FPS và 182,43 giây. Frame giải mã ở 4 vị trí cách xa nhau có hash trùng bản raw. Âm thanh không được đưa vào bản dẫn xuất vì chỉ cần hình cho detector.

Chạy lại YOLOv8n + ByteTrack trên cùng **300 frame đầu** ở 960 × 493 cho 483 Track ID, 6.850 quan sát và tốc độ xử lý 9,54 FPS trên CPU. So sánh `tracks.jsonl` của hai lượt: **danh sách box, nhãn và ID trùng ở cả 300 frame**; chỉ có mốc video thay đổi, ví dụ frame 150 từ 5.000 ms lên 9.998 ms. Vì vậy bản phát 1× giúp xem đúng nhịp thời gian giả định, nhưng không làm tracking ổn định hơn khi các frame đã được lấy từ nguồn phát 2×. Cần video ghi trực tiếp ở 1×, ROI và dữ liệu gán nhãn để đánh giá hoặc cải thiện ID switch.

Pipeline debug hiện tại dùng `yolov8n.pt` nằm trong `TechGAR_Parking/TechGAR_Parking/backend/` (SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`), Ultralytics **8.4.190**, tracker cấu hình `bytetrack.yaml`, PyTorch **2.12.0+cpu** và OpenCV **4.13.0**. Nhánh so sánh MOG2 dùng `MotionVehicleTracker` từ mã TechGAR và không phải model YOLO. Không có bộ phát hiện hành vi vi phạm trong lượt chạy P0 này.

## Quyết định tạm thời

Giữ `vd2` làm clip thử **xe máy/giao lộ đông**. YOLO là ứng viên phát hiện ban đầu vì MOG2 quá chậm trong mẫu này; chưa chọn pipeline chính. Bước tiếp theo là cấu hình ROI loại công trình/biển hiệu, đánh nhãn một số quỹ đạo xe máy/ô tô và đo bỏ sót, nhầm lớp, ID switch. Nên tìm thêm clip **tốc độ bình thường** cùng góc hoặc một clip tự quay để đánh giá thời gian/quỹ đạo thực tế, vì bản 2× không đủ để xác nhận các ngưỡng thời gian của rule.
