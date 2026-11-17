# Kế hoạch làm Web trước, thử bằng video

> Lập ngày 09/11/2026; cập nhật 14/11/2026 theo luồng **gán đường trên frame, tự nhận xe/ID, mỗi lỗi một event có ảnh chứng cứ**. **Đây là kế hoạch, chưa có mã Django.** Web thử bằng MP4 trước, tiếp đến URL DroidCam; đèn trên Web ban đầu là mô phỏng, còn phần cứng sẽ được nối và nghiệm thu khi có sa bàn. Xem [đặc tả ngã tư](INTERSECTION_CONTROL_SPEC.md) cho quy ước hai đường A/B, mỗi đường hai chiều.

## 1. Web phải làm được gì trong bản đầu?

Người dùng mở Web, bấm **Chọn nguồn** để chọn MP4 trong `data/raw/` hoặc dán URL DroidCam; bên trái xem video/luồng hình lớn, bên phải điều khiển tín hiệu đèn. Nút **Chụp khung hình để cấu hình** đóng băng một frame của **ngã tư thật đang thấy trong video**. Người dùng chỉ **gán tên đường A/B và đánh dấu quy ước tĩnh trên ảnh**: hai vùng chiều xe chạy của mỗi đường, mũi tên chiều hợp lệ, đường phân cách, vùng giữa ngã tư và vạch dừng. Web không vẽ ra ngã tư mới, không yêu cầu người dùng vẽ box/đánh ID xe hoặc vẽ đường đi của từng xe. Detector/tracker tự tìm phương tiện, gán box/nhãn loại nếu biết, cấp ID và cập nhật quỹ đạo. Luôn có nhãn **VIDEO GHI SẴN** hoặc **TRỰC TIẾP** tương ứng với nguồn.

`menu.py` vẫn là công cụ chạy và debug trực tiếp trong IDE. Web gọi các module xử lý video bằng **worker riêng**, không gọi `menu.py` tương tác và không chạy YOLO trong request HTTP. Bản Web đầu có thể hoàn thành phần trình phát, cấu hình cảnh và timeline ngay cả khi đồng đội chưa giao xong ba rule.

### Bố cục màn hình chính

```text
┌──────────────────────── khoảng 75% ────────────────────────┬──── khoảng 25% ────┐
│ [Chọn nguồn: MP4 | URL DroidCam] [Chụp frame] [Chạy phân tích]│ ĐÈN TUYẾN A  ●     │
│ Video/replay hoặc live, phủ box/ID, làn và vạch đã lưu       │ ĐÈN TUYẾN B  ●     │
│                                                             │ Thủ công | Hẹn giờ │
│                                                             │ A đi | B đi | Đỏ hết│
│                                                             │ Giây xanh/vàng/đỏ  │
├─────────────────────────────────────────────────────────────┴───────────────────┤
│ Timeline video/pha đèn/sự kiện; trạng thái nguồn, FPS, job, cảnh đã chọn        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Tỉ lệ 75/25 áp dụng khi màn hình laptop đủ rộng; trên màn hình hẹp, panel đèn xuống dưới để video vẫn đọc được. Khi bấm **Chụp frame**, mở vùng biên tập quy ước đường ngay trên ảnh tĩnh ở khu vực video, có **Lưu / Hủy / Sửa mốc**; trạng thái pha đèn vẫn nhìn thấy ở bên phải. Hệ thống vẫn tự nhận xe khi xử lý video; một bộ đọc frame phía backend dùng chung cho preview và worker live để box/ID, frame chụp và timestamp không lệch nhau.

Một lượt thử MP4 đi theo thứ tự: chọn clip → **xem box/ID và lỗi tracking** → chạy tracker từ Web → chụp frame/vẽ cảnh → kiểm tra ngược chiều và lấn qua phân cách → đặt pha đèn để kiểm tra qua vạch đỏ → duyệt sự kiện. **Dùng YOLOv8n + ByteTrack hiện có làm mặc định để triển khai đủ chức năng**; vẫn cho chọn MOG2 và YOLO11s. Kết quả quy tắc là sự kiện **nghi vấn** và phải hiện nhãn **mô phỏng** khi pha đèn chỉ được đặt trên Web. Việc chọn model tốt nhất bằng bộ video gán nhãn là mốc cải thiện chất lượng sau bản demo. DroidCam live và Arduino được kiểm tra riêng khi sẵn thiết bị.

### Nút chọn nguồn và chụp khung hình

- **MP4:** chọn một clip đã có trong `data/raw/` hoặc tải clip lên máy chủ Web; xác thực đuôi/định dạng và lưu vào `data/raw/`. Trình phát cho tua, dừng và bấm **Chụp frame hiện tại**. Frame chụp ghi mốc `video_timestamp_ms`, kích thước ảnh gốc và định danh clip. Không lấy ảnh bất kỳ không liên quan đến mốc video đang xem.
- **DroidCam:** nhập URL mà điện thoại hiển thị, ví dụ `http://192.168.1.20:4747/video`, bấm **Kiểm tra kết nối** trước khi phát. Trang Web báo đang kết nối, có hình, mất hình, thử nối lại; hiện tuổi frame. Backend đọc nguồn một lần, giữ frame mới nhất cho preview, xử lý và nút **Chụp frame hiện tại**. URL dùng để đọc trên laptop chạy Web, không bắt trình duyệt/điện thoại mở cùng một luồng lần thứ hai. Hướng dẫn URL `/video` có trong [DroidCam Help](https://droidcam.app/help/).
- Mỗi `SceneConfig` gắn với **nguồn, kích thước ảnh và bố cục/góc camera**. Khi đổi vị trí điện thoại, zoom, xoay máy hoặc thay clip khác góc nhìn, Web yêu cầu chụp frame và tạo phiên bản cấu hình mới. Ảnh chụp dùng để vẽ; hình live tiếp tục chạy sau khi đóng biên tập.

