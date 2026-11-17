# WEB API CONTRACT & DATA SCHEMA (HỢP ĐỒNG API VÀ DỮ LIỆU)

> Ngày chốt: 14/11/2026  
> Trạng thái: **ĐÃ CHỐT BỞI LEAD** — Áp dụng chung cho Subagent A, Subagent B, Subagent C và Lead tích hợp.  
> Không tự ý sửa đổi endpoint hoặc schema nếu không có sự thống nhất chung.

---

## 1. Phân chia phạm vi và nguyên tắc cốt lõi

1. **Subagent A — Backend Django, Video streaming, Job tracking & Evidence Service:**
   - Sở hữu: `manage.py`, `requirements-web.txt`, `web/traffic_web/**`, `web/monitor/models.py`, `web/monitor/migrations/**`, `web/monitor/views.py`, `web/monitor/services/**`, `web/monitor/management/commands/**`.
   - Cung cấp HTTP Range streaming cho video MP4 trong `data/raw/` (an toàn path traversal).
   - Cung cấp dịch vụ chụp ảnh chứng cứ: lưu 1 ảnh toàn cảnh vẽ box vi phạm + 1 ảnh crop xe đúng mốc `event_timestamp_ms`.
   - Quản lý tracking jobs (chạy CLI không `--show`, mapping đúng `--output` / `--output-dir`, trạng thái `QUEUED/RUNNING/DONE/FAILED`, 1 job CPU tại 1 thời điểm).
   - Cung cấp REST API phục vụ UI và Rule Engine.

2. **Subagent B — Frontend UI, Canvas Video Player, Road Convention Editor:**
   - Sở hữu: `web/templates/**`, `web/static/**`, fixtures giao diện trong `web/fixtures/`.
   - Bố cục 75/25: Màn hình video lớn (HTML5 video phát MP4 gốc + Canvas overlay vẽ box/ID/quỹ đạo lấy từ API theo `video_timestamp_ms`).
   - Editor quy ước tĩnh trên frame chụp: vẽ đường A (chiều A1, A2, phân cách, stop_line), đường B (chiều B1, B2, phân cách, stop_line), vùng giao cắt `intersection_polygon`.
   - Panel đèn: Manual ("Cho A đi", "Cho B đi", "Cả hai đỏ") & Timed; **tuyệt đối không bao giờ cho A và B cùng xanh**.
   - Trang duyệt vi phạm: bảng sự kiện, tua video đến đúng giây vi phạm, hiển thị ảnh toàn cảnh + ảnh crop, đổi `review_status` (`pending`, `confirmed`, `dismissed`).

3. **Subagent C — Pure Python Rule Engine & Signal Controller:**
   - Sở hữu: `src/traffic_monitor/traffic_rules/**`, `tests/traffic_rules/**`, fixtures rule trong `tests/traffic_rules/fixtures/`.
   - Hoàn toàn độc lập Django, chạy được qua CLI / unit test độc lập.
   - 3 Rule:
     - `wrong_way`: Đi ngược chiều quy định của vùng `direction_region` (xét quỹ đạo điểm tiếp xúc mặt đường qua nhiều frame quan sát).
     - `lane_encroachment`: Lấn qua đường phân cách `center_boundary` giữa hai chiều của cùng một đường ngoài vùng giao cắt, duy trì đủ dải đệm & số frame.
     - `red_light`: Cắt vạch dừng `stop_line` của hướng xe tương ứng khi nhóm đèn đang đỏ (hoặc pha không phải Green).
   - **Nguyên tắc kích hoạt 1 lần:** Trạng thái lưu theo `(segment_id, track_id, rule_type)`. Chỉ phát event khi chuyển từ chưa vi phạm sang xác nhận; các frame tiếp theo của xe trong lượt đi đó KHÔNG phát thêm event.
   - `SignalController` interface + fake serial ACK + adapter `pyserial`.

---

