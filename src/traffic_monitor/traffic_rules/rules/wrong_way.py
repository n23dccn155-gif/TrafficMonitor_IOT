"""Rule: Đi ngược chiều (wrong_way).
Detects vehicles driving against the configured direction_region allowed_direction.
"""
from __future__ import annotations

import math
from typing import Optional

from ..geometry import point_in_polygon, scale_bbox, scale_point, vector_angle_degrees
from ..schemas import SceneConfig, SignalTimeline, TrackFrame, TrackObservation, ViolationEvent
from .base import BaseRule, RuleState


class WrongWayRule(BaseRule):
    def __init__(
        self,
        rule_run_id: str,
        min_displacement_px: float = 20.0,
        min_consecutive_frames: int = 3,
        angle_threshold_deg: float = 120.0,
    ):
        super().__init__("wrong_way", rule_run_id)
        self.min_displacement_px = min_displacement_px
        self.min_consecutive_frames = min_consecutive_frames
        self.angle_threshold_deg = angle_threshold_deg

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

        # Only use confirmed detections for reliable violation proof
        if observation.observation_kind != "detection":
            return None

        # Scale ground point and bbox to scene reference size
        pt = scale_point(observation.ground_point_xy, frame.processing_size, scene.reference_size)
        bbox = scale_bbox(observation.bbox_xyxy, frame.processing_size, scene.reference_size)

        # Ignore if vehicle is currently inside the central intersection area
        if scene.intersection_polygon and point_in_polygon(pt, scene.intersection_polygon):
            self._track_history.pop(key, None)
            return None

        # Find which direction region vehicle is in
        matched_region = None
        for road in scene.roads.values():
            for region in road.direction_regions:
                if point_in_polygon(pt, region.polygon):
                    matched_region = region
                    break
            if matched_region:
                break

        if not matched_region:
            self._track_history.pop(key, None)
            return None

        if self._track_history.get(key, {}).get("region_id") != matched_region.id:
            self._track_history.pop(key, None)
        elif frame.frame_index != self._track_history[key].get("last_frame_index", frame.frame_index - 1) + 1:
            # A missing detection breaks a consecutive confirmation sequence.
            self._track_history.pop(key, None)

        # Maintain track history
        hist = self._track_history.setdefault(
            key,
            {
                "region_id": matched_region.id,
                "points": [],
                "first_violation_ms": frame.video_timestamp_ms,
                "first_bbox": bbox,
                "consecutive_violation_count": 0,
                "last_frame_index": frame.frame_index,
            },
        )
        hist["last_frame_index"] = frame.frame_index
        hist["points"].append((pt[0], pt[1], frame.video_timestamp_ms))
        if len(hist["points"]) > 20:
            hist["points"].pop(0)

        # Need at least 2 distinct points separated by time
        if len(hist["points"]) < 2:
            return None

        # Calculate displacement vector from earliest point in region to current point
        start_pt = hist["points"][0]
        dx = pt[0] - start_pt[0]
        dy = pt[1] - start_pt[1]
        dist = math.hypot(dx, dy)

        if dist < self.min_displacement_px:
            hist["consecutive_violation_count"] = 0
            return None

        # Compare movement vector with allowed direction
        angle = vector_angle_degrees((dx, dy), matched_region.allowed_direction)

        if angle >= self.angle_threshold_deg:
            hist["consecutive_violation_count"] += 1
            if hist["consecutive_violation_count"] == 1:
                hist["first_violation_ms"] = frame.video_timestamp_ms
                hist["first_bbox"] = bbox

            if hist["consecutive_violation_count"] >= self.min_consecutive_frames:
                # Trigger confirmed violation once and lock!
                self.lock_track(frame.segment_id, observation.track_id)
                event_id = ViolationEvent.generate_id(
                    self.rule_run_id, frame.segment_id, observation.track_id, self.rule_name
                )
                reason = (
                    f"Xe ID {observation.track_id} ({observation.vehicle_type}) di chuyển ngược chiều tại {matched_region.name} "
                    f"(lệch {angle:.1f}°, quãng đường {dist:.1f}px trong {hist['consecutive_violation_count']} frames)"
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