### Bảng đèn bên phải: hai chế độ

- **Quy ước ngã tư:** hai đường A và B cắt nhau. **A xanh ⇒ B đỏ; B xanh ⇒ A đỏ**. Hai phía xe đi vào của cùng đường dùng chung tín hiệu đường đó. Khi đổi pha có thể có khoảng **A đỏ, B đỏ**; tuyệt đối không có A và B cùng xanh.
- **Thủ công:** người dùng bấm **Cho A đi**, **Cho B đi** hoặc **Cả hai đỏ**. Đây là ba *lệnh cho toàn giao lộ*, không phải bốn công tắc bật/tắt đỏ/xanh riêng. Khi chuyển A sang B, phần mềm tạo `A_YELLOW → ALL_RED → B_GREEN`, và chiều ngược lại tương tự. Web hiện pha hiện hành của cả A và B.
- **Theo thời gian:** nhập `A_xanh_s`, `B_xanh_s`, `vang_s`, `do_chung_s`; có **Bắt đầu / Tạm dừng / Tiếp tục / Dừng** và đồng hồ đếm ngược. Chu kỳ là `A_GREEN → A_YELLOW → ALL_RED → B_GREEN → B_YELLOW → ALL_RED → ...`. Kiểm tra các thời lượng đều dương và không cho A/B cùng xanh. Mọi chuyển pha được lưu vào timeline, không chỉ đổi màu trên màn hình.
- **Khi phát MP4:** đồng hồ là **thời gian video**. Người dùng đặt pha đầu/điểm bắt đầu tại vị trí phát; tua lùi hoặc tải lại cho kết quả pha giống nhau. Tạm dừng video thì đồng hồ pha tự động cũng dừng. Bấm thủ công tạo/sửa mốc trên timeline ở đúng frame đang xem. Các pha này mang nhãn `simulation`; nếu clip có đèn thật thì dùng chế độ gán nhãn riêng để ghi những pha quan sát được.
- **Khi xem DroidCam live trước Arduino:** đồng hồ theo thời gian thực của máy và panel ghi rõ **ĐÈN MÔ PHỎNG**; nút chưa điều khiển LED vật lý. Sau này controller gửi lệnh Arduino, chờ ACK rồi mới đánh dấu pha có hiệu lực để xét vượt đèn đỏ. Mất hình hoặc mất xác nhận trạng thái đèn được báo rõ, không gắn kết luận cho đoạn thiếu dữ liệu.

## 2. Công nghệ và lý do chọn

