"""Rule: Lấn qua vạch phân cách hai chiều (lane_encroachment).
Detects vehicles encroaching across the center_boundary between two opposing direction regions.
"""
from __future__ import annotations

from typing import Optional

from ..geometry import point_in_polygon, point_to_segment_distance, scale_bbox, scale_point
from ..schemas import SceneConfig, SignalTimeline, TrackFrame, TrackObservation, ViolationEvent
from .base import BaseRule, RuleState


class LaneEncroachmentRule(BaseRule):
    def __init__(
        self,
        rule_run_id: str,
        buffer_distance_px: float = 8.0,
        min_consecutive_frames: int = 3,
    ):
        super().__init__("lane_encroachment", rule_run_id)
        self.buffer_distance_px = buffer_distance_px
        self.min_consecutive_frames = min_consecutive_frames

    def evaluate(
        self,
        observation: TrackObservation,
        frame: TrackFrame,
        scene: SceneConfig,
        timeline: Optional[SignalTimeline],
    ) -> Optional[ViolationEvent]:
        key = (frame.segment_id, observation.track_id)
        if self.is_locked(frame.segment_id, observation.track_id):
            return None

        if observation.observation_kind != "detection":
            return None

        pt = scale_point(observation.ground_point_xy, frame.processing_size, scene.reference_size)
        bbox = scale_bbox(observation.bbox_xyxy, frame.processing_size, scene.reference_size)

        # Ignore if vehicle is in the intersection zone
        if scene.intersection_polygon and point_in_polygon(pt, scene.intersection_polygon):
            self._track_history.pop(key, None)
            return None

        # Find which region the point is currently in
        current_region = None
        current_road_key = None
        for r_key, road in scene.roads.items():
            for region in road.direction_regions:
                if point_in_polygon(pt, region.polygon):
                    current_region = region
                    current_road_key = r_key
                    break
            if current_region:
                break

        if current_region is None:
            self._track_history.pop(key, None)
            return None

        hist = self._track_history.get(key)
        if hist is not None and frame.frame_index != hist["last_frame_index"] + 1:
            self._track_history.pop(key, None)
            hist = None
        if hist is None or hist["road_key"] != current_road_key:
            self._track_history[key] = {
                "origin_region_id": current_region.id,
                "road_key": current_road_key,
                "consecutive_violation_count": 0,
                "first_violation_ms": frame.video_timestamp_ms,
                "first_bbox": bbox,
                "last_frame_index": frame.frame_index,
            }
            return None

        hist["last_frame_index"] = frame.frame_index
        if current_region.id == hist["origin_region_id"]:
            hist["consecutive_violation_count"] = 0
            return None

        road = scene.roads[current_road_key]
        if not road.center_boundary or len(road.center_boundary) < 2:
            return None

        dist_to_boundary = min(
            point_to_segment_distance(pt, road.center_boundary[i], road.center_boundary[i + 1])
            for i in range(len(road.center_boundary) - 1)
        )

        if dist_to_boundary >= self.buffer_distance_px:
            hist["consecutive_violation_count"] += 1
            if hist["consecutive_violation_count"] == 1:
                hist["first_violation_ms"] = frame.video_timestamp_ms
                hist["first_bbox"] = bbox

            if hist["consecutive_violation_count"] >= self.min_consecutive_frames:
                self.lock_track(frame.segment_id, observation.track_id)
                event_id = ViolationEvent.generate_id(
                    self.rule_run_id, frame.segment_id, observation.track_id, self.rule_name
                )
                reason = (
                    f"Xe ID {observation.track_id} ({observation.vehicle_type}) lấn qua vạch phân cách giữa hai chiều "
                    f"của {road.name} (từ vùng {hist['origin_region_id']} sang vùng đối diện, khoảng cách {dist_to_boundary:.1f}px)"
                )
                return ViolationEvent(
                    event_id=event_id,
                    tracking_run_id=self.rule_run_id,
                    rule_run_id=self.rule_run_id,
                    segment_id=frame.segment_id,
                    rule_type=self.rule_name,
                    track_id=observation.track_id,
                    vehicle_type=observation.vehicle_type,
                    event_timestamp_ms=hist["first_violation_ms"],
                    bbox_xyxy=hist["first_bbox"],
                    scene_config_version=scene.version,
                    signal_source=timeline.mode if timeline else "none",
                    reason=reason,
                )
        else:
            hist["consecutive_violation_count"] = 0

        return None
