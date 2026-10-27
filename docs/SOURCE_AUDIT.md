# Kiểm chứng nguồn tham khảo

Kiểm tra trực tiếp trang nguồn ngày **26/10/2026**. Bảng này đánh giá mức hữu ích cho **đồ án hiện tại**, không xác nhận mã bên ngoài chạy được với TechGAR hoặc video của nhóm. Nguồn nào chưa rõ giấy phép thì chỉ đọc ý tưởng; không chép mã vào dự án.

## Nguồn nên dùng

| Nguồn | Đã kiểm chứng | Cách dùng |
| --- | --- | --- |
| Mã TechGAR trong workspace riêng của tác giả (không có khi clone repo này) | Có `src/techgar/motion_tracker.py` với `MotionVehicleTracker.process_frame(frame, timestamp_s)` trả `(tracks, mask, expired_tracks)` và `active_tracks`; `TrackedVehicle` có ID, bbox, `cx/cy`, history. | Đã viết adapter một camera và thử 4 giây đầu `vd1.mp4`; baseline bỏ sót nhiều xe trên khung mẫu. Xem [báo cáo P0](P0_VD1_REPORT.md). |
| [Ultralytics Track](https://docs.ultralytics.com/modes/track/) | Tài liệu chính thức mô tả tracking có ID và chọn tracker như ByteTrack. [Giấy phép Ultralytics](https://docs.ultralytics.com/help/contributing/) có điều kiện AGPL hoặc Enterprise. | YOLO hiện là hai lựa chọn 1 và 3 trong `menu.py`; vẫn cần đo trên video có nhãn trước khi kết luận chất lượng tracking. |
| [Roboflow Supervision LineZone](https://supervision.roboflow.com/latest/detection/tools/line_zone/) và [PolygonZone](https://supervision.roboflow.com/latest/detection/tools/polygon_zone/) | Tài liệu chính thức có công cụ vùng/đếm đường, `LineZone` cần `tracker_id`; [Supervision](https://supervision.roboflow.com/latest/) ghi giấy phép MIT. | Tham khảo cách định nghĩa vùng/vạch; công cụ đếm qua vạch **không tự kết luận** vượt đèn đỏ hay lấn làn. Cài khi có nhu cầu thực sự. |
| [Open GoPro](https://gopro.github.io/OpenGoPro/) | Tài liệu GoPro có bảng camera/firmware hỗ trợ và chức năng stream qua Wi-Fi/USB cho mẫu tương thích. | Chỉ dùng sau khi biết model/firmware GoPro của nhóm. P0 vẫn dùng MP4. |
| [MQTT specification](https://mqtt.org/mqtt-specification/), [Mosquitto](https://mosquitto.org/documentation/) và [Paho Python](https://eclipse.dev/paho/files/paho.mqtt.python/html/) | Nguồn chính thức cho protocol, broker và Python client. Trang Paho được kiểm tra có ghi lưu ý về phiên bản API/callback, nên phải xem docs đúng phiên bản khi triển khai. | Dùng ở P2 để thực hiện luồng IoT và thử gửi lặp/mất kết nối; MQTT vẫn là đề xuất, chưa được giảng viên xác nhận là bắt buộc. |

## Các repo được nêu trong bản bàn giao

| Repo | Kết quả kiểm chứng | Quyết định hiện tại |
| --- | --- | --- |
| [ilhamfzri/traffic-violation-detection](https://github.com/ilhamfzri/traffic-violation-detection) | Repo còn tồn tại nhưng chủ sở hữu đã **archive** từ 2022; README dùng YOLOv5/SORT cho đèn đỏ, mũ bảo hiểm và ngược chiều. Không thấy giấy phép rõ ở trang repo. | Tham khảo lịch sử kiến trúc, không dùng làm nền tảng. |
| [blikezain/Red_Light_Violation](https://github.com/blikezain/Red_Light_Violation) | Repo tồn tại; README mô tả **chu kỳ đèn mô phỏng**, qua vạch, OCR; ít lịch sử commit; không thấy giấy phép rõ. | Chỉ tham khảo test trạng thái đèn và qua vạch trong sa bàn/mô phỏng. Không coi kết quả trên video thật là phát hiện đèn thật. |
| [Usmankhujaev/Wrong-direction-drivers-detection](https://github.com/Usmankhujaev/Wrong-direction-drivers-detection) | Repo tồn tại; bản gốc 2020 nằm trong `legacy/`, README nói bản hiện đại hóa 2026 dùng YOLO11/ByteTrack và quy tắc vùng vào/ra, hướng, hysteresis. Không thấy giấy phép rõ ở trang repo. | **Tham khảo thuật toán ngược chiều và cách cấu hình**, không chép code. Đây là nguồn cộng đồng sát P0 nhất, nhưng phải kiểm chứng trên clip nhóm. |
| [AnujKumarC/Traffic_AI_Project](https://github.com/AnujKumarC/Traffic_AI_Project) | Repo tồn tại; README trình bày nhiều model, huấn luyện/dataset, OCR và Web; README tự ghi MIT. Quy mô vượt phạm vi P0 và không chứng minh các model phù hợp góc quay nhóm. | Tham khảo phân lớp module và báo cáo; chưa tải toàn bộ repo/model. |
| [harisraja123/Real-Time-Traffic-Violation-Detection](https://github.com/harisraja123/Real-Time-Traffic-Violation-Detection) | Repo tồn tại; README có pipeline riêng cho đèn và lane crossing, dùng nhiều model/DeepSort; README ghi MIT nhưng cần kiểm tra file license trước khi sao chép. | Tham khảo phương pháp lane/line, không cài cả stack. |
| [kyliew1/smart-traffic-light-dashboard](https://github.com/kyliew1/smart-traffic-light-dashboard) | Repo tồn tại; mô hình ESP32 + MQTT + dashboard 3D + điều khiển đèn; không thấy giấy phép rõ ở trang repo. | Tham khảo sơ đồ IoT/sa bàn ở P3, chưa chọn ESP32 hoặc dashboard 3D. |
| [som3a-web/signalwatch-traffic-detection](https://github.com/som3a-web/signalwatch-traffic-detection) | Repo tồn tại; README mô tả Web cấu hình vùng/vạch, bằng chứng và trạng thái review, nhưng repo rất mới và không thấy giấy phép rõ. | Tham khảo UX hiệu chỉnh camera và quản lý sự kiện ở P2; chưa dùng mã. |

## Video, dataset và bài báo

| Nguồn | Kết quả kiểm chứng | Quyết định hiện tại |
| --- | --- | --- |
| [AI City Challenge 2021 Track 1](https://www.aicitychallenge.org/2021-track1-download/) | Trang chính thức còn liên kết tải qua Google Drive. Chưa xem clip cụ thể, giấy phép và mức phù hợp góc quay. | Ứng viên khảo sát sau; chưa tải bộ dữ liệu lớn. |
| [AI City Challenge 2022 Track 1](https://www.aicitychallenge.org/2022-track1-download/) | Trang chính thức còn liên kết Drive và [thỏa thuận dữ liệu](https://www.aicitychallenge.org/wp-content/uploads/2022/02/Dataset-License-AIC2022.pdf). Điều khoản cho phép sử dụng học thuật phi thương mại sau cuộc thi và hạn chế phân phối dữ liệu. | Có thể khảo sát nội bộ; không đưa clip nguyên bản vào repo hoặc sản phẩm công khai. Chưa xác nhận nhãn ba hành vi cần làm. |
| [Bài báo dữ liệu CCTV Đà Nẵng 2026](https://www.techscience.com/cmc/v88n1/67301/html) | Bài báo mở CC BY 4.0 về ảnh CCTV giao thông Việt Nam, 23.364 ảnh; mô tả nhãn phát hiện đối tượng/tín hiệu. Chưa xác minh đường tải **video gốc** hoặc nhãn sự kiện vi phạm. | **Đã tải PDF bài báo** vào `references/papers/` để đọc/trích dẫn. Hữu ích cho chọn góc quay, loại xe và so sánh detector; chưa phải clip P0. |
| [Zenodo 14041920](https://zenodo.org/records/14041920) | Dataset còn tồn tại, khoảng 9,4 GB; bản bàn giao ghi nhóm đã đánh giá video mờ/tối/cũ. | Không ưu tiên và không tải lại. |

### Bản PDF đã tải

Bản PDF được giữ cục bộ và bị `.gitignore` loại khỏi repo; người clone có thể tải từ liên kết nguồn ở dưới.

- Đường dẫn cục bộ trên máy tác giả: `references/papers/Vo_Nguyen_Tran_2026_Vietnamese_CCTV_dataset.pdf` (không có khi clone).
- Trang nguồn: <https://www.techscience.com/cmc/v88n1/67301/html>
- PDF nguồn: <https://cdn.techscience.press/files/cmc/2026/TSP_CMC-88-1/TSP_CMC_78756/TSP_CMC_78756.pdf>
- Kiểm tra: PDF mở được, **19 trang**, **28.777.140 byte**, SHA-256 `d702118b357272b71f1087f043b2ddd0d794166c08b3d51fa37719440b7d7759`.
- Giấy phép bài báo: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); khi dùng hình/số liệu cần dẫn tên tác giả và DOI `10.32604/cmc.2026.078756`.

## Kết luận chọn nguồn

`vd1.mp4` đã có URL nguồn và được chạy thử, nhưng quyền tái phân phối vẫn chưa được xác minh; còn thiếu ROI và nhãn để chấm chất lượng. Repo bên ngoài và dataset lớn chưa được tải vào mã dự án vì chưa có tiêu chí đo cho thấy chúng cần thiết. Tài liệu PDF Đà Nẵng là bản tải tham khảo duy nhất, có xuất xứ và checksum rõ ràng.
