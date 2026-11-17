# Định hướng đồ án TrafficMonitor IoT

> Cập nhật 09/11/2026 theo quyết định của nhóm: **điện thoại chạy DroidCam** làm camera, **Arduino Uno R3** điều khiển đèn của sa bàn. Quyết định bổ sung 13/11/2026: **hoàn thiện phần mềm bằng tracker hiện có và MP4 trước; cải thiện/đánh giá model sau**. GoPro và ESP32 không còn là phần cứng trong phương án demo hiện tại. Danh sách linh kiện là dự tính, chưa xác nhận đã mua hoặc đã đấu mạch.

Nhóm đã chọn làm **Web mô phỏng màn hình giám sát**, nhưng sẽ kiểm thử thuật toán trên MP4 trước. Xem [kế hoạch video trước và Web](VIDEO_FIRST_WEB_PLAN.md) để biết stack, dữ liệu và điều kiện nghiệm thu từng mốc.

Phần việc Web có thể tự làm ngay bằng `vd3` và output đã có được chia thành các mốc W0–W7 trong [kế hoạch Web MVP](WEB_MVP_PLAN.md). W1 hiện box/ID để kiểm tra tracking; W7 mở DroidCam rồi mới nối Arduino.

Web còn là nơi **vẽ hai vùng chiều xe chạy trên mỗi đường A/B, mũi tên, đường phân cách và vạch dừng**, đồng thời chọn pha đèn cho A/B. A1/A2 thuộc hai chiều của A và dùng chung nhóm đèn A; B1/B2 tương tự. Xem [đặc tả cấu hình ngã tư và điều khiển đèn](INTERSECTION_CONTROL_SPEC.md).

## 1. Mục tiêu và trạng thái hiện tại

Camera cố định quan sát một sa bàn giao lộ. Laptop nhận video trực tiếp từ DroidCam, theo dõi phương tiện, so quỹ đạo với làn/hướng/vạch dừng, rồi lưu **sự kiện nghi vấn** gồm thời gian, ID, ảnh/clip và lý do kích hoạt. Ba tình huống mục tiêu là **đi ngược chiều**, **đi sai/lấn làn theo vạch cấm**, và **qua vạch dừng khi đèn áp dụng đang đỏ**. Kết quả cần người xem kiểm tra, không tự động kết luận vi phạm pháp luật.

`menu.py` **đã có** nguồn MP4/URL DroidCam, ba lựa chọn tracking, cửa sổ box/ID và JSONL/summary. **Chưa có** bộ quy tắc cho ba tình huống, cấu hình ROI/vạch/làn, Arduino Serial, đồng bộ đèn với video, hoặc xử lý live đủ tin cậy khi chậm/mất mạng. Video giao thông thật `vd1`–`vd3` dùng để đánh giá tracking; kết quả trên chúng phải báo cáo riêng với sa bàn. Không dùng chúng để xác nhận vượt đèn đỏ bằng trạng thái Arduino vì không có log đèn đồng bộ.

## 2. Kiến trúc demo đã chọn

```text
MP4 trước / DroidCam live sau → detector/tracker → ID + box + quỹ đạo ─────┐
                                                                           ├→ Rule Engine → sự kiện + bằng chứng
Django Web → vẽ làn/hướng/vạch → SceneConfig ───────────────────────────────┤                    ↓
Django Web → chọn pha A/B → timeline mô phỏng (MP4) ────────────────────────┘       Web phát lại/duyệt
                            └→ khi live: lệnh → Arduino Uno → ACK → timeline thật
```

Laptop xử lý ảnh; **Django Web điều khiển pha logic và cấu hình hình học**. Với video ghi sẵn, lần bấm pha gắn vào thời gian của clip và ghi rõ là mô phỏng/gán nhãn. Với live, Web gửi lệnh, Arduino Uno cập nhật chân LED rồi trả ACK qua cùng cáp USB cấp điện; chỉ pha đã ACK mới được xét trong rule. Không cần mua ESP32 để hoàn thành đường dữ liệu này. MQTT chỉ thêm khi cần theo rubric hoặc mở rộng truyền sự kiện; xem [đối chiếu môn học](COURSE_ALIGNMENT.md).

## 3. M0 — hoàn thiện luồng phần mềm bằng video trước

