# Thử MOG2 và frame difference + Kalman trên `vd2`

Ngày 27/10/2026. Chạy **300 frame đầu** của [bản `vd2` phát 1×](../data/CLIP_CATALOG.md) ở 960 × 492, khoảng 20 giây video. Hai nhánh dùng cùng frame đầu vào, **không dùng YOLO**.

## Xem ngay

- [Video so sánh ba ô, H.264](../outputs/vd2_classical_compare_300/comparison_h264.mp4): **RAW** bên trái, **MOG2 + Kalman** ở giữa, **FrameDiff + Kalman** bên phải. Dải đen/trắng dưới mỗi nhánh là mặt nạ chuyển động; pixel trắng là nơi thuật toán thấy thay đổi.
- [Ảnh frame 100](../outputs/vd2_classical_compare_300/debug_frame_100.jpg): cả hai nhánh có blob. [Ảnh frame 150](../outputs/vd2_classical_compare_300/debug_frame_150.jpg): frame difference không có blob, nên các box tím `P` chỉ là dự đoán Kalman.
- [Bảng tóm tắt JSON](../outputs/vd2_classical_compare_300/summary.json) và [theo dõi từng frame](../outputs/vd2_classical_compare_300/tracks.jsonl).

Muốn **thấy cửa sổ trong lúc chạy** từ terminal IDE tại thư mục `IOT`:

```powershell
& '.\IOT_CAM\TrafficMonitor_IoT\run_classical_vd2.cmd'
```

Launcher chạy 300 frame đầu; dùng `--max-frames 2737` nếu muốn chạy cả file. **Space** tạm dừng, **N** đi một frame khi tạm dừng, **Q/Esc** dừng. Cửa sổ do công cụ Codex mở có thể nằm trong phiên desktop cách ly; chạy launcher từ terminal của bạn để nhìn thấy cửa sổ.

## Cách chạy

1. **MOG2:** OpenCV `createBackgroundSubtractorMOG2` tạo mặt nạ tiền cảnh; bỏ bóng có giá trị 127, lọc nhiễu bằng morphology rồi lấy contour.
2. **FrameDiff:** lấy trị tuyệt đối chênh lệch hai frame xám liền kề, ngưỡng 22, lọc nhiễu rồi lấy contour. Cách này có thể tạo hai vệt cũ/mới cho một xe và không tạo blob nếu hai frame quá giống nhau.
3. **Theo dõi cho từng nhánh:** mỗi blob là một phép đo tâm box; Kalman trạng thái `[x, y, vx, vy]` dự đoán tâm frame kế tiếp, ghép blob bằng global assignment với ngưỡng 65 pixel. Track được vẽ sau hai phép đo; khi mất blob, giữ tối đa 5 frame dự đoán. Box tím `P` là **dự đoán**, box xanh/cam là **phép đo từ ảnh**.

Đây là script so sánh tối giản ở [`classical_compare.py`](../src/traffic_monitor/classical_compare.py); **không phải** toàn bộ tracker TechGAR (TechGAR còn nhiều bước ghép, kiểm tra che khuất và mô tả ngoại hình). Các nhánh cũng chưa có ROI giao thông, phân loại xe, nhãn chuẩn hay cảnh báo vi phạm.

## Kết quả quan sát

| Chỉ số trên 300 frame | MOG2 + Kalman | FrameDiff + Kalman |
| --- | ---: | ---: |
| ID được tạo | 323 | 573 |
| Quan sát box từ ảnh trên track đã xác nhận | 14.360 | 6.693 |
| Vị trí chỉ do Kalman dự đoán | 2.397 | 7.122 |
| Frame không có blob hợp lệ | 7 | 92 |

Script xử lý 300 frame trong khoảng 12,2 giây trên CPU của lần thử này. Các con số ID **không phải số xe thật hay độ chính xác**: một xe có thể sinh nhiều ID, nhiều xe có thể nhập một blob, và các box có thể bám bóng/người. Trong 299 cặp frame liên tiếp đầu tiên, 65 cặp có chênh lệch pixel trung bình dưới 0,1 sau khi thu nhỏ; điều này góp phần khiến FrameDiff thường không có blob. MOG2 nhìn nền tích lũy nên vẫn có nhiều blob hơn, nhưng cảnh đông làm box/ID dễ nhầm. Cần video ghi thật ở 1× và gán nhãn để đánh giá tracking đúng sai.
