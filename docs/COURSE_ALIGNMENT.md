# Đối chiếu bài giảng, giáo trình và bản bàn giao

Kiểm tra ngày 26/10/2026. Tài liệu nguồn nằm ở thư mục môn học `../../../` và bản bàn giao ở `../../IOT_Traffic_Monitoring_Project_Handoff.md`.

## Những điều bài giảng nêu trực tiếp

| Nguồn | Nội dung đọc được | Tác động đến đồ án |
| --- | --- | --- |
| `0- Gioi thieu mon hoc.pptx`, slide 1 | Đồ án cuối kỳ chiếm 60% điểm môn; tối đa 2 hoặc 3 sinh viên cho một đề tài. | Xác nhận quy mô nhóm và chuẩn bị sản phẩm có thể trình diễn. |
| `1- Tong quan IoT.pptx`, slide 1 | Phần demo tổng quát đề cập sơ đồ, sản phẩm, thành phần phần cứng/API/giao thức và thực nghiệm. | Báo cáo nên có sơ đồ hệ thống, vai trò các thành phần và số liệu thực nghiệm. Đây là nội dung giảng dạy, chưa thấy rubric bắt buộc riêng cho đề tài. |
| `2- 1_2_3_4 Cong nghe ho tro.pdf`, trang 20–29 | Giới thiệu MQTT, mô hình publish/subscribe và broker; cũng giới thiệu CoAP và các giao thức khác. | MQTT phù hợp làm kênh sự kiện/telemetry, nhưng tài liệu chưa chứng minh nó là điều kiện bắt buộc của đồ án. |
| `3- Phat trien he thong IoT - 3.pptx`, slide 1–10 | Bài thực hành MQTT Client/Broker, Mosquitto, MQTT Explorer và giao tiếp với thiết bị. | Có thể tái dùng mô hình thiết bị/vision → broker → backend/Web ở giai đoạn P2/P3. Các URL/version trong slide là ví dụ thực hành cũ, không khóa phiên bản dự án. |
| `4- Cac mien ung dung.pptx`, slide 21 | Smart City là một miền ứng dụng IoT. | Là bối cảnh để trình bày đề tài, không phải thuật toán phát hiện hành vi. |

## Phần giáo trình đáng tận dụng

- `[2] Internet-of-Things (IoT) Systems_ Architectures, Algorithms, Methodologies...pdf`: chương 2 (trang PDF 17–25) về giao thức, database, **time bases** và bảo mật; chương 4 (trang PDF 33–44) về sự kiện. Hữu ích nhất cho thiết kế event, timestamp và kết nối các thành phần.
- `[3] Beginning Data Science IoT and AI on Single Board Computers...pdf`: chương 9 (từ trang PDF 184) về kết nối Wi-Fi, chương 10 (từ trang PDF 220) về ML/AI, chương 12 (từ trang PDF 283) về edge device. Chỉ cần đọc sâu khi đã chọn phần cứng/kiến trúc edge; ví dụ trong sách không phải chỉ định dùng micro:bit hoặc một dịch vụ Cloud cụ thể.
- `[1]. Arshdeep Bahga, Vijay Madisetti, Internet-of-things-a-hands-on-approach.pdf`: bản PDF 514 trang trong workspace không trích xuất được mục lục/chữ bằng công cụ đọc text đã dùng. Giữ làm tài liệu nền và chỉ dẫn chương/trang sau khi xem bản hiển thị hoặc OCR; chưa dùng nó để suy ra yêu cầu kỹ thuật cụ thể.

Không tìm thấy trong phần bài giảng đã kiểm tra một yêu cầu khẳng định rằng đồ án **phải** dùng ESP32, GoPro live, Cloud hay một mô hình AI cụ thể. Cần hỏi giảng viên về rubric cuối kỳ trước khi khóa kiến trúc phần cứng.

## Những điều đã chốt trong bản bàn giao

- Một GoPro cố định; giai đoạn đầu dùng MP4, live chỉ khi model/firmware thực tế hỗ trợ.
- Chỉ ba nhóm hành vi: đi ngược chiều, lấn/đi sai làn theo quy tắc, không chấp hành tín hiệu đèn. Nhận dạng biển số không thuộc phạm vi đầu tiên.
- Tái sử dụng thành phần tracking, ROI và quỹ đạo của TechGAR; đo hiệu quả trên video giao thông trước khi quyết định MOG2 hay YOLO.
- Quy tắc phụ thuộc camera, làn, hướng, loại xe và trạng thái tín hiệu; Web phải sửa được cấu hình và lưu phiên bản có thời điểm hiệu lực.
- Sự kiện là `POSSIBLE_VIOLATION` hoặc `NEEDS_REVIEW`; thiếu dữ liệu thì `UNKNOWN`/`INSUFFICIENT_EVIDENCE`. Không tự động xử phạt.
- Thử nghiệm trên video thật và sa bàn là hai loại minh chứng riêng.

## Đề xuất kỹ thuật, chưa phải quyết định của nhóm

- Dùng MQTT để chứng minh luồng IoT; backend lưu sự kiện và Web hiển thị/cấu hình. Chọn giao thức sau khi rõ yêu cầu giảng viên và sơ đồ triển khai.
- Dùng `ManualSignalProvider`/`ScheduledSignalProvider` cho kiểm thử, `HardwareSignalProvider` khi đã chọn board. Mọi nguồn tín hiệu phải kèm timestamp, clock domain và trạng thái hợp lệ.
- Dùng YOLO pretrained + tracker như phương án đối chứng trên **cùng clip** với TechGAR; không mặc định YOLO tốt hơn hoặc buộc phải huấn luyện lại.

## Điểm cần xác nhận trước khi chốt sản phẩm

Deadline, số thành viên, rubric phần cứng/giao thức/Cloud/thời gian thực, model GoPro, khả năng laptop, kịch bản sa bàn và clip thử nghiệm. Các câu hỏi này không cản việc làm P0 trên MP4.
