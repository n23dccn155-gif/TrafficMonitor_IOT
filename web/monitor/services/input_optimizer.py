"""Scene ROI geometry and optional track smoothing helpers."""
from __future__ import annotations

from collections import Counter, deque

from src.traffic_monitor.traffic_rules.geometry import point_in_polygon, scale_point

ROI_MARGIN = 0.08       # lề thêm quanh ROI, theo tỉ lệ kích thước ROI
MIN_ROI_SIDE = 32
MIN_TRACK_FRAMES = 3    # track phải xuất hiện ít nhất N frame mới được xét luật
SMOOTH_POINTS = 3       # số điểm chân dùng để tính trung bình trượt
TRAJECTORY_POINTS = 60
FORGET_AFTER_FRAMES = 150


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


def point_in_roi(point, polygons) -> bool:
    return not polygons or any(point_in_polygon(point, polygon) for polygon in polygons)


class TrackFilter:
    """Giữ trạng thái từng track ID để quyết định track nào đủ tin cậy cho Rule Engine."""

    def __init__(self, min_frames: int = MIN_TRACK_FRAMES, smooth_points: int = SMOOTH_POINTS):
        self.min_frames = min_frames
        self.smooth_points = smooth_points
        self._frame = 0
        self._tracks: dict[int, dict] = {}

    def clear(self):
        self._tracks.clear()

    def next_frame(self):
        """Gọi mỗi frame; quên các track đã mất lâu để bộ nhớ không tăng mãi."""
        self._frame += 1
        stale = [tid for tid, t in self._tracks.items() if self._frame - t["last_seen"] > FORGET_AFTER_FRAMES]
        for tid in stale:
            del self._tracks[tid]

    def update(self, track_id: int, vehicle_type: str, point: list[int]) -> dict:
        track = self._tracks.setdefault(track_id, {
            "age": 0, "classes": Counter(),
            "raw": deque(maxlen=self.smooth_points),
            "trajectory": deque(maxlen=TRAJECTORY_POINTS),
        })
        track["age"] += 1
        track["last_seen"] = self._frame
        track["classes"][vehicle_type] += 1
        track["raw"].append(point)
        count = len(track["raw"])
        smoothed = [round(sum(p[0] for p in track["raw"]) / count), round(sum(p[1] for p in track["raw"]) / count)]
        track["trajectory"].append(smoothed)
        return {
            "confirmed": track["age"] >= self.min_frames,
            "vehicle_type": track["classes"].most_common(1)[0][0],
            "ground_point_xy": smoothed,
            "trajectory_xy": list(track["trajectory"]),
        }
