# Tốc độ xử lý và độ mượt của cửa sổ debug

`vd3.mp4` có 30 frame/giây. Muốn cửa sổ cập nhật đúng nhịp video, toàn bộ việc đọc frame, phát hiện, gán ID, vẽ box và hiển thị phải xong trong khoảng **33 ms/frame**. Nếu một frame mất 250 ms, cửa sổ chỉ cập nhật khoảng 4 lần/giây dù chương trình vẫn đọc đủ mọi frame. File sẽ phát chậm, không tự động mất frame.

## Vì sao ba lựa chọn khác nhau

- **1 — YOLO11s chia 4 ô:** chạy detector bốn lần cho mỗi frame để nhìn xe máy nhỏ. Đây là phần tốn CPU nhất; giảm độ rộng giúp nhanh hơn nhưng xe nhỏ có thể khó thấy hơn.
- **2 — TechGAR MOG2:** xử lý vùng chuyển động, hình thái học và ghép quỹ đạo trên nhiều điểm ảnh. Chi phí tăng rất mạnh khi tăng độ phân giải. Nó không phân loại xe; hạ độ phân giải có thể làm xe nhỏ biến mất hoặc box sai.
- **3 — YOLOv8n:** model nhỏ, chạy một lần trên toàn frame. Thường cập nhật cửa sổ nhanh hơn lựa chọn 1, nhưng dễ bỏ sót xe máy rất nhỏ.

CPU phải làm lần lượt các bước của một frame: giải mã MP4 → đổi kích thước → tìm box → ghép box với ID cũ → vẽ quỹ đạo → hiển thị/ghi file. YOLO tốn phần lớn thời gian ở các phép tích chập của mạng nơ-ron; chia bốn ô nhân số lượt suy luận. TechGAR MOG2 không chạy mạng nơ-ron nhưng vẫn cập nhật mô hình nền, làm sạch mask và ghép nhiều vùng chuyển động; số điểm ảnh lớn và nhiều vùng nhiễu đều tăng chi phí. ByteTrack còn ghép ID theo từng frame, nên không thể xử lý các frame của một video hoàn toàn độc lập nếu muốn giữ ID liên tục.

Máy kiểm tra dùng PyTorch CPU (`torch.cuda.is_available() == False`). Hai pipeline YOLO hiện tự chọn CUDA nếu môi trường PyTorch có GPU tương thích; TechGAR vẫn là pipeline OpenCV/CPU. Đây là nút thắt hiệu năng của máy đã đo, chưa phải giới hạn cố định của mọi phần cứng: GPU tương thích, model nhẹ hơn, ROI, độ phân giải thấp hơn hoặc camera gần hơn có thể thay đổi kết quả. Không nên tuyên bố một cấu hình đạt thời gian thực trước khi đo trên máy đích.

## Số đo kiểm tra nhanh ngày 27/10/2026

Cùng **45 frame đầu `vd3`**, chạy lần lượt một tiến trình trên CPU, rộng 640 px, không mở cửa sổ và không mã hóa MP4:

| Pipeline | FPS xử lý | Quan sát/45 frame | Lưu ý |
| --- | ---: | ---: | --- |
| 1 YOLO11s chia 4 ô | 3,79 | 1.171 | 4 lần suy luận/frame |
| 2 TechGAR MOG2 | 22,71 | 137 | Ngưỡng blob đang giữ theo cấu hình gốc; nhiều xe nhỏ có thể bị lọc |
| 3 YOLOv8n | 10,83 | 516 | Có chi phí khởi tạo tracker ở đầu phép thử |

Số quan sát và số ID **không phải** số xe đúng hoặc độ chính xác. Phép thử ngắn, không có GUI; tốc độ khi xem trực tiếp có thể thấp hơn. Các lượt cũ ở 1280 px với GUI/ghi video cho TechGAR khoảng 1,45 FPS và YOLOv8n khoảng 9,39 FPS; điều kiện khác nhau nên chỉ dùng để giải thích cảm giác lag, không dùng xếp hạng model.

## Cách dùng sau thay đổi

Chạy `menu.py` từ terminal IDE. Ba preset hiện **không bỏ frame của file**; chúng chỉ thay độ rộng ảnh xử lý. Chọn `N` ở câu hỏi ghi MP4 để tránh bước mã hóa khi chỉ cần xem và ghi JSONL. Dòng dưới cùng cửa sổ hiện FPS nguồn, FPS xử lý gần đây và hệ số chậm. Khi nhấn `Q`, `summary.json` ghi số frame đã xử lý. Pipeline 1 ghi thêm `read_frames` và `skipped_frames`; từ menu `skipped_frames` phải bằng 0.

Nếu mục tiêu là **xem mượt video đã phân tích** mà vẫn giữ đủ frame, cần chờ xử lý xong rồi phát lại MP4 debug ở FPS gốc. Việc xử lý trực tiếp và đồng thời hiển thị đúng 30 FPS chỉ có thể xảy ra khi pipeline thật sự đạt ít nhất 30 FPS. Bỏ frame sẽ làm cửa sổ bắt kịp thời gian hơn nhưng làm mất quan sát, ảnh hưởng ID và không phù hợp lượt đánh giá file.

Đã thử gộp bốn ô của YOLO11s thành một batch trên vài frame đầu ở 960 px: khoảng 0,30 giây/frame, so với 0,21 giây/frame khi gọi tuần tự. Thử nghiệm quá ngắn để kết luận chung, nhưng không cho thấy lợi ích trên CPU hiện tại nên chưa đổi cách suy luận.

Để tối ưu tiếp, đo trên một đoạn có nhãn: so sánh 640/960/1280 px, thử ROI loại vùng không có đường, thử model nhỏ hơn hoặc phần cứng có GPU. Chỉ nhận cấu hình nhanh hơn nếu độ liên tục ID xe máy và số xe bị bỏ sót vẫn đạt mức chấp nhận được trên đoạn kiểm tra độc lập.
