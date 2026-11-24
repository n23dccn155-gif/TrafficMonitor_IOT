"""Adapt TechGAR's camera-local motion tracks to TrafficMonitor observations."""
from __future__ import annotations

import cv2

from src.traffic_monitor.techgar_motion.motion_tracker import MotionVehicleTracker
from src.traffic_monitor.techgar_motion.vehicle_tracker import TrackStatus


class TechGarMotionAdapter:
    def __init__(self, max_width: int = 960):
        self.max_width = max_width
        self.tracker = MotionVehicleTracker(
            min_visible_count=3,
            history_len=60,
            min_area=150,
            min_width=10,
            min_height=12,
            max_distance=95,
            min_confirm_displacement=4,
            motion_threshold=20,
            motion_min_pixels=45,
            motion_min_ratio=0.05,
            enable_multiscale_motion=True,
            reject_cast_shadows=True,
            max_bbox_width_ratio=0.35,
            max_bbox_height_ratio=0.45,
            max_bbox_area_ratio=0.15,
        )
        self.size = None
        self.frames_seen = 0

    def reset(self):
        self.__init__(self.max_width)

    def process(self, source_frame, timestamp_ms: int, frame_index: int) -> tuple[list[dict], list[int]]:
        source_height, source_width = source_frame.shape[:2]
        width = min(self.max_width, source_width)
        height = max(2, round(source_height * width / source_width))
        frame = cv2.resize(source_frame, (width, height)) if width != source_width else source_frame
        if self.size is not None and self.size != [width, height]:
            self.reset()
        self.size = [width, height]
        self.tracker.process_frame(frame, timestamp_s=timestamp_ms / 1000, source_frame_idx=frame_index)
        self.frames_seen += 1
        tracks = []
        for track in self.tracker.observable_tracks.values():
            if track.status not in (TrackStatus.CONFIRMED, TrackStatus.LOST):
                continue
            x, y, box_width, box_height = track.bbox
            box = [int(x), int(y), int(x + box_width), int(y + box_height)]
            if (box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height):
                continue
            point = [int(track.cx), int(track.cy)]
            observation_kind = getattr(track, "observation_kind", "detection")
            tracks.append({
                "track_id": int(track.track_id),
                "track_source": "techgar",
                "vehicle_type": "vehicle",
                "class_confidence": 0.0,
                "bbox_xyxy": box,
                "ground_point_xy": point,
                "trajectory_xy": [[int(px), int(py)] for px, py in track.history],
                "observation_kind": observation_kind,
                "track_quality": track.status.value,
            })
        return tracks, self.size
