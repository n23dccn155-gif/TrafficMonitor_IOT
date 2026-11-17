# Kế hoạch tiếp theo: kiểm thử bằng video, rồi làm màn hình giám sát Web

> Đề xuất ngày 09/11/2026; cập nhật mục tiêu hoàn thiện bản demo phần mềm ngày 13/11/2026. Đây là kế hoạch; Web, ba bộ quy tắc và kết nối Arduino chưa được triển khai. Phần mềm hiện tại chỉ phát hiện/theo dõi và xuất box/ID. **Dùng tracker hiện có để lập trình đủ chức năng trước**, gán nhãn/chọn model tốt hơn sau; xem [kế hoạch Web W0–W7](WEB_MVP_PLAN.md) và [prompt chia subagent](SUBAGENT_IMPLEMENTATION_PROMPT.md) cho thứ tự hiện hành.

## 1. Quyết định kỹ thuật

**Stack đề xuất cho đồ án:** Python 3.12 hiện dùng trong repo; **Django 5.2 LTS** cho Web và dữ liệu; **Django templates + Bootstrap 5.3 + JavaScript/Canvas** cho màn hình giám sát; **SQLite** cho bản demo một laptop; worker Python/OpenCV/Ultralytics hiện có để xử lý video. Web phát MP4 H.264 gốc và vẽ box/ID bằng Canvas; FFmpeg chỉ cần khi video đầu vào có codec trình duyệt không mở được hoặc khi xuất clip chứng cứ. Django có auth/admin và hỗ trợ Python 3.12 trong [release notes 5.2](https://docs.djangoproject.com/en/5.2/releases/5.2/). Bootstrap dùng giao diện responsive, có thể lưu CSS/JS cục bộ để demo không phụ thuộc Internet.

Web là một phần sản phẩm nhóm đã chọn, không phụ thuộc việc giảng viên có bắt buộc Django hay không. **Django không chạy YOLO trong một HTTP request**: tiến trình vision đọc video, ghi track/sự kiện/ảnh/clip; Django quản lý cấu hình, danh sách lần chạy, trình phát và thao tác duyệt. Đặt Web và worker cùng repo nhưng tách tiến trình, để tải trang không chờ CPU suy luận.

```text
MP4 nguồn ──► tracking worker ──► tracks.jsonl + summary.json ─────┐
Web Canvas ──► SceneConfig: làn / hướng / vạch ────────────────────┤
Web replay ──► timeline pha A/B theo thời gian video ──────────────┤
                                                                   ▼
                                                       Rule Engine → events.jsonl + ảnh/clip
                                                                   ▼
                                                       SQLite → Django dashboard / duyệt

DroidCam preview/chụp frame ──► Web (W7); Arduino ACK ──► tín hiệu live (W7, sau preview)
```

Không cần React, Django REST Framework, Channels, Redis hoặc broker MQTT cho phiên bản Web phát lại đầu tiên. Chúng chỉ là ứng viên sau khi đo nhu cầu nhiều người dùng, độ trễ hoặc yêu cầu môn học. Django Admin dành cho quản trị dữ liệu nội bộ; màn hình giám sát cần trang riêng, không dùng Admin làm giao diện trình diễn.

## 2. Video để thử bản phần mềm và đánh giá chất lượng sau

| Bộ video | Vai trò | Giới hạn |
| --- | --- | --- |
| `vd3.mp4` (82,2 s; 30 FPS; 2.466 frame) | So sánh detector/tracker, kiểm tra ROI và các ca xe bị che/đổi ID. | Không suy ra có vi phạm thật hoặc pha đèn đúng hướng nếu chưa gán nhãn. Giao lộ rất đông, vạch/làn không đủ rõ ở mọi hướng. |
| Clip sa bàn 1× từ điện thoại ở góc cố định | Bộ đánh giá/cải thiện sau khi phần mềm chạy đủ ba rule; có kịch bản đúng/sai chiều, lấn/không lấn, qua vạch khi đèn xanh/đỏ. | Nếu xe mô hình không được YOLO nhận diện thì phải thử phương pháp camera cố định khác hoặc bổ sung dữ liệu; báo cáo tách với video giao thông thật. |
| Clip sa bàn khác góc **không đổi**, chưa dùng để chỉnh ngưỡng | Bộ kiểm tra cuối. | Ghi rõ số ca và giới hạn; không dùng để sửa ngưỡng rồi chấm lại trên chính clip ấy. |

Trong lúc lập trình, dùng `vd3` để kiểm tra Web/tracking và dùng quỹ đạo/pha **tự xác định đáp án** để kiểm tra logic rule, nên chưa cần sa bàn thật. Khi đánh giá sau bản demo, quay ngắn từng kịch bản để dễ biết thời điểm và đáp án: ít nhất một ca đúng và một ca sai cho mỗi rule; trước khi báo cáo, tăng số ca và giữ riêng đoạn kiểm tra. Cố định camera, ánh sáng, kích thước xe trong ảnh và vùng sa bàn. Nếu đẩy xe bằng tay, cố gắng giữ tay ngoài ROI hoặc ghi ca bị che để không đánh giá nhầm tay là xe. Lưu bảng nhãn đơn giản: `video`, `start_ms`, `end_ms`, `track/xe thật`, `loại ca`, `kết quả mong đợi`, `ghi chú`.

**Kiểm thử đèn đỏ trước khi có Arduino:** tại trang phát lại video, người dùng chọn mốc thời gian rồi đặt pha `A_GREEN`, `A_YELLOW`, `ALL_RED`, `B_GREEN` hoặc `B_YELLOW`. Web lưu timeline theo thời gian *của video* và cho xuất `signal_timeline.json`. Đây là tín hiệu **gán nhãn hoặc mô phỏng để thử phần mềm**, phải được hiển thị là `simulation` trong Web. Khi có Arduino, thay bằng log đổi pha thật qua USB Serial nhưng giữ nguyên giao diện `SignalProvider`. Không dùng một clip giao thông cũ không có log đèn để công bố độ chính xác rule đèn đỏ.

## 3. Các bước triển khai thuật toán theo video

### A. Chuẩn hóa output đang có

Ba pipeline đang ghi `tracks.jsonl` theo từng frame với `frame_index`, `video_timestamp_ms`, `processing_size`, danh sách `tracks` gồm ID, box, điểm mặt đường và quỹ đạo. Chuẩn hóa thêm `run_id`, `segment_id`, kích thước ảnh gốc, loại nguồn, `observation_kind` và phiên bản model. Quy tắc chỉ dùng vị trí **đo từ ảnh** đủ tin cậy; vị trí Kalman dự đoán chỉ phục vụ hiển thị/giữ track. Khi đọc MP4, kiểm tra FPS/timestamp; các quy tắc dùng thời gian video, không dùng thời gian CPU xử lý xong.

### B. Cấu hình cảnh trên một frame tĩnh

Lưu `SceneConfig` dạng JSON có phiên bản: **đường A có hai vùng chiều chạy A1/A2, đường B có B1/B2**, mũi tên hướng hợp lệ của từng vùng, đường phân cách hai chiều của từng đường, vùng giữa ngã tư và vạch dừng. Hai chiều của A dùng chung nhóm đèn A; hai chiều của B dùng chung nhóm đèn B. Trang Canvas cho người vận hành **đánh dấu quy ước lên frame ngã tư đã quay**; không vẽ xe/ID/quỹ đạo thủ công. Detector/tracker tự cấp box, loại xe nếu biết và ID theo thời gian. Tọa độ lưu theo tỉ lệ ảnh hoặc kèm kích thước tham chiếu, để ảnh hiển thị ở 640/960/1280 px không làm lệch vạch. Bất cứ khi nào đổi vị trí điện thoại/zoom hoặc bố trí sa bàn, phải tạo phiên bản cảnh mới. Chi tiết nằm trong [đặc tả ngã tư](INTERSECTION_CONTROL_SPEC.md).

### C. Rule Engine độc lập với detector

1. **Ngược chiều:** tính hướng/quãng đường từ nhiều điểm tiếp xúc mặt đường đã quan sát trong ROI; có ngưỡng quãng đường/thời gian, bỏ ca xe đứng, track đứt, đổi ID và chống báo lặp.
2. **Sai/lấn làn:** phát hiện điểm đi từ phía hợp lệ sang phía bị cấm của ranh giới đã cấu hình, có vùng đệm để chống rung box; chỉ gọi là sai làn nếu SceneConfig nói rõ làn nào được phép cho hướng/loại xe đó.
3. **Vượt đèn đỏ:** tìm lúc xe cắt vạch dừng theo hướng đi, tra timeline của **đúng nhóm đèn** tại thời điểm đó. Nếu tín hiệu thiếu, xe qua trước lúc đỏ, hoặc khoảng sai số thời gian chạm mốc đổi pha, trả `INSUFFICIENT_EVIDENCE`.

Mỗi rule chỉ phát **một event cho cùng ID/loại lỗi trong một lượt đi liên tục**, tại mốc vừa xác nhận lỗi. `ViolationEvent` ghi `event_id`, `tracking_run_id`, `rule_run_id`, `segment_id`, `rule_type`, `track_id`, `event_timestamp_ms`, `bbox_xyxy`, `scene_config_version`, `signal_source`, `reason`, ảnh toàn khung có box và ảnh crop đúng xe, `review_status`. Xe vẫn còn thấy ở các frame sau không tạo event lặp; chạy lại/import cùng `RuleRun` không nhân đôi. Trường hợp không đủ bằng chứng lưu ở diagnostics riêng. Viết bộ thử bằng các quỹ đạo/timeline **được tự xác định đáp án**, sau đó đối chiếu trên clip giữ riêng. Chấm precision/recall ở **mức sự kiện**, cùng ID switch, box sai và FPS của pipeline; không dùng tổng số box làm độ chính xác.

### D. Đầu ra dùng cho Web

Một lần chạy có `run_id`, đường dẫn nguồn, `tracks.jsonl`, `events.jsonl`, `summary.json` và ảnh/clip sự kiện. Metadata sự kiện/lần chạy vào SQLite; file lớn giữ ở thư mục media. Web ưu tiên phát **MP4 H.264 nguồn** và vẽ box/ID từ track bằng Canvas, nên không cần lưu một video annotated nữa cho mỗi lần đổi cấu hình. `vd3.mp4` hiện báo H.264. Output `annotated.mp4` hiện dùng OpenCV `mp4v`, codec này không được các trình duyệt lớn hỗ trợ đáng tin cậy; chỉ chuyển mã sang H.264 khi phải phát một video đầu vào không tương thích hoặc xuất clip bằng chứng. [MDN: video codecs](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Video_codecs).

## 4. Web mô phỏng màn hình trung tâm giám sát

```text
┌──────────────────────────── Video / replay + box, ID, vạch ───────────────────────────┬── Sự kiện mới ──┐
│                                                                                       │ thời gian, loại, │
│                                                                                       │ ảnh nhỏ, mức tin │
├──────────────────────── Timeline: pha đèn, mốc sự kiện, tua đến thời điểm ─────────────┴────────────────┤
│ Danh sách lần chạy/camera • lọc loại sự kiện • trạng thái duyệt • FPS/độ trễ/nguồn tín hiệu               │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Dashboard:** nhãn `VIDEO GHI SẴN` hoặc `TRỰC TIẾP` hiển thị rõ; video lớn, box/ID/quỹ đạo, trạng thái camera và nguồn đèn, bảng sự kiện gần nhất. Có bảng điều khiển **“Cho đường A đi” / “Cho đường B đi” / “Cả hai đỏ”**; Web tạo pha vàng và chuyển tiếp trước khi đổi nhóm xanh, không cho hai nhóm cùng xanh. Ở replay, nút đặt mốc trên timeline video; ở live, nút gửi lệnh cho Arduino và chờ ACK. Không trình bày video phát lại như hình đang live.
- **Chi tiết sự kiện:** nhảy đến thời điểm trên video, xem ảnh/clip vài giây trước và sau, ID, vạch/làn đã kích hoạt, pha đèn và lý do rule. Người xem đánh dấu `pending` / `confirmed` / `dismissed` kèm ghi chú; kết quả hệ thống vẫn là nghi vấn cho đến khi được duyệt.
- **Cấu hình cảnh:** đóng băng một frame và vẽ ROI, vạch, làn, hướng trên Canvas; xem trước trên đúng kích thước video, lưu phiên bản và khóa cấu hình đã dùng cho mỗi run.
- **Lịch sử và thống kê:** lọc theo clip, loại, thời gian, trạng thái; xem FPS và số lần ID đứt. Không dùng số sự kiện xuất ra làm bằng chứng độ chính xác.
- **Tài khoản:** dùng Django Auth cho một tài khoản vận hành/duyệt trên laptop demo. Giao diện là **mô phỏng phục vụ học tập**, không dùng nhận diện/biểu trưng của cơ quan nhà nước.

Các bảng Django tối thiểu: `VideoAsset`, `Camera`, `SceneConfig`, `ProcessingRun`, `SignalCommand`, `SignalChange`, `ViolationEvent`, `ReviewAction`. `SignalChange` lưu pha A/B, nguồn `simulation`/`manual_annotation`/`arduino_ack`, mốc video hoặc mốc nhận trên laptop và số thứ tự. `ProcessingRun` lưu model/rule/config version, FPS, thời gian và vị trí file. `ViolationEvent` trỏ tới ảnh/clip và pha đèn đã xét. Tạo khóa duy nhất cho `event_id` để import lại không nhân đôi.

## 5. Thứ tự giao việc và cổng nghiệm thu

| Mốc | Sản phẩm chạy được | Điều kiện qua mốc |
| --- | --- | --- |
| 0 — nhận diện + Web box/ID | `vd3` cho tracking và Web phát lại với box/ID từ pipeline hiện có. | Chọn video, chạy tracker, xem box/ID/quỹ đạo trên Web; biết frame bỏ sót, ID đứt và FPS. Chưa chạy rule vi phạm. |
| 1 — Web cấu hình cảnh/pha | Editor trên frame tĩnh cho hai vùng chiều của mỗi đường và timeline pha A/B theo thời gian video. | Tải lại đúng vùng/mũi tên/ranh giới/vạch; không tạo hai nhóm cùng xanh; đổi timeline không chạy lại YOLO. |
| 2 — hai rule hình học offline | Ngược chiều và sai/lấn làn đọc `tracks.jsonl` + SceneConfig, xuất `events.jsonl` + ảnh. | Chạy lại cùng clip cho cùng sự kiện; ca âm tính và ca ID đứt không báo sai hàng loạt. |
| 3 — đèn đỏ offline | `SignalProvider` từ timeline Web, rule qua vạch. | Ca xanh/đỏ/chuyển pha được đối chiếu với bảng nhãn; ca thiếu dữ liệu trả chưa đủ bằng chứng. |
| 4 — Web giám sát | Django dashboard, video H.264, timeline và trang duyệt sự kiện. | Mở trên trình duyệt laptop, bấm sự kiện tua đúng lúc, xem ảnh/clip, đổi trạng thái duyệt và tải lại vẫn còn. |
| 5 — phần cứng và live | Arduino Serial/ACK cho timeline thật; DroidCam frame mới nhất; cùng Rule Engine và Web. | Demo có đèn vật lý và log đúng pha; xem FPS, tuổi frame, frame bỏ, reset ID khi mất hình; thử rút USB/mất Wi-Fi. |

**Việc cần làm ngay:** dựng Web phát `vd3` với box/ID, cho chạy lại ba pipeline, rồi lập trình ba rule trên quỹ đạo/pha kiểm thử. Sau khi bản phần mềm chạy xuyên suốt, quay clip sa bàn 20–30 giây ở đúng góc dự định để biết detector hiện có có nhận xe mô hình hay phải cải thiện.
