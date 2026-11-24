# Điều khiển đèn Arduino Uno từ web

Web Django và Uno giao tiếp qua cáp USB Serial ở 9600 baud. Arduino IDE chỉ dùng để **nạp sketch một lần**. Sau đó đóng Serial Monitor và Arduino IDE, chạy web để điều khiển.

## Nạp và kết nối

1. Giữ dây như mạch hiện tại: đường A đỏ/vàng/xanh ở D2/D3/D4; đường B đỏ/vàng/xanh ở D5/D6/D7. Mỗi LED cần điện trở hạn dòng và chung GND. Firmware giả định `HIGH` là sáng, giống sketch hiện tại.
2. Mở `arduino/traffic_signal/traffic_signal.ino` trong Arduino IDE, chọn **Arduino Uno** và đúng cổng COM, rồi bấm **Upload**. Đây là lần dùng IDE cần thiết để thay chương trình `delay()` cũ bằng chương trình nhận lệnh. Sau khi nạp, Uno tự chạy chu kỳ mặc định 5 giây xanh, 2 giây vàng kể cả khi chưa mở web.
3. Đóng **Serial Monitor/Serial Plotter** để giải phóng cổng COM. Cắm Uno vào cùng máy Windows đang chạy Django.
4. Chạy `run_web.bat` hoặc `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000` trong thư mục dự án. Mở `http://127.0.0.1:8000/`.
5. Ở bảng **Đèn giao thông**, chọn cổng USB Serial của Uno (web sẽ gợi ý nếu tìm thấy; số COM thay đổi theo máy) và bấm **Kết nối**. Web sẽ gửi chu kỳ xanh/vàng hiện đang đặt. Bấm **Áp dụng chu kỳ** để đổi thời gian; chuyển tab **Thủ công** rồi bấm bóng đèn để đổi pha. Ở tab Thủ công, bấm vàng ở cả hai đường để Uno sáng cả hai đèn vàng (`ALL_YELLOW`); muốn cả hai đỏ hãy bấm nút **Cả hai đỏ**. Lệnh `AUTO` giữ nguyên 4 tham số, nên sau khi nạp bản sketch có `ALL_YELLOW` web cũ vẫn dùng được.

Khi kết nối, Uno giữ nhịp bằng `millis()` và trả về pha cùng số mili giây còn lại. Web đọc trạng thái đó để hiện đếm ngược; API cũng chuyển pha thực tế vào luồng nhận diện trực tiếp. Chuyển giữa hai hướng có khoảng hai đèn đỏ 0,5 giây. Bấm **Ngắt kết nối** sẽ yêu cầu Uno về cả hai đèn đỏ trước khi đóng cổng; đây là trạng thái dừng chủ động, muốn chạy lại hãy kết nối web và chọn Tự động hoặc bấm Reset trên Uno. Nếu mất USB, web báo lỗi và đánh dấu trạng thái đèn là chưa biết cho luồng nhận diện.

## Kiểm tra nhanh

- Nếu báo cổng đang bận, đóng Serial Monitor và các chương trình khác đang dùng COM, rồi thử lại.
- Nếu không biết số COM, xem **Tools → Port** trong Arduino IDE hoặc **Device Manager → Ports (COM & LPT)**. Đóng IDE trước khi kết nối web.
- Chọn cổng **USB Serial Device/Arduino Uno**, tránh chọn cổng **Standard Serial over Bluetooth link** nếu máy có cả hai.
- Nếu màu LED thực tế khác bảng web, kiểm tra lại dây D2–D7 và cực LED. Đừng đổi thứ tự chân trong web mà chưa đối chiếu mạch.
- MP4 mẫu chỉ dùng để xem trước và thử nhận diện/theo dõi xe. Đèn Uno chạy độc lập khi xem MP4; web không suy ra pha đèn của video đã ghi và không chấm vượt đèn đỏ trên video đó. Pha Uno được đưa vào luồng **camera trực tiếp**.

API USB chỉ nhận yêu cầu từ máy đang chạy Django. Để điều khiển qua mạng, cần thêm xác thực và cơ chế phân quyền trước khi mở endpoint ra ngoài.