## 2. Chuẩn dữ liệu (Data Schemas)

### 2.1. `TrackFrame` (Lưu & Trả về theo frame)
Mỗi dòng trong `tracks.jsonl` hoặc query API:
```json
{
  "camera_id": "CAM_01",
  "segment_id": "seg0",
  "frame_index": 120,
  "video_timestamp_ms": 4000,
  "processing_size": [1280, 606],
  "tracks": [
    {
      "track_id": 5,
      "vehicle_type": "motorcycle",
      "class_confidence": 0.82,
      "bbox_xyxy": [564, 377, 604, 428],
      "ground_point_xy": [584, 428],
      "trajectory_xy": [[570, 390], [584, 428]],
      "track_quality": "confirmed",
      "observation_kind": "detection"
    }
  ]
}
```

### 2.2. `SceneConfig` (Quy ước tĩnh ngã tư)
Tọa độ điểm tính theo pixel của ảnh tham chiếu `reference_size` `[width, height]`:
```json
{
  "scene_id": "scene_vd3_v1",
  "version": 1,
  "source_id": "vd3.mp4",
  "reference_frame_ms": 0,
  "reference_size": [1912, 906],
  "roads": {
    "A": {
      "name": "Đường A (Trục dọc)",
      "signal_group": "A",
      "center_boundary": [[950, 100], [960, 850]],
      "direction_regions": [
        {
          "id": "A1",
          "name": "A1 (Từ trên xuống)",
          "polygon": [[800, 100], [950, 100], [960, 850], [800, 850]],
          "allowed_direction": [0, 1]
        },
        {
          "id": "A2",
          "name": "A2 (Từ dưới lên)",
          "polygon": [[950, 100], [1100, 100], [1120, 850], [960, 850]],
          "allowed_direction": [0, -1]
        }
      ],
      "stop_lines": [
        {
          "id": "stop_A1",
          "direction_region_id": "A1",
          "line": [[800, 300], [950, 300]]
        },
        {
          "id": "stop_A2",
          "direction_region_id": "A2",
          "line": [[955, 600], [1110, 600]]
        }
      ]
    },
    "B": {
      "name": "Đường B (Trục ngang)",
      "signal_group": "B",
      "center_boundary": [[100, 450], [1800, 460]],
      "direction_regions": [
        {
          "id": "B1",
          "name": "B1 (Từ trái sang phải)",
          "polygon": [[100, 450], [1800, 460], [1800, 600], [100, 600]],
          "allowed_direction": [1, 0]
        },
        {
          "id": "B2",
          "name": "B2 (Từ phải sang trái)",
          "polygon": [[100, 300], [1800, 300], [1800, 450], [100, 450]],
          "allowed_direction": [-1, 0]
        }
      ],
      "stop_lines": [
        {
          "id": "stop_B1",
          "direction_region_id": "B1",
          "line": [[700, 455], [700, 600]]
        },
        {
          "id": "stop_B2",
          "direction_region_id": "B2",
          "line": [[1200, 300], [1200, 445]]
        }
      ]
    }
  },
  "intersection_polygon": [[700, 300], [1200, 300], [1200, 600], [700, 600]]
}
```

### 2.3. `SignalTimeline` & Pha đèn
Các pha hợp lệ:
- `A_GREEN`: Tuyến A Xanh, Tuyến B Đỏ
- `A_YELLOW`: Tuyến A Vàng, Tuyến B Đỏ
- `ALL_RED`: Tuyến A Đỏ, Tuyến B Đỏ (pha chuyển tiếp an toàn)
- `B_GREEN`: Tuyến A Đỏ, Tuyến B Xanh
- `B_YELLOW`: Tuyến A Đỏ, Tuyến B Vàng
- Tuyệt đối cấm pha `A_GREEN` và `B_GREEN` đồng thời.

