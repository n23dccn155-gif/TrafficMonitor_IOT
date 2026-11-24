 

# Đặc tả điều khiển đèn và cấu hình làn trên Web

> Đề xuất ngày 09/11/2026 theo ý tưởng của nhóm. Đây là thiết kế cho **sa bàn học tập**; các nút Web, Rule Engine và phần Arduino chưa được lập trình. Bắt đầu bằng MP4, sau đó dùng DroidCam live và đèn vật lý.

## 1. Hai tuyến đường, bốn hướng đi vào

Đặt **đường A** (ví dụ trục dọc) và **đường B** (trục ngang). Mỗi đường có hai phía đi vào giao lộ:

| Hướng vào         | Hướng xe hợp lệ khi đi thẳng | Nhóm đèn |
| -------------------- | ---------------------------------- | ----------- |
| A1: từ phía trên  | Đi xuống                         | A           |
| A2: từ phía dưới | Đi lên                           | A           |
| B1: từ phía trái  | Đi sang phải                     | B           |
| B2: từ phía phải  | Đi sang trái                     | B           |

Đây là giả định demo **hai nhóm tín hiệu đối diện cùng pha, chỉ kiểm tra xe đi thẳng**. Nếu có rẽ trái/phải, làn riêng hoặc đường một chiều, phải bổ sung `allowed_path` và đèn áp dụng cho chuyển động đó trước khi gọi là sai chiều/lấn làn. Giữa ngã tư là vùng giao cắt; không áp quy tắc cấm cắt ranh giới làn của đoạn đường thẳng vào toàn bộ vùng này.

Với **mỗi làn**, Web cho vẽ `lane_polygon`, mũi tên `allowed_direction`, các `forbidden_boundary` thật sự cấm cắt, `stop_line` của hướng vào và `signal_group` A/B. ROI/mask xác định nơi theo dõi; **ROI một mình không quyết định vi phạm**. Đường nào có thêm làn thì cấu hình thêm làn, không cần đổi số nhóm đèn. Tọa độ lưu theo ảnh tham chiếu hoặc tỉ lệ ảnh; lưu `scene_config_version` và không ghi đè cấu hình đã dùng cho lượt chạy cũ.

## 2. Web chọn pha giao lộ

Giao diện có nút **“Cho đường A đi”**, **“Cho đường B đi”**, **“Tạm dừng: cả hai đỏ”**. Web hiển thị đèn của cả hai đường cùng lúc; không có hai công tắc xanh/đỏ độc lập có thể tạo A và B cùng xanh.

| Pha          | Đường A | Đường B |
| ------------ | ---------- | ---------- |
| `A_GREEN`  | Xanh       | Đỏ       |
| `A_YELLOW` | Vàng      | Đỏ       |
| `ALL_RED`  | Đỏ       | Đỏ       |
| `B_GREEN`  | Đỏ       | Xanh       |
| `B_YELLOW` | Đỏ       | Vàng      |
| `ALL_YELLOW` | Vàng   | Vàng      |

Pha `ALL_YELLOW` (cả hai đường cùng vàng) **chỉ dùng ở chế độ Thủ công**: bấm vàng ở đèn Đường A rồi bấm vàng ở đèn Đường B (bấm lại một bên để trở về vàng một chiều). Chế độ **Tự động theo giây** không dùng pha này và chu kỳ vẫn `A xanh → A vàng → B xanh → B vàng`. Khi cả hai cùng vàng, xe đường nào cắt vạch dừng cũng **không** bị ghi vi phạm đèn đỏ, vì chiều của xe đang ở vàng.

Khi chuyển từ A xanh sang B xanh, bộ điều khiển đi qua `A_YELLOW → ALL_RED → B_GREEN`; chiều ngược lại tương tự. Thời lượng vàng và cả hai đỏ là **tham số demo**, chưa lấy số giây của đường thật. Không cho hai nhóm xung đột cùng xanh. Nếu Uno còn nguồn nhưng mất lệnh/khởi động lại, firmware đưa cả hai nhóm về đỏ; Web vẫn đánh dấu `UNKNOWN` cho đến khi có ACK mới. Nếu mất cả nguồn USB, không thể giả định LED còn sáng. Ý tưởng khoảng chuyển pha được mô tả trong [FHWA Traffic Signal Timing Manual](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm); tài liệu này chỉ để tham khảo cấu trúc bộ điều khiển, không dùng làm quy định xử lý giao thông Việt Nam.

## 3. Hai chế độ thời gian khác nhau

### Video ghi sẵn — làm trước

