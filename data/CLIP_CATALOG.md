# Danh mục video thử nghiệm

## `raw/vd1.mp4`

- Người đưa vào workspace: người dùng, ngày 26/10/2026.
- Nguồn người dùng cung cấp: [YouTube — 4 Corners Camera Downtown](https://www.youtube.com/watch?v=1H0iTzv2jiQ), tác giả hiển thị qua YouTube oEmbed là **City of Coldwater MI**. Khung hình có watermark `COLDWATER` / `CBPU`. Chưa xác minh giấy phép tái phân phối; dùng nội bộ để thử thuật toán.
- Metadata đọc bằng OpenCV: 2554 × 1440, 30 FPS, 1.787 frame, khoảng 59,57 giây, 117.069.044 byte. SHA-256: `3ae14f8dd6cda274dc6f20c1fc7b5482a2cf691a5b12a6d6525fd8ecc129f486`.
- Cảnh: camera cố định trên cao nhìn xuống giao lộ ban ngày, có ô tô/xe tải, vạch dừng và tín hiệu đèn. Đèn tín hiệu nhỏ trong toàn cảnh; chưa kiểm tra tín hiệu áp dụng cho từng luồng xe.
- Phù hợp: kiểm tra phát hiện xe, tracking, quỹ đạo, vạch và ROI. Chưa phù hợp để đánh giá xe máy hoặc quy tắc giao thông Việt Nam; chưa có nhãn hành vi vi phạm.
- Kết quả P0 ban đầu: xem [`docs/P0_VD1_REPORT.md`](../docs/P0_VD1_REPORT.md).

## `raw/vd2.mp4`

- Nguồn người dùng cung cấp: [YouTube — Intersection in Vietnam. Intense traffic, rush hour](https://www.youtube.com/watch?v=Kv2Z_NHz9KE&t=206s), tác giả hiển thị qua YouTube oEmbed là **Третій канал**. Chưa xác minh giấy phép tái phân phối; dùng nội bộ để thử thuật toán.
- Metadata đọc bằng OpenCV: 2552 × 1310, 30 FPS, 2.737 frame, khoảng 91,23 giây, 164.093.895 byte. SHA-256: `1b643d5cbb768b2a870af9f541e444235cda8b70c3b08bef766b21fc86518849`.
- Người dùng cho biết bản quay đang phát ở **2×**; ở khung cuối cũng thấy overlay `2x`. FPS file vẫn là 30, nhưng không thể dùng FPS đó để khẳng định thời gian thực của cảnh giao thông. Cần đánh giá việc xe đi xa hơn giữa hai frame và mất quan sát do tua nhanh; phát chậm lại để xem **không khôi phục** các frame gốc đã thiếu.
- Cảnh: góc cố định trên cao nhìn giao lộ Việt Nam, rất nhiều xe máy, xe ô tô, vạch dừng và đèn. Mật độ/che khuất cao khiến tracking khó hơn `vd1` nhưng sát bối cảnh đồ án.
- Chưa có nhãn xe/ID/hành vi hoặc kiểm chứng tín hiệu áp dụng cho từng hướng. Đã có [báo cáo thử detector/tracker](../docs/P0_VD2_REPORT.md) và video debug 10 giây đầu.

## `derived/vd2_playback_1x_from_2x.mp4`

- Dẫn xuất từ `raw/vd2.mp4` ngày 27/10/2026 bằng FFmpeg `-itsscale 2 -map 0:v:0 -an -c:v copy`: kéo giãn timestamp, sao chép nguyên luồng H.264, bỏ âm thanh vì pipeline chỉ phân tích hình. [Tài liệu FFmpeg về `-itsscale` và `-c copy`](https://ffmpeg.org/ffmpeg.html).
- OpenCV đọc được 2552 × 1310, 2.737 frame, khoảng 15 FPS, 182,43 giây, 161.886.558 byte. SHA-256: `323a4068587afc04c588a9dc6229b6995c1cd63cc71a6ce8bee7bcc3aa12dbc8`.
- Frame 0, 100, 1368 và 2736 sau giải mã có hash giống hệt bản raw. Đây là bản **phát chậm theo giả định nguồn được ghi khi phát 2×**, không phải video nguồn 1× thật: khoảng cách không gian giữa các frame và số frame đã bị bỏ qua vẫn như cũ.
- [Kết quả YOLO/ByteTrack 300 frame đầu trên bản 1×](../docs/P0_VD2_REPORT.md) và [cách mở cửa sổ debug](../docs/DEBUG_VIEWING.md). Dùng nội bộ để thử nghiệm; quyền tái phân phối vẫn theo nguồn gốc ở trên.

## `raw/vd3.mp4`

- Người dùng bổ sung ngày 27/10/2026 và xác nhận quay khi nguồn phát **1×**. URL nguồn và điều khoản tái phân phối chưa được cung cấp/xác minh; hiện chỉ dùng nội bộ để thử thuật toán.
- OpenCV đọc được 1912 × 906, 30 FPS, 2.466 frame, 82,2 giây, 77.176.470 byte. SHA-256: `a5f738848d9bdeaa57fb2fa87ddedd04f3074823c8160ac307f6b3b1559d4b9c`.
- Góc cố định nhìn xuống giao lộ Việt Nam đông xe máy, có ô tô, vạch qua đường và đèn tín hiệu. Chưa có nhãn xe/ID/hành vi, chưa xác minh đèn áp dụng cho từng hướng.
- [So sánh YOLO với tracker TechGAR trên 180 frame đầu](../docs/P0_VD3_REPORT.md); không đổi tốc độ phát video.

Khi thêm clip mới, ghi URL/nguồn, điều khoản sử dụng, góc quay, độ phân giải, FPS, thời lượng, loại xe, vùng/vạch nhìn thấy, nhãn hành vi và giới hạn của clip trước khi so sánh thuật toán.
