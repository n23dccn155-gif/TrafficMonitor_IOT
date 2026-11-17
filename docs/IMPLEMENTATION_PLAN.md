# Kế hoạch triển khai và cổng kiểm chứng

**Quyết định nhóm ngày 09/11/2026, chỉnh mục tiêu ngày 13/11/2026:** dùng **phát hiện xe và ID hiện có** để hoàn thiện bản demo phần mềm gồm Web và ba quy tắc ngược chiều/lấn qua phân cách/vượt đỏ. Mặc định YOLOv8n + ByteTrack; YOLO11s chia ô và MOG2 + Kalman vẫn chạy để so sánh. Cải thiện model và đánh giá độ chính xác sẽ làm sau, không chặn việc lập trình. Điện thoại DroidCam là nguồn live và Arduino Uno R3 phát trạng thái đèn sa bàn qua USB Serial khi có phần cứng. Phần Web nằm trong [W0–W7](WEB_MVP_PLAN.md). Xem [báo cáo `vd3`](P0_VD3_REPORT.md) và [kế hoạch video/rule](VIDEO_FIRST_WEB_PLAN.md).

## Kiến trúc dự kiến

```text
Điện thoại cố định dùng DroidCam / MP4 quay từ cùng góc
  → video input
  → detector + tracker (MOG2 + Kalman và hai nhánh YOLO trong menu)
  → TrackObservation {camera, timestamp, ID, bbox, ground_point, trajectory, quality}
  → hình học ROI/làn/vạch dừng/hướng
  → Rule Engine + SignalProvider có đồng bộ thời gian
  → cảnh báo nghi vấn + ảnh/clip + rule_version
  → backend / kênh IoT / Web cấu hình và xem sự kiện
```

`Rule Engine` nhận dữ liệu track theo một hợp đồng chung, không phụ thuộc detector. Điểm kiểm tra đường là điểm tiếp xúc mặt đường/bottom-center của bbox khi chưa có calibration; cấu hình hình học gắn với kích thước frame và camera. Không dùng vị trí tâm bbox để tự suy ra xe đã qua vạch.

## P0 — dùng tracking hiện có để dựng bản chạy xuyên suốt

1. Mở `vd3.mp4` bằng pipeline YOLOv8n + ByteTrack hiện có, xác nhận có box/ID và `tracks.jsonl`, `summary.json`. Web phát video gốc và phủ box/ID theo `video_timestamp_ms`; đây là lát cắt chức năng đầu tiên để nhóm xem được tiến trình xử lý.
2. Chuẩn hóa output `{timestamp, track_id, bbox, ground_point, observation_kind, vehicle_type?}` từ cả ba pipeline; giữ vị trí dự đoán khác màu so với vị trí đo từ ảnh. Chạy được cả ba lựa chọn từ Web mà không phụ thuộc repo cũ.
3. Kiểm tra thủ công một số frame của `vd3` để biết ID/box có thể sai ở đâu; lưu ca lỗi trong báo cáo. Cho các rule trả `INSUFFICIENT_EVIDENCE` nếu track đứt ở thời điểm quyết định. **Không đợi gán nhãn toàn bộ hoặc chốt model tốt nhất mới xây Web/rule.**

**Xong P0 khi:** Web phát `vd3`, hiện box/ID từ output thật, chạy lại được ít nhất pipeline mặc định và báo rõ frame thiếu/ID đứt. Đây là cổng **chức năng**, chưa phải chứng nhận độ chính xác nhận diện. P0 chưa cần có sự kiện vi phạm.