Mở MP4 trong Web, tạm dừng hoặc tua đến một frame, chọn pha A/B đang có hiệu lực từ thời điểm đó. Web lưu `SignalChange {run_id, video_timestamp_ms, phase, source: simulation|manual_annotation, seq}`. Khi bấm nút trên trang phát lại, mốc được lấy theo **thời gian video**, không theo giờ máy lúc người dùng bấm. Với `simulation`, nút “Cho đường B đi” tạo chuỗi vàng → cả hai đỏ → B xanh theo thời lượng demo đã cấu hình. Với `manual_annotation` của clip **có đèn thực sự xuất hiện**, người gán nhãn đánh dấu từng pha quan sát được, không tự chèn pha không thấy trong clip. Lưu/sửa timeline rồi chạy lại **Rule Engine từ `tracks.jsonl`**, không cần chạy lại YOLO. Nếu video không quay đèn thật, hiển thị nhãn **“pha mô phỏng”**; đây chỉ là phép thử thuật toán.

### DroidCam và Arduino live — làm sau

Web ghi `SignalCommand {command_id, requested_phase, requested_at}`. Một tiến trình điều khiển riêng nhận lệnh, chuyển pha, gửi lệnh qua USB Serial; Arduino cập nhật chân LED rồi trả `ACK {command_id, seq, phase, t_ms}`. Laptop lưu thời gian nhận ACK theo **cùng đồng hồ đơn điệu** với thời gian nhận frame từ DroidCam. Chỉ trạng thái đã được ACK mới là `effective_phase` dùng cho rule; quá hạn ACK, rút USB hoặc mất liên kết thì `signal_status=UNKNOWN` và không kết luận vượt đèn đỏ. ACK chứng minh chương trình đã ra lệnh cập nhật chân, không tự chứng minh bóng LED ngoài đời thực sáng; có thể đối chiếu thêm ảnh camera khi demo.

Với live, mốc frame phải lấy khi **nhận frame**, không lấy lúc YOLO xử lý xong; bộ đọc ưu tiên frame mới nhất, báo tuổi frame và số frame bỏ. Khi mất hình lâu hoặc nối lại, bắt đầu `segment_id` mới và reset ID. Ca xe cắt vạch sát lúc đổi pha trong khoảng sai số timestamp trả `INSUFFICIENT_EVIDENCE`.

## 4. Quy tắc dùng cấu hình này

- **Ngược chiều:** xét nhiều điểm tiếp xúc mặt đường của một ID trong làn A1/A2/B1/B2. Nếu quỹ đạo đi đủ xa, đủ lâu, ngược mũi tên `allowed_direction` và track ổn định, tạo sự kiện nghi vấn. Xe đứng hoặc chỉ có vị trí Kalman dự đoán không đủ để báo.
- **Lấn/sai làn:** xét việc xe vượt `forbidden_boundary` hoặc đi vào làn không được phép cho hướng đã cấu hình. Có vùng đệm và nhiều frame để tránh báo do box rung. Việc đổi làn hợp lệ hoặc di chuyển ở giữa ngã tư theo đường rẽ được cho phép không bị gắn nhãn sai.
- **Vượt đèn đỏ:** xác định thời điểm xe đi **qua stop_line của hướng vào tương ứng**, tra pha của `signal_group` A/B tại mốc ấy. Xe qua lúc xanh, xe đã qua trước khi đỏ, mốc không rõ hoặc tín hiệu `UNKNOWN` không bị báo vượt đỏ. Vàng có nhãn riêng, chưa tự coi là đỏ.

Một xe có thể tạo nhiều loại sự kiện nghi vấn nếu thật sự thỏa nhiều rule; Web phải ghi lý do từng rule và cho người xem duyệt. Các phép thử dùng cả ca đúng và sai, ghi `run_id`, `scene_config_version`, `rule_version`, `signal_source` cùng ảnh/clip.

## 5. Thứ tự hiện thực và cổng kiểm chứng

1. **Video + hình học:** chạy tracker trên MP4 sa bàn, Web hiển thị một frame và cho vẽ/lưu bốn hướng vào, làn, mũi tên, vạch dừng, ranh giới cấm cắt. Tải lại trang phải hiện đúng cấu hình.
2. **Pha trong replay:** Web cho đặt/sửa timeline A/B theo `video_timestamp_ms`; kiểm tra không thể tạo A/B xanh cùng lúc. Đổi timeline chỉ chạy lại rule, giữ nguyên `tracks.jsonl`.
3. **Ba rule offline:** kiểm tra ca đi đúng/ngược, qua/không qua ranh giới, qua vạch xanh/đỏ/vàng và ca sát lúc đổi pha. Xuất sự kiện và ảnh/clip để duyệt.
4. **Web quan sát:** phát video có box/ID, timeline pha và mốc sự kiện; bấm sự kiện tua đúng thời điểm, thấy nhãn `simulation` khi chưa có Arduino.
5. **Live + phần cứng:** Web gửi lệnh, Arduino ACK, đèn vật lý đổi đúng pha, DroidCam nhận hình và hệ thống ghi cùng clock; thử mất USB/Wi-Fi và trạng thái `UNKNOWN`.