| Thành phần | Chọn cho MVP | Việc nó làm |
| --- | --- | --- |
| Backend Web | **Django 5.2 LTS**, Python 3.12 | Trang Web, đăng nhập, lưu cấu hình, lần chạy và sự kiện; [Django 5.2 hỗ trợ Python 3.12](https://docs.djangoproject.com/en/5.2/releases/5.2/). |
| Giao diện | Django templates + Bootstrap 5.3 + JavaScript/Canvas | Bố cục màn hình giám sát, box/ID, vẽ polygon/mũi tên/vạch và timeline. Lưu CSS/JS cần dùng vào `static/` để demo không cần Internet. |
| Cơ sở dữ liệu | SQLite trên laptop demo | Lưu metadata và phiên bản cấu hình. Video/ảnh và `tracks.jsonl` vẫn là file, không nhét file lớn vào DB. |
| Xử lý video | Các script `src/traffic_monitor/` hiện có, chạy ở tiến trình worker | Tạo `tracks.jsonl` và `summary.json`. Dùng YOLOv8n lựa chọn 3 làm **baseline giao diện đầu tiên**; chọn pipeline chấm vi phạm sau khi so ba nhánh trên clip góc sa bàn mục tiêu. |
| Trình phát | Video H.264 gốc + lớp Canvas | Vẽ box/ID/ROI lên video theo thời gian, có thể bật/tắt từng lớp. `vd3.mp4` trên máy hiện báo codec `h264`; `annotated.mp4` hiện dùng `mp4v`, codec này không được các trình duyệt lớn hỗ trợ tốt theo [MDN](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Video_codecs). |

Nếu MP4 khác dùng codec trình duyệt không phát được, tạo **bản dẫn xuất H.264** một lần; giữ video gốc. Chưa cần FFmpeg để mở `vd3` nếu trình duyệt trên máy demo phát được nó. Endpoint phát video cần hỗ trợ [HTTP byte-range](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests) để tua đến mốc giữa/cuối của file dài. Chưa cần React, Redis, Channels hoặc Django REST Framework cho một máy và một người dùng thử; có thể thêm khi yêu cầu thực tế xuất hiện.

## 3. Cấu trúc mã sẽ tạo

```text
TrafficMonitor_IoT/
├─ manage.py                     # lệnh Django, sẽ tạo ở mốc W0
├─ requirements-web.txt           # phụ thuộc Web riêng
├─ web/traffic_web/               # settings, urls
├─ web/monitor/                   # models, views, forms, services, management commands
├─ web/templates/                 # dashboard, video, scene editor, signal timeline, events
├─ web/static/                    # CSS, JS Canvas, Bootstrap dùng cục bộ
├─ data/raw/                      # MP4 gốc, không commit
└─ outputs/runs/                  # track/summary/event/ảnh; không commit
```

Không thay đổi thuật toán tracking để dựng giao diện đầu tiên. Khi thêm nút **Chạy phân tích**, tạo một `TrackingRun` trạng thái `QUEUED`, tiến trình `run_worker` ở terminal thứ hai gọi script CLI với `--source`, `--output`/`--output-dir`, `--width` **không có `--show`**. Worker ghi `RUNNING`/`DONE`/`FAILED`, đường dẫn output và thông báo lỗi. Chạy **một job video tại một thời điểm** trên laptop CPU. Không khởi động worker trong `AppConfig.ready()` của Django vì dev server có cơ chế tải lại mã.

## 4. Hợp đồng trao đổi với phần thuật toán

### Dữ liệu Web đọc từ tracking

Các pipeline hiện ghi một dòng `tracks.jsonl` cho mỗi frame đã xử lý: `frame_index`, `video_timestamp_ms`, `processing_size` và `tracks` với `track_id`, box, loại xe nếu biết, `observation_kind`. `summary.json` ghi số frame đã xử lý và thời gian xử lý, nhưng các pipeline dùng **tên trường thống kê khác nhau**; riêng YOLO11s chia ô có thể bỏ frame và `frame_index` trong JSONL là thứ tự frame được xử lý, không phải số frame gốc. Bộ import chuẩn hóa các trường này, lấy `video_timestamp_ms` làm mốc ghép với video và tự đọc metadata video để biết FPS/kích thước/số frame nguồn khi summary thiếu. Web lưu cả **độ phủ đã xử lý**: một lượt người dùng đóng giữa chừng không có overlay/sự kiện cho phần video còn lại.

File JSONL hiện có thể hơn 10 MB vì lặp cả quỹ đạo trong nhiều frame. Khi import, giữ file gốc để truy vết, tạo bảng `TrackFrame` **mỗi frame một dòng** với danh sách gọn `{id, box, type, observation_kind}`; index theo `(tracking_run, video_timestamp_ms)`. Browser chỉ gọi API lấy một cửa sổ thời gian ngắn quanh vị trí phát, không tải toàn bộ JSONL. Canvas đặt khớp vùng ảnh thực trong `<video>` và nhân tọa độ theo `processing_size`; test cả khi phóng to/thu nhỏ trình duyệt. Có thể dùng [`requestVideoFrameCallback` và `mediaTime`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback) trên Chrome/Edge hiện đại, với cách cập nhật theo `currentTime` làm dự phòng. Nếu pipeline bỏ frame, chỉ hiện box ở mốc có quan sát tương ứng trong sai số cho phép; vùng thiếu dữ liệu có nhãn riêng, không giữ box cũ như thể đang quan sát liên tục.

**Lưu ý khi clone repo:** `summary.json` cũ có thể chứa đường dẫn tuyệt đối của máy tác giả. Web chỉ phục vụ file nằm trong `data/raw/` và `outputs/runs/` của bản clone; lúc import sẽ ghép lại video tương ứng bằng tên/kích thước/thời lượng hoặc hỏi người dùng chọn, không dùng thẳng đường dẫn cũ hay cho trình duyệt mở path tùy ý.

### Dữ liệu Web giao cho Rule Engine

- `SceneConfig` có `scene_id`, `version`, `source_id`, `reference_frame_ms` (MP4) hoặc thời điểm chụp (live), `reference_size`; hai `roads` A/B. Mỗi đường có hai `direction_regions` A1/A2 hoặc B1/B2 với `direction_polygon`, `allowed_direction`; cấp đường có một `center_boundary` phân cách hai chiều và `signal_group`. Thêm `intersection_polygon` để bỏ xét lấn ranh giới ở vùng giao cắt và `stop_line` cho từng phía xe đi vào. Tọa độ chuẩn hóa theo ảnh; Web kiểm tra polygon đủ điểm, ranh giới/vạch đủ hai đầu và mũi tên có độ dài khác 0 trước khi lưu. Một phiên bản đã dùng cho phép chấm không bị sửa đè.
- `SignalProgram` lưu chế độ `manual|timed`, thời lượng xanh A/B, vàng, cả hai đỏ, thời điểm bắt đầu và hành động dừng/tạm dừng. `SignalTimeline` có `video_id`, `version`, các `{at_video_ms, phase, source}`; pha chỉ nhận `A_GREEN`, `A_YELLOW`, `ALL_RED`, `B_GREEN`, `B_YELLOW`. Với `simulation`, nút “Cho A/B đi” hoặc chương trình timed sinh các pha chuyển tiếp trên **thời gian video**; với `manual_annotation`, người dùng đánh dấu các pha thực sự thấy trong clip. Bấm thủ công khi video đang chạy sẽ tạm dừng trước để chọn đúng mốc. Một lần chạy rule dùng timeline đã lưu thành phiên bản, không dùng màu đèn hiện trên trình duyệt làm nguồn sự thật.
- Nếu clip không quay đèn thật, timeline `simulation` chỉ kiểm tra luồng xử lý và giao diện. Mọi sự kiện dựa vào timeline này phải mang nhãn **mô phỏng**, không trình bày như vi phạm giao thông đã xảy ra trong clip.
- `RuleRun` tham chiếu **một** `TrackingRun`, **một** phiên bản `SceneConfig` và **một** phiên bản `SignalTimeline`; nó sinh `events.jsonl`. Sửa làn hoặc timeline chỉ tạo `RuleRun` mới từ track cũ, không chạy lại YOLO. `ViolationEvent` có loại rule, ID xe, thời gian, lý do, ảnh/clip và trạng thái duyệt.

### Từ xe tự nhận diện đến một sự kiện có chứng cứ

Tracker tự tạo box/ID ngay khi phát hiện xe; Web chỉ hiển thị chúng. Rule Engine nhận các quan sát của **cùng ID** theo thời gian và giữ trạng thái riêng cho từng loại lỗi. Ví dụ, xe ID 17 cắt vạch lúc A đỏ ở giây 12 thì lưu đúng **một** event `red_light` tại giây 12, với ảnh toàn cảnh có box/ID/vạch/pha và ảnh crop xe. Các frame 12,1–13,0 còn thấy xe không tạo thêm event. Ngược chiều chỉ phát một lần sau khi quỹ đạo ngược đã được xác nhận; lấn qua phân cách chỉ phát một lần khi xe sang vùng kia đủ ổn định. Một xe có thể có các **loại lỗi khác nhau**, nhưng không lặp cùng loại lỗi mỗi frame.

Dùng khóa ổn định tối thiểu `(rule_run_id, segment_id, track_id, rule_type)` và trạng thái “đã phát” cho một lượt đi liên tục; DB cũng có ràng buộc chống import trùng. Nếu vài frame sau mới đủ chắc để xác nhận, lưu mốc cắt vạch/vượt ranh giới đầu tiên làm `event_timestamp_ms` để ảnh chụp đúng lúc. ID đứt ở mốc quyết định thì ghi `INSUFFICIENT_EVIDENCE` vào diagnostics, không tự tạo event. Nếu tracker đổi ID, không thể bảo đảm hai ID là cùng một xe; các ca nghi trùng cần được hiển thị để người xem duyệt.

Các model Django dự kiến: `VideoAsset`, `CameraSource`, `TrackingRun`, `TrackFrame`, `SceneConfig`, `SignalProgram`, `SignalTimeline`, `SignalChange`, `RuleRun`, `ViolationEvent`, `ReviewAction`. Định dạng trao đổi là JSON/JSONL rõ phiên bản; nhóm làm thuật toán có thể xuất event vào file trước khi Web nhập DB.

## 5. Các mốc bạn có thể thực hiện tuần tự

**Quyết định cho bản demo:** báo cáo [`vd3` hiện có](P0_VD3_REPORT.md) cho thấy vẫn có xe máy bỏ sót và ID ngắn. Điều này **không chặn việc lập trình W0–W7**: dùng pipeline sẵn có và các quỹ đạo/pha kiểm thử tự tạo để chạy đủ ba rule. Khi một ID bị đứt đúng vùng xét vi phạm, rule phải trả “chưa đủ dữ liệu” thay vì tạo kết luận chắc chắn. Chỉ công bố độ chính xác sau khi có clip mục tiêu và nhãn thật; việc đó là mốc đánh giá/cải thiện tiếp theo.

| Mốc | Bạn xây gì | Cách tự kiểm tra trước khi làm tiếp |
| --- | --- | --- |
| **W0 — màn hình và MP4** | Django project, phụ thuộc Web, SQLite migration, bố cục video ~75% và panel đèn ~25%; nút Chọn nguồn mở danh sách MP4 và ô URL DroidCam. Phát/tua MP4 qua HTTP byte-range; URL live ghi nhãn “sẽ kích hoạt ở W7”. | `manage.py check`, `migrate`, `runserver`; chọn `vd3`, phát/tua đầu/giữa/cuối và thấy nhãn VIDEO GHI SẴN. |
| **W1 — box/ID trên Web** | Import `tracks.jsonl` và `summary.json` có sẵn; chuẩn hóa output ba pipeline; Canvas vẽ box, ID, quỹ đạo, điểm tiếp xúc dự kiến và trạng thái đo/dự đoán. | Chọn run `vd3`, tua đến frame có track, box khớp xe; frame bị bỏ hiện thiếu dữ liệu. Rà ca xe bị bỏ sót, ID đổi, box sai ngay trên Web. |
| **W2 — chạy tracking từ Web** | Nút chọn thuật toán/độ rộng và chạy worker riêng với trạng thái `QUEUED/RUNNING/DONE/FAILED`, một job CPU mỗi lần. Mặc định YOLOv8n + ByteTrack; vẫn cho chọn hai pipeline còn lại. | Chạy `vd3` từ Web, xem kết quả box/ID và summary; Web không treo, đầu vào sai/worker lỗi hiện thông báo. |
| **W3 — chụp frame, gán quy ước đường** | Editor Canvas trên frame đã quay để gán A/B, hai vùng chiều mỗi đường, mũi tên, hai đường phân cách, vùng giao cắt và vạch dừng; lưu phiên bản theo nguồn/góc camera. Người dùng không vẽ xe/ID. | Chụp một frame, đánh dấu/lưu, tải lại vẫn đúng; đổi kích thước cửa sổ không lệch mốc; thiếu mũi tên/vùng/ranh giới báo lỗi. |
| **W4 — hai quy tắc hình học** | Từ track tự nhận diện và SceneConfig, tính ngược chiều và vượt ranh giới hai chiều qua nhiều frame; lưu một sự kiện nghi vấn/loại lỗi/xe kèm ảnh box tại mốc kích hoạt. | Quỹ đạo kiểm thử có ca đúng/sai; xe tiếp tục xuất hiện 30 frame sau khi kích hoạt vẫn chỉ có một event; không báo khi xe đứng, ID đứt hoặc chạy ở giữa ngã tư. |
| **W5 — pha đèn và vượt đỏ** | Panel A/B thủ công và hẹn giờ trên timeline MP4; rule xét xe qua vạch dừng theo pha tương ứng, chụp đúng xe tại lúc cắt vạch. | Tua/pause/tải lại ra cùng pha ở cùng mốc; không A/B cùng xanh; một xe đã vượt vạch lúc đỏ chỉ có một event dù còn xuất hiện nhiều frame; clip không có đèn thật ghi “mô phỏng”. |
| **W6 — sự kiện và duyệt** | Danh sách nghi vấn, timeline, ảnh/clip và `pending/confirmed/dismissed`; có thể dùng fixture gắn nhãn giả lập khi đợi Rule Engine. | Bấm sự kiện tua đúng mốc, xem lý do/ảnh; tải lại vẫn còn quyết định duyệt; import output thật không tạo trùng sự kiện. |
| **W7 — DroidCam và cổng phần cứng** | Mở URL DroidCam, bộ đọc frame mới nhất, chụp cảnh và tracking live; chuẩn bị `SignalController`/adapter Serial ACK cùng fake serial để thử khi chưa có sa bàn. | Luồng live giả cho thấy box/ID, FPS, tuổi frame, số frame bỏ và reset ID khi mất hình; fake ACK/mất ACK hoạt động. Khi có điện thoại/Arduino thật, kiểm tra lại kết nối và LED; chỉ ACK thật mới đại diện trạng thái đèn vật lý. |

Sau khi **mã Web** đã được triển khai, các lệnh dự kiến sẽ là:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
# terminal thứ hai, khi đã có W2:
.\.venv\Scripts\python.exe manage.py run_worker
```

**Các lệnh này chưa chạy được ở thời điểm viết kế hoạch vì `manage.py` và `requirements-web.txt` chưa tồn tại.** Khi W0 xong, cập nhật README bằng lệnh thực tế đã thử từ bản clone sạch.

## 6. Thứ tự giao việc với các thành viên khác

Bạn có thể hoàn tất W0–W6 bằng `vd3`, output tracking hiện có và quỹ đạo/pha kiểm thử được xác định đáp án; một clip sa bàn quay sau sẽ giúp kiểm tra và cải thiện model mà không cần viết lại Web/rule. Người làm Rule Engine đọc `tracks.jsonl`, `SceneConfig`, `SignalTimeline` rồi xuất `events.jsonl` đúng schema. W7 triển khai và thử luồng live/Serial bằng fake trước, rồi thử điện thoại/Arduino thật khi có thiết bị. Replay dùng `video_timestamp_ms`; live dùng mốc nhận frame và ACK trên laptop.

**Điểm bắt đầu hợp lý nhất:** W0 và W1. Sau hai mốc này Web mở được `vd3.mp4` với box/ID đã tính sẵn, giúp bạn quan sát và ghi lỗi tracking trước khi viết quy tắc. W2 thêm khả năng tự chạy lại từ Web; W3 mới vẽ hình học; W4–W5 mới kết luận hành vi. Cần tách **độ đúng của nhận diện xe** và **độ đúng của sự kiện vi phạm** khi báo cáo.
