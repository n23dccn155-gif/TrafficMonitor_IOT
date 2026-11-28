"""Làm sạch đầu vào camera trực tiếp trước khi đưa vào YOLO và Rule Engine.

- Cắt khung theo vùng quan tâm (ROI) lấy từ cấu hình cảnh: xe trong vùng được
  nhiều điểm ảnh hơn ở cùng kích thước ảnh vào model.
- Đổi toạ độ box từ ảnh đã cắt/thu nhỏ về pixel của frame gốc.
- Lọc track: chỉ track đủ tuổi mới được xét luật; nhãn lớp lấy theo đa số;
  điểm chân xe được làm mượt để một box giật không tạo vi phạm giả.
"""
from __future__ import annotations

from collections import Counter, deque

from src.traffic_monitor.traffic_rules.geometry import point_in_polygon, scale_point

MAX_SIDE = 960          # cạnh dài nhất của ảnh vào YOLO (khớp imgsz)
ROI_MARGIN = 0.08       # lề thêm quanh ROI, theo tỉ lệ kích thước ROI
MIN_ROI_SIDE = 32
MIN_TRACK_FRAMES = 3    # track phải xuất hiện ít nhất N frame mới được xét luật
SMOOTH_POINTS = 3       # số điểm chân dùng để tính trung bình trượt
TRAJECTORY_POINTS = 60
FORGET_AFTER_FRAMES = 150
STITCH_MAX_GAP_MS = 1500  # track mất lâu hơn mức này thì không nối ID nữa
STITCH_MIN_PX = 40        # bán kính nối ID tối thiểu quanh vị trí dự đoán


def scene_polygons(scene, frame_size) -> list[list[list[int]]]:
    """Các vùng hướng và vùng nút giao, đổi từ toạ độ cảnh sang pixel frame."""
    polygons = [region.polygon for road in scene.roads.values() for region in road.direction_regions]
    polygons.append(scene.intersection_polygon)
    return [
        [scale_point(p, scene.reference_size, frame_size) for p in polygon]
        for polygon in polygons if len(polygon) >= 3
    ]


def roi_rect(polygons, frame_size, margin: float = ROI_MARGIN) -> tuple[int, int, int, int]:
    """Hình chữ nhật bao các vùng (kèm lề), kẹp trong frame; không có vùng thì lấy cả frame."""
    width, height = frame_size
    if not polygons:
        return 0, 0, width, height
    xs = [p[0] for polygon in polygons for p in polygon]
    ys = [p[1] for polygon in polygons for p in polygon]
    pad_x = int((max(xs) - min(xs)) * margin)
    pad_y = int((max(ys) - min(ys)) * margin)
    x1, y1 = max(0, min(xs) - pad_x), max(0, min(ys) - pad_y)
    x2, y2 = min(width, max(xs) + pad_x), min(height, max(ys) + pad_y)
    if x2 - x1 < MIN_ROI_SIDE or y2 - y1 < MIN_ROI_SIDE:
        return 0, 0, width, height
    return x1, y1, x2, y2


def yolo_input_size(crop_width: int, crop_height: int, max_side: int = MAX_SIDE) -> tuple[int, int]:
    """Thu nhỏ một lần, giữ tỉ lệ; không phóng to ảnh nhỏ."""
    scale = min(1.0, max_side / max(crop_width, crop_height))
    return max(2, round(crop_width * scale)), max(2, round(crop_height * scale))


def box_to_frame(box, yolo_size, rect) -> list[int]:
    """Box trong ảnh vào YOLO -> box trong frame gốc (bù tỉ lệ và độ lệch của ROI)."""
    x0, y0, x1, y1 = rect
    scale_x = (x1 - x0) / yolo_size[0]
    scale_y = (y1 - y0) / yolo_size[1]
    return [
        int(round(box[0] * scale_x)) + x0, int(round(box[1] * scale_y)) + y0,
        int(round(box[2] * scale_x)) + x0, int(round(box[3] * scale_y)) + y0,
    ]


def point_in_roi(point, polygons) -> bool:
    return not polygons or any(point_in_polygon(point, polygon) for polygon in polygons)