Cấu trúc `SignalTimeline`:
```json
{
  "timeline_id": "timeline_vd3_v1",
  "version": 1,
  "video_id": "vd3.mp4",
  "mode": "simulation",
  "changes": [
    {"at_video_ms": 0, "phase": "A_GREEN", "source": "simulation", "seq": 1},
    {"at_video_ms": 10000, "phase": "A_YELLOW", "source": "simulation", "seq": 2},
    {"at_video_ms": 13000, "phase": "ALL_RED", "source": "simulation", "seq": 3},
    {"at_video_ms": 15000, "phase": "B_GREEN", "source": "simulation", "seq": 4},
    {"at_video_ms": 25000, "phase": "B_YELLOW", "source": "simulation", "seq": 5},
    {"at_video_ms": 28000, "phase": "ALL_RED", "source": "simulation", "seq": 6}
  ]
}
```

### 2.4. `ViolationEvent` (`events.jsonl`)
**Quy tắc sinh `event_id` ổn định & chống trùng:**  
`event_id = f"{rule_run_id}_{segment_id}_{track_id}_{rule_type}"`
```json
{
  "event_id": "run20261105_seg0_trk17_red_light",
  "tracking_run_id": "run_20261105_093319_774",
  "rule_run_id": "rule_run_001",
  "segment_id": "seg0",
  "rule_type": "red_light",
  "track_id": 17,
  "vehicle_type": "motorcycle",
  "event_timestamp_ms": 12000,
  "bbox_xyxy": [479, 240, 498, 264],
  "scene_config_version": 1,
  "signal_source": "simulation",
  "reason": "Xe ID 17 cắt vạch stop_A1 khi nhóm đèn A đang ĐỎ tại mốc 12000 ms",
  "full_image_path": "/media/evidence/run20261105_seg0_trk17_red_light_full.jpg",
  "crop_image_path": "/media/evidence/run20261105_seg0_trk17_red_light_crop.jpg",
  "review_status": "pending"
}
```

---

## 3. Danh sách REST Endpoints

### 3.1. Quản lý Video
- `GET /api/videos/`
  - Trả về danh sách file `.mp4` trong `data/raw/` kèm metadata (tên, size_bytes, duration_ms, fps, width, height).
- `POST /api/videos/upload/`
  - Upload file MP4 mới vào `data/raw/`, xác thực định dạng và đuôi mở rộng, không cho phép ghi đè đường dẫn ngoài `data/raw/`.
- `GET /media/videos/<str:filename>` hoặc `GET /api/videos/<str:filename>/stream/`
  - Phát video hỗ trợ **HTTP 206 Partial Content (HTTP Range Requests)** để trình duyệt tua đến giây bất kỳ.
- `GET /api/videos/<str:filename>/snapshot/?at_ms=<int>`
  - Trích xuất 1 frame tĩnh JPEG tại mốc `at_ms` để mở Canvas Editor cấu hình ngã tư.

### 3.2. Quản lý Tracking Jobs
- `POST /api/tracking/jobs/`
  - Body:
    ```json
    {
      "source": "vd3.mp4",
      "algorithm": "3",
      "width": 1280,
      "tile_imgsz": 640
    }
    ```
  - Khởi chạy subprocess CLI (`yolo_camera.py`, `motion_camera.py`, hoặc `tiled_yolo11_camera.py`) KHÔNG CÓ `--show`, ánh xạ `--output` hoặc `--output-dir` tương ứng.
  - Trả về: `{"job_id": "...", "status": "QUEUED"}`.
- `GET /api/tracking/jobs/<str:job_id>/`
  - Trả về trạng thái job: `QUEUED`, `RUNNING`, `DONE`, `FAILED`, log gần nhất, lỗi nếu có.
- `GET /api/tracking/runs/<str:run_id>/tracks/`
  - Query parameters: `?from_ms=<int>&to_ms=<int>`
  - Trả về danh sách `TrackFrame` trong cửa sổ thời gian phát (ví dụ 3-5 giây quanh vị trí video hiện tại) để Canvas vẽ overlay, không nạp toàn bộ file 10MB vào RAM trình duyệt.

