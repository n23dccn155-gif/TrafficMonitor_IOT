# Kế hoạch triển khai và cổng kiểm chứng

**Tiến độ hiện tại:** `menu.py` có ba lựa chọn chạy từ repo này: YOLO11s chia ô, MOG2 + Kalman độc lập, YOLOv8n + ByteTrack. TechGAR chỉ còn trong phép thử lịch sử và không cần cho menu. Đã chạy mẫu `vd1.mp4` với TechGAR cũ và YOLO/ByteTrack; bản YOLO đã xuất toàn clip. Chưa có nhãn quỹ đạo, ROI hoặc đánh giá hành vi. Xem [báo cáo P0](P0_VD1_REPORT.md).

## Kiến trúc dự kiến

```text
GoPro cố định / MP4
  → video input
  → detector + tracker (MOG2 + Kalman và hai nhánh YOLO trong menu)
  → TrackObservation {camera, timestamp, ID, bbox, ground_point, trajectory, quality}
  → hình học ROI/làn/vạch dừng/hướng
  → Rule Engine + SignalProvider có đồng bộ thời gian
  → cảnh báo nghi vấn + ảnh/clip + rule_version
  → backend / kênh IoT / Web cấu hình và xem sự kiện
```

`Rule Engine` nhận dữ liệu track theo một hợp đồng chung, không phụ thuộc detector. Điểm kiểm tra đường là điểm tiếp xúc mặt đường/bottom-center của bbox khi chưa có calibration; cấu hình hình học gắn với kích thước frame và camera. Không dùng vị trí tâm bbox để tự suy ra xe đã qua vạch.

## P0 — video và tracking một camera

1. Chọn clip ban ngày, camera cố định, rõ xe và đường; ghi nguồn và quyền sử dụng. Ưu tiên có xe máy/ô tô, đủ frame liên tiếp, không rung hoặc thay góc.
2. Chạy ba nhánh hiện có trong `menu.py` trên cùng đoạn video: MOG2 + Kalman độc lập, YOLO11s chia ô và YOLOv8n + ByteTrack. Adapter TechGAR cũ chỉ để tái lập báo cáo lịch sử, không là phụ thuộc của chương trình chính.
3. Lấy track đã xác nhận, xuất timestamp, Track ID, bbox, `cx/cy`, lịch sử và chất lượng theo schema thống nhất. Phân biệt quan sát thật với vị trí dự đoán để không đưa dự đoán quá lâu vào rule.
4. Xuất video box/ID và JSONL, xem bằng mắt ID switch, xe bị bỏ sót, bóng đổ, che khuất và xe đứng yên.
5. Gán nhãn một đoạn kiểm tra và so sánh độ liên tục ID, bỏ sót xe, box sai và FPS của ba nhánh trên **cùng clip**. Chưa dùng nhánh nào để kết luận vi phạm trước khi có số liệu.
6. Cấu hình ROI và hướng hợp lệ, làm `WrongWayDetector` trên nhiều quan sát và có ngưỡng khoảng cách/thời gian, chống báo lặp.

**Xong P0 khi:** có một clip đầu vào có xuất xứ, video đầu ra có box/ID/quỹ đạo, file sự kiện/track đọc được, bảng lỗi tracking, và một vài ca đúng/sai chiều được đánh nhãn thủ công. Nếu clip không có hành vi sai chiều, phải ghi rõ chưa đo được recall sự kiện.

## P1 — ba bộ phân tích hành vi

- **Ngược chiều:** so quỹ đạo trong ROI với hướng hợp lệ, ngưỡng quãng đường/thời gian và độ tin cậy track; dừng/che khuất/mất ID trả về chưa đủ dữ liệu.
- **Lấn/đi sai làn:** chỉ báo khi cắt ranh giới cấu hình cấm cắt hoặc vào làn không phù hợp theo loại xe đã biết; có hysteresis để tránh rung quanh vạch.
- **Đèn:** đánh dấu thời điểm qua vạch bằng timeline video và so với tín hiệu **áp dụng cho làn/hướng/loại xe đó**. Đèn vàng, nhấp nháy, tín hiệu riêng và clock lệch phải có quy tắc riêng hoặc trả về chưa đủ dữ liệu.
- Lưu cả ca âm tính: đi đúng chiều, chuyển làn hợp lệ, qua vạch lúc xanh, xe đã ở trên vạch trước khi đổi pha, loại xe chưa xác định.

## P2 — IoT, dữ liệu và Web

Thiết kế event ID chống lưu trùng, lưu bằng chứng và `rule_version`/`effective_at`. Chọn và thử kênh truyền sự kiện (MQTT là ứng viên hợp với bài học), mất kết nối và gửi lặp. Web sửa ROI/rule theo phiên bản, xem video và duyệt `pending`/`confirmed`/`dismissed`.

## P3 — GoPro và sa bàn

Xác nhận model/firmware GoPro rồi mới thử live. Chọn board đèn sau khi biết rubric và kích thước sa bàn; phần mềm phải chạy được với MP4 và nguồn tín hiệu mô phỏng. Trên sa bàn, đồng bộ chính xác log pha đèn với video. Báo cáo kết quả sa bàn tách khỏi video giao thông thật.

## Chỉ số tối thiểu

Ghi precision/recall/F1 **ở mức sự kiện** trên bộ clip có nhãn; số lần đổi ID, xe bị bỏ sót, FPS, độ trễ cảnh báo và tỷ lệ thông điệp trùng khi thử IoT. Mọi chỉ số phải ghi số clip, điều kiện quay và cách gán nhãn. Không dùng kết quả phát hiện vật thể để suy thành độ chính xác phát hiện vi phạm.