1. Dùng `vd3.mp4` để xem tracking trên giao lộ thật và các lỗi box/ID. Clip này không có log đèn Arduino; không lấy nó làm bằng chứng độ chính xác của rule vượt đỏ.
2. Dùng `vd3` và quỹ đạo/pha kiểm thử đã xác định đáp án để dựng Web, ba rule và trang duyệt trước. Khi có sa bàn, cố định điện thoại trên cao, khóa vị trí/góc nhìn và quay **MP4 1×** với các ca đúng/sai để đánh giá độ chính xác thật. Khi chưa có đèn Arduino, timeline pha A/B đặt trên Web phải ghi rõ nguồn là `simulation`.
3. Chạy `menu.py` → nguồn **1** → chọn `vd3` hoặc dán đường dẫn MP4 sa bàn → thuật toán **3 (YOLOv8n + ByteTrack)** → độ rộng **640 px** trước, sau đó thử 960 px nếu xe mô hình quá nhỏ. So sánh với thuật toán 2 MOG2 + Kalman trên cùng frame.
4. Sau khi Web phát lại MP4 và các rule offline chạy được, mở DroidCam live: điện thoại và laptop cùng Wi-Fi; thử URL `http://<IP>:<PORT>/video` trong trình duyệt rồi dán vào nguồn **2** của menu hoặc ô URL trên Web khi W7 hoàn tất. [DroidCam hướng dẫn endpoint `/video`](https://droidcam.app/help/). Nhánh tracking/rule live cần bộ đọc frame mới nhất, mốc nhận frame, tuổi frame, số frame bỏ và reset ID sau mất hình; hiện chưa có đầy đủ.

**Cổng đánh giá sau khi phần mềm chạy được:** clip sa bàn chạy được ít nhất một pipeline, box/ID bám phương tiện đủ để chấm rule. Model YOLO huấn luyện trên xe thật có thể không nhận xe mô hình; phải kiểm tra bằng clip sa bàn 20–30 giây trước khi **công bố độ đúng hoặc chọn detector cuối**. MOG2 có thể bám vật chuyển động nhưng không phân loại xe và có thể bám tay người đẩy xe.

## 4. Mạch đèn sa bàn dự tính

Danh sách nhóm gửi ngày 09/11/2026 chỉ gồm **phần mạch điện**, tổng dự tính **248.400 đ**: Arduino Uno R3 SMD CH340, cáp USB A–B, 2 PCB 5×7 cm, mỗi màu đỏ/vàng/xanh 1 gói 10 LED 5 mm, gói điện trở 330 Ω và 220 Ω, hàng rào chân, dây cắm, dây lõi đồng, ống co nhiệt và keo. Số lượng 4 LED mỗi màu phù hợp **4 cụm đèn**, mỗi cụm 1 đỏ + 1 vàng + 1 xanh. Giá và link shop trong ảnh chưa được kiểm chứng từ bảng gốc vì ảnh không chứa URL đích.

Để dùng 6 chân D2–D7, ghép hai cụm đèn đối diện cùng pha: Bắc–Nam (BN) và Đông–Tây (ĐT). Đây là **hai nhóm tín hiệu**, không phải bốn đèn điều khiển độc lập.

| Chân Uno | Nhóm/màu | Số nhánh LED đang điều khiển |
| --- | --- | ---: |
| D2, D3, D4 | BN đỏ, vàng, xanh | 2 nhánh riêng cho từng chân |
| D5, D6, D7 | ĐT đỏ, vàng, xanh | 2 nhánh riêng cho từng chân |

Mỗi LED phải có **một điện trở nối tiếp riêng**, rồi các nhánh của cùng màu/nhóm mới nối về cùng chân. Tổng cần 12 điện trở, không dùng một điện trở chung cho hai LED mắc song song. Theo [pinout Arduino Uno Rev3 SMD](https://docs.arduino.cc/resources/pinouts/A000073-full-pinout.pdf), giới hạn dòng ghi cho mỗi chân I/O là 20 mA. Với hai nhánh trên cùng một chân, gói **220 Ω cho LED xanh** có thể làm dòng vượt mức này tùy điện áp thuận của LED. Trước khi mua/hàn, nên đổi sang **12 điện trở 470 Ω, 1/4 W** (hoặc đo LED cụ thể rồi tính lại); ở mức 5 V với LED có điện áp thuận từ khoảng 2 V trở lên, hai nhánh 470 Ω cùng chân dưới khoảng 13 mA. Gói 330 Ω/220 Ω trong ảnh vì vậy là **dự tính cần rà lại**, chưa coi là sơ đồ đấu cuối.

Web cho chọn **đường A xanh**, **đường B xanh** hoặc **cả hai đỏ**, không cho bật hai nhóm xung đột cùng xanh. Bộ điều khiển đi qua vàng và pha hai bên đỏ khi đổi nhóm. Khi live, tiến trình điều khiển gửi lệnh đến Arduino qua USB Serial; Arduino cập nhật chân LED rồi trả một dòng ACK, ví dụ `{"command_id":12,"seq":12,"phase":"A_GREEN","t_ms":15320}`. Laptop lưu thêm thời gian nhận ACK theo đồng hồ đơn điệu của nó; khi Arduino reset, mất Serial hoặc quá hạn ACK, đánh dấu trạng thái đèn `unknown`. ACK là xác nhận chương trình đã cập nhật đầu ra, chưa phải phép đo độc lập bóng LED sáng. Chi tiết nằm trong [đặc tả Web điều khiển đèn](INTERSECTION_CONTROL_SPEC.md).

Danh sách trong ảnh không bao gồm vật liệu đường/làn/vạch, xe mô hình, giá đỡ điện thoại và dụng cụ hàn; chúng cần có sẵn hoặc lập danh sách riêng. Nếu nhóm đã có cáp USB A–B đủ dài, cáp 1,5 m là khoản có thể cân nhắc bỏ. Nên thử mạch bằng breadboard sẵn có trước khi hàn PCB, đặc biệt kiểm tra cực LED và chân chung GND.

## 5. Hợp đồng dữ liệu và thứ tự làm ba tình huống

`TrackObservation` cần có `camera_id`, `segment_id`, `frame_index`, `capture_timestamp`, `track_id`, `bbox_xyxy`, điểm tiếp xúc mặt đường tạm lấy giữa cạnh dưới box, quỹ đạo, loại xe nếu biết, và trạng thái `detection`/`prediction`. `SceneConfig` gắn với vị trí camera và kích thước hình: **hai vùng chiều chạy cho mỗi đường A/B**, mũi tên hợp lệ của từng vùng, ranh giới giữa hai chiều, vùng giữa ngã tư, vạch dừng và nhóm đèn A/B áp dụng. Đổi vị trí điện thoại hoặc zoom buộc vẽ lại cấu hình. `SignalChange` có pha, nguồn `simulation`/`manual_annotation`/`arduino_ack`, số thứ tự và mốc thời gian video hoặc mốc nhận live; cần giữ toàn bộ lịch sử, không chỉ pha mới nhất.

1. **Ngược chiều:** quỹ đạo trong ROI đi ngược hướng đã cấu hình đủ xa/đủ lâu; loại xe dừng, mất ID hoặc chỉ có dự đoán.
2. **Sai/lấn làn:** điểm tiếp xúc cắt ranh giới cấu hình cấm cắt hoặc vào làn không hợp lệ, cần vùng đệm và nhiều frame để tránh box rung. Không gọi mọi lần đổi làn là vi phạm.
3. **Đèn đỏ:** xác định thời điểm xe **qua vạch dừng**, tra lịch sử pha của **đúng nhóm đèn**. Giai đoạn video đầu dùng timeline pha gán nhãn/mô phỏng; sau đó thay bằng log Arduino thật. Xe qua trước khi chuyển đỏ, ca sát lúc đổi pha, mất tín hiệu hoặc ảnh/ID không rõ phải trả `INSUFFICIENT_EVIDENCE`.

Lưu `ViolationEvent` với loại tình huống, track/segment ID, thời gian, phiên bản cấu hình/quy tắc, lý do và ảnh/clip. Giữ cả ca âm tính (đúng chiều, đúng làn, qua khi xanh) để chấm precision/recall mức sự kiện. Video sa bàn và video giao thông thật là hai bộ đánh giá riêng.

## 6. Mốc nghiệm thu

| Mốc | Việc làm | Bằng chứng cần lưu |
| --- | --- | --- |
| M0 | Dùng MP4 `vd3` và tracker hiện có để Web phát video với box/ID, rồi chạy lại pipeline từ Web. | Web mở được clip, hiện box/ID, FPS và ca lỗi; không cần sa bàn để lập trình. |
| M1 | Web vẽ hai vùng chiều của mỗi đường, mũi tên, ranh giới/vạch và đặt timeline pha A/B trên video. | Tải lại giữ cấu hình; không thể có hai nhóm xanh; thay timeline không phải chạy lại YOLO. |
| M2 | Dùng tracker mặc định hiện có và làm hai rule ngược chiều, lấn qua phân cách offline. | Ca đúng/sai trên quỹ đạo kiểm thử, ảnh/clip nghi vấn và ca không đủ dữ liệu. |
| M3 | Rule vượt đỏ với timeline Web; mở rộng Django thành màn hình phát lại/duyệt. | Ca đỏ/xanh/chuyển pha; thiếu tín hiệu không bị kết luận sai; bấm sự kiện tua đúng lúc. |
| M4 | Web gửi lệnh đến Uno và nhận ACK; tích hợp DroidCam live frame mới nhất. | Đèn vật lý và log đúng pha; thử rút USB/mất Wi-Fi, FPS/tuổi frame/frame bỏ. |
| M5 | Demo đủ ba rule với video live và báo cáo; MQTT nếu rubric yêu cầu. | Sự kiện có bằng chứng và trạng thái nguồn; báo cáo độ chính xác/độ trễ/giới hạn. |

**Ưu tiên gần nhất:** thực hiện [prompt chia ba subagent](SUBAGENT_IMPLEMENTATION_PROMPT.md) để có Web video → box/ID → cấu hình cảnh/đèn → ba rule → duyệt sự kiện. Sau bản phần mềm, quay MP4 20–30 giây từ góc sa bàn dự định để đánh giá xe mô hình và chọn detector cuối. Không lấy số ID tạo ra thay cho độ chính xác nhận diện.