### 3.3. Cấu hình Cảnh (SceneConfig)
- `GET /api/scene-configs/?source_id=<filename>`
  - Lấy danh sách các phiên bản cấu hình của video/nguồn.
- `POST /api/scene-configs/`
  - Lưu phiên bản `SceneConfig` mới. Backend kiểm tra tính hợp lệ hình học (polygon đủ đỉnh, ranh giới đủ 2 đầu, vector hướng khác 0) trước khi cấp `version`.
- `GET /api/scene-configs/<str:scene_id>/`
  - Lấy chi tiết `SceneConfig`.

### 3.4. Quản lý Pha Đèn (SignalTimeline)
- `GET /api/signal-timelines/?video_id=<filename>`
  - Lấy danh sách timeline của video.
- `POST /api/signal-timelines/`
  - Tạo timeline từ cấu hình thủ công hoặc theo thời gian (timed generator).
  - Backend xác thực không cho phép pha nào có A và B cùng xanh.
- `GET /api/signal-timelines/<str:timeline_id>/phase_at/?at_ms=<int>`
  - Tra cứu pha đèn tại mốc thời gian video `at_ms`.

### 3.5. Chạy Rule & Sự Kiện (RuleRuns & Events)
- `POST /api/rules/run/`
  - Body:
    ```json
    {
      "tracking_run_id": "run_20261105_093319_774",
      "scene_config_id": "scene_vd3_v1",
      "signal_timeline_id": "timeline_vd3_v1"
    }
    ```
  - Gọi Rule Engine (Subagent C) xử lý `tracks.jsonl`, sinh `events.jsonl`.
  - Gọi Evidence Service (Subagent A) cắt ảnh toàn cảnh + crop cho mỗi event.
  - Lưu vào cơ sở dữ liệu `ViolationEvent`.
- `GET /api/events/`
  - Query parameters: `?run_id=...&rule_type=...&review_status=...`
  - Trả về danh sách sự kiện vi phạm.
- `PATCH /api/events/<str:event_id>/review/`
  - Body: `{"review_status": "confirmed" | "dismissed" | "pending", "note": "..."}`
  - Cập nhật trạng thái duyệt của sự kiện.
- `GET /media/evidence/<str:filename>`
  - Phục vụ ảnh chứng cứ (ảnh toàn cảnh box ID và crop xe).

### 3.6. DroidCam Live & Thiết bị Giả lập
- `POST /api/live/connect/`
  - Body: `{"url": "http://192.168.1.20:4747/video"}`
  - Thử kết nối URL, khởi động bộ đọc frame mới nhất trong thread nền.
- `GET /api/live/preview/`
  - Trả về frame JPEG mới nhất từ bộ đệm.
- `GET /api/live/status/`
  - Trả về: `{"status": "connected"|"disconnected"|"error", "frame_age_ms": 45, "dropped_frames": 2}`.

---

## 4. Kiểm thử tích hợp Lead sẽ chạy

1. `python manage.py check` sạch, không cảnh báo nghiêm trọng.
2. `pytest tests/` chạy pass toàn bộ test backend + rule engine.
3. Test tua video bằng HTTP Range (Header `Range: bytes=0-1024`, trả mã `206`).
4. Test chạy 1 tracking job trên `vd3.mp4`, kiểm tra `tracks.jsonl` được tạo ra.
5. Test kích hoạt 1 lần của Rule Engine: xe xuất hiện 30 frame liên tiếp sau khi vi phạm chỉ phát đúng **1 event**, không tăng khi import/chạy lại.
6. Mở trình duyệt Web local: kiểm tra bố cục 75/25, Canvas phủ box/ID khi video chạy, editor vẽ được A/B, bảng đèn chuyển đúng pha.
