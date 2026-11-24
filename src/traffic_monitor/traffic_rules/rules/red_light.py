"""Rule: Vượt đèn đỏ (red_light).
Detects vehicles crossing the stop line when their road's signal group is RED.
"""
from __future__ import annotations

from typing import Optional

from ..geometry import point_in_polygon, scale_bbox, scale_point, segment_intersection_fraction
from ..schemas import SceneConfig, SignalTimeline, TrackFrame, TrackObservation, ViolationEvent
from .base import BaseRule, RuleState


class RedLightRule(BaseRule):
    def __init__(self, rule_run_id: str):
        super().__init__("red_light", rule_run_id)

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

        if not timeline:
            return None

        pt = scale_point(observation.ground_point_xy, frame.processing_size, scene.reference_size)
        bbox = scale_bbox(observation.bbox_xyxy, frame.processing_size, scene.reference_size)

        hist = self._track_history.setdefault(
            key,
            {
                "prev_pt": None,
                "prev_ms": None,
                "passed_on_permitted_phase": set(),
            },
        )

        prev_pt = hist["prev_pt"]
        prev_ms = hist["prev_ms"]
        hist["prev_pt"] = pt
        hist["prev_ms"] = frame.video_timestamp_ms

        if prev_pt is None:
            return None

        # Check each road's stop lines (supports 2 or more points polyline)
        for road_key, road in scene.roads.items():
            for stop_line in road.stop_lines:
                if len(stop_line.line) < 2:
                    continue
                if stop_line.id in hist["passed_on_permitted_phase"]:
                    continue

                # Check if movement from prev_pt to pt intersects ANY segment of the stop line
                crossing_fraction = None
                for i in range(len(stop_line.line) - 1):
                    s1, s2 = stop_line.line[i], stop_line.line[i + 1]
                    crossing_fraction = segment_intersection_fraction(prev_pt, pt, s1, s2)
                    if crossing_fraction is not None:
                        break

                if crossing_fraction is not None:
                    # Check that vehicle is moving forward in the entry direction of the stop line's region
                    region = next((r for r in road.direction_regions if r.id == stop_line.direction_region_id), None)
                    if not region or not point_in_polygon(prev_pt, region.polygon):
                        continue
                    if region.allowed_direction:
                        move_dx = pt[0] - prev_pt[0]
                        move_dy = pt[1] - prev_pt[1]
                        dot = move_dx * region.allowed_direction[0] + move_dy * region.allowed_direction[1]
                        if dot <= 0:
                            # Moving backwards across stop line is not an intersection-entering red light violation
                            continue

                    crossing_ms = round(prev_ms + crossing_fraction * (frame.video_timestamp_ms - prev_ms))
                    current_phase = timeline.get_phase_at(crossing_ms)

                    if current_phase == "UNKNOWN":
                        # Insufficient evidence due to missing signal log
                        return None

                    # Yellow is a separate phase; crossing on one's own yellow
                    # must not be reported as a red-light violation.
                    # ALL_YELLOW means both directions show yellow, so either group may pass.
                    if current_phase in {f"{road.signal_group}_GREEN", f"{road.signal_group}_YELLOW", "ALL_YELLOW"}:
                        hist["passed_on_permitted_phase"].add(stop_line.id)
                        return None
                    else:
                        # Crossed stop line while this road's signal is red.
                        self.lock_track(frame.segment_id, observation.track_id)
                        event_id = ViolationEvent.generate_id(
                            self.rule_run_id, frame.segment_id, observation.track_id, self.rule_name
                        )
                        reason = (
                            f"Xe ID {observation.track_id} ({observation.vehicle_type}) cắt qua vạch dừng {stop_line.id} "
                            f"của Tuyến {road.signal_group} khi tín hiệu đang {current_phase} tại mốc {crossing_ms}ms"
                        )
                        return ViolationEvent(
                            event_id=event_id,
                            tracking_run_id=self.rule_run_id,
                            rule_run_id=self.rule_run_id,
                            segment_id=frame.segment_id,
                            rule_type=self.rule_name,
                            track_id=observation.track_id,
                            vehicle_type=observation.vehicle_type,
                            event_timestamp_ms=crossing_ms,
                            bbox_xyxy=bbox,
                            scene_config_version=scene.version,
                            signal_source=timeline.mode,
                            reason=reason,
                        )

        return None