**Chọn baseline lúc dựng Web:** dùng YOLOv8n + ByteTrack đang có để sớm thấy box/ID, rồi giữ MOG2 + Kalman và YOLO11s chia ô làm lựa chọn đối chứng. ByteTrack là thuật toán ghép box qua frame, vì vậy ID đúng vẫn phụ thuộc detector và cảnh quay; [bài báo ByteTrack](https://arxiv.org/abs/2110.06864) mô tả bước ghép này. [OpenCV](https://docs.opencv.org/4.13.0/d1/dc5/tutorial_background_subtraction.html) mô tả MOG2 là trừ nền tạo mask vật thể chuyển động trên camera tĩnh, nên nhánh này không tự phân loại ô tô/xe máy. YOLO11s chia bốn ô gọi detector nhiều lần mỗi frame theo mã hiện có. Báo cáo `vd3` cũ chỉ là phép thử ngắn, không đủ để công bố độ chính xác.

## P1 — Web cấu hình cảnh/pha và ba bộ phân tích hành vi offline

Trang Web đầu tiên cho vẽ **hai vùng chiều xe chạy của mỗi đường A/B**, mũi tên chiều hợp lệ, đường phân cách hai chiều, vùng giữa ngã tư và vạch dừng; hai chiều của cùng đường dùng chung nhóm đèn. Trên video ghi sẵn, Web cho đặt timeline pha theo **thời gian video**, nhãn `simulation` hoặc `manual_annotation`. Không có hai công tắc độc lập khiến hai đường cùng xanh. Xem [đặc tả điều khiển ngã tư](INTERSECTION_CONTROL_SPEC.md).

Nút chụp frame dùng để **gán đường A/B và quy ước mặt đường trên ảnh đã quay**, không phải vẽ một ngã tư mới hoặc gán ID xe bằng tay. Detector/tracker tự tạo box, loại xe nếu biết và ID. Khi rule kích hoạt, lưu một ảnh toàn khung có box của xe đó và một crop xe; các frame tiếp theo không tạo lại cùng loại event cho cùng ID/lượt đi. Khóa chống trùng theo `rule_run_id`, `segment_id`, `track_id`, `rule_type`, đồng thời xử lý trạng thái kích hoạt của từng rule.

- **Ngược chiều:** so quỹ đạo trong ROI với hướng hợp lệ, ngưỡng quãng đường/thời gian và độ tin cậy track; dừng/che khuất/mất ID trả về chưa đủ dữ liệu.
- **Lấn qua phân cách hai chiều:** chỉ báo khi xe vượt đường phân cách giữa hai vùng chiều của cùng đường và duy trì nhiều frame quan sát; có dải đệm để tránh rung box. Bản sa bàn đầu giả định mỗi đường có một vùng cho mỗi chiều.
- **Đèn:** đánh dấu thời điểm qua vạch bằng timeline video do Web lưu và so với tín hiệu **áp dụng cho làn/hướng/loại xe đó**. Đèn vàng, nhấp nháy, tín hiệu riêng và clock lệch phải có quy tắc riêng hoặc trả về chưa đủ dữ liệu.
- Lưu cả ca âm tính: đi đúng chiều, chạm vạch nhưng chưa sang chiều kia, đi qua vùng giữa ngã tư, qua vạch dừng lúc xanh, xe đã ở trên vạch trước khi đổi pha, loại xe chưa xác định.

## P2 — Web duyệt sự kiện sau khi có tracking và rule

Django 5.2 LTS bắt đầu **ngay từ P0** bằng phát video và box/ID để rà lỗi tracking; sau khi P1 có rule, Web thêm timeline và sự kiện từ output của worker chạy trên MP4. Có trang duyệt `pending`/`confirmed`/`dismissed`, lưu cấu hình cảnh theo phiên bản và cho tua đến thời điểm sự kiện. Worker suy luận chạy riêng khỏi HTTP request; Web hiển thị rõ chế độ phát lại, không giả làm live. Dùng SQLite cho demo một laptop; MQTT vẫn là mở rộng tùy rubric.

## P3 — DroidCam, Arduino Uno và sa bàn live

Thử URL `/video` của DroidCam trên laptop, đo độ trễ và độ ổn định. Sa bàn dự tính 4 cụm đèn với hai nhóm đối diện điều khiển bởi D2–D7 của Arduino Uno; mỗi LED có điện trở riêng. Web gửi yêu cầu đổi pha cho tiến trình điều khiển; Uno cập nhật LED rồi trả ACK qua USB Serial với số thứ tự, pha và `millis()`. Laptop ghi thời gian nhận ACK cùng clock dùng cho frame; ca gần lúc đổi pha, mất tín hiệu hoặc quá hạn ACK phải trả về chưa đủ bằng chứng. Tích hợp bộ đọc frame mới nhất và reset ID khi mất hình. Báo cáo sa bàn tách khỏi video giao thông thật.

## Chỉ số tối thiểu

Ghi precision/recall/F1 **ở mức sự kiện** trên bộ clip có nhãn; số lần đổi ID, xe bị bỏ sót, FPS, độ trễ cảnh báo và tỷ lệ thông điệp trùng khi thử IoT. Mọi chỉ số phải ghi số clip, điều kiện quay và cách gán nhãn. Không dùng kết quả phát hiện vật thể để suy thành độ chính xác phát hiện vi phạm.

## P4 — đánh giá và cải thiện sau bản demo phần mềm

Quay clip sa bàn ở góc camera dự định; nếu xe mô hình không được YOLO nhận ra, thử MOG2 trên camera cố định hoặc thu dữ liệu để huấn luyện detector phù hợp. Với `vd3`, khóa một đoạn điều chỉnh và **hai đoạn kiểm tra cuối**; trên các đoạn kiểm tra gán nhãn box/ID thật của ít nhất **20 xe máy và 10 ô tô** nhìn qua nhiều frame. So ba pipeline trên cùng CPU theo tỷ lệ frame có box đúng, độ liên tục ID, lần đổi/mất ID, box sai và FPS; không dùng đoạn kiểm tra cuối để chỉnh tham số. Thử riêng clip sa bàn, rồi chấm precision/recall các **sự kiện** trên clip có ca đúng/sai. Nếu chưa đạt, giữ nhãn thử nghiệm và báo ca thất bại; Web/rule vẫn chạy được bằng hợp đồng dữ liệu đã chốt.