class TrackFilter:
    """Giữ trạng thái từng track để quyết định track nào đủ tin cậy cho Rule Engine.

    ByteTrack hay đổi ID khi xe bị che hoặc đi nhanh hơn số frame xử lý được. Khi một
    ID mới xuất hiện gần chỗ dự đoán của một track vừa mất, ID mới được nối vào track
    cũ (giữ ID ổn định, tuổi và quỹ đạo) để luật không mất lịch sử của xe.
    """

    def __init__(self, min_frames: int = MIN_TRACK_FRAMES, smooth_points: int = SMOOTH_POINTS):
        self.min_frames = min_frames
        self.smooth_points = smooth_points
        self._frame = 0
        self._tracks: dict[int, dict] = {}   # ID ổn định -> trạng thái
        self._alias: dict[int, int] = {}     # ID của ByteTrack -> ID ổn định
        self._spare_id = 1_000_000           # ID riêng khi ID của ByteTrack đã thuộc xe khác

    def clear(self):
        self._tracks.clear()
        self._alias.clear()

    def next_frame(self):
        """Gọi mỗi frame; quên các track đã mất lâu để bộ nhớ không tăng mãi."""
        self._frame += 1
        stale = {tid for tid, t in self._tracks.items() if self._frame - t["last_seen"] > FORGET_AFTER_FRAMES}
        for tid in stale:
            del self._tracks[tid]
        self._alias = {raw: tid for raw, tid in self._alias.items() if tid not in stale}

    def _find_lost_track(self, point, bbox, now_ms):
        """Track vừa mất (không thấy ở frame này) gần vị trí dự đoán nhất, hoặc None."""
        x1, y1, x2, y2 = bbox
        gate = max(STITCH_MIN_PX, 1.5 * ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
        best_id, best_dist = None, gate
        for tid, track in self._tracks.items():
            gap_ms = now_ms - track.get("last_ms", now_ms)
            if track["last_seen"] == self._frame or not 0 < gap_ms <= STITCH_MAX_GAP_MS:
                continue
            # Dự đoán theo vận tốc của 2 lần thấy gần nhất (px/ms).
            px, py = track["last_point"]
            vx, vy = track["velocity"]
            dist = ((point[0] - (px + vx * gap_ms)) ** 2 + (point[1] - (py + vy * gap_ms)) ** 2) ** 0.5
            if dist <= best_dist:
                best_id, best_dist = tid, dist
        return best_id

    def update(self, track_id: int, vehicle_type: str, point: list[int],
               bbox: list[int] | None = None, now_ms: int | None = None) -> dict:
        stable_id = self._alias.get(track_id)
        if stable_id is None:
            stitched = self._find_lost_track(point, bbox, now_ms) if bbox and now_ms is not None else None
            stable_id = track_id if stitched is None else stitched
            if stitched is None and track_id in self._tracks:
                # ByteTrack bắt lại ID cũ nhưng ID ổn định đó đã được nối sang xe khác.
                self._spare_id += 1
                stable_id = self._spare_id
            # Một track ổn định chỉ gắn với một ID ByteTrack: ID cũ nếu quay lại sẽ thành xe mới.
            self._alias = {raw: tid for raw, tid in self._alias.items() if tid != stable_id}
            self._alias[track_id] = stable_id
        track = self._tracks.setdefault(stable_id, {
            "age": 0, "classes": Counter(),
            "raw": deque(maxlen=self.smooth_points),
            "trajectory": deque(maxlen=TRAJECTORY_POINTS),
            "velocity": (0.0, 0.0),
        })
        if now_ms is not None and "last_ms" in track and now_ms > track["last_ms"]:
            dt = now_ms - track["last_ms"]
            track["velocity"] = ((point[0] - track["last_point"][0]) / dt, (point[1] - track["last_point"][1]) / dt)
        if now_ms is not None:
            track["last_ms"] = now_ms
        track["last_point"] = point
        track["age"] += 1
        track["last_seen"] = self._frame
        track["classes"][vehicle_type] += 1
        track["raw"].append(point)
        count = len(track["raw"])
        smoothed = [round(sum(p[0] for p in track["raw"]) / count), round(sum(p[1] for p in track["raw"]) / count)]
        track["trajectory"].append(smoothed)
        return {
            "track_id": stable_id,
            "confirmed": track["age"] >= self.min_frames,
            "vehicle_type": track["classes"].most_common(1)[0][0],
            "ground_point_xy": smoothed,
            "trajectory_xy": list(track["trajectory"]),
        }
