"""Data schemas for Traffic Rules and Event Generation.
Pure Python, zero external dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TrackObservation:
    track_id: int
    vehicle_type: str = "vehicle"
    class_confidence: float = 1.0
    bbox_xyxy: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    ground_point_xy: List[int] = field(default_factory=lambda: [0, 0])
    trajectory_xy: List[List[int]] = field(default_factory=list)
    track_quality: str = "confirmed"
    observation_kind: str = "detection"

    @classmethod
    def from_dict(cls, data: dict) -> TrackObservation:
        # Compute ground point if missing: mid-point of bottom edge
        bbox = data.get("bbox_xyxy", [0, 0, 0, 0])
        ground_point = data.get("ground_point_xy")
        if not ground_point and len(bbox) == 4:
            ground_point = [int((bbox[0] + bbox[2]) / 2), int(bbox[3])]
        return cls(
            track_id=int(data["track_id"]),
            vehicle_type=str(data.get("vehicle_type", "vehicle")),
            class_confidence=float(data.get("class_confidence", 1.0)),
            bbox_xyxy=[int(v) for v in bbox],
            ground_point_xy=[int(v) for v in ground_point] if ground_point else [0, 0],
            trajectory_xy=[[int(p[0]), int(p[1])] for p in data.get("trajectory_xy", [])],
            track_quality=str(data.get("track_quality", "confirmed")),
            observation_kind=str(data.get("observation_kind", "detection")),
        )

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "vehicle_type": self.vehicle_type,
            "class_confidence": round(self.class_confidence, 4),
            "bbox_xyxy": self.bbox_xyxy,
            "ground_point_xy": self.ground_point_xy,
            "trajectory_xy": self.trajectory_xy,
            "track_quality": self.track_quality,
            "observation_kind": self.observation_kind,
        }


@dataclass
class TrackFrame:
    camera_id: str
    frame_index: int
    video_timestamp_ms: int
    processing_size: List[int]
    tracks: List[TrackObservation]
    segment_id: str = "seg0"

    @classmethod
    def from_dict(cls, data: dict) -> TrackFrame:
        tracks = [TrackObservation.from_dict(t) for t in data.get("tracks", [])]
        return cls(
            camera_id=str(data.get("camera_id", "CAM_01")),
            frame_index=int(data.get("frame_index", 0)),
            video_timestamp_ms=int(data.get("video_timestamp_ms", 0)),
            processing_size=[int(v) for v in data.get("processing_size", [1280, 720])],
            tracks=tracks,
            segment_id=str(data.get("segment_id", "seg0")),
        )

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "segment_id": self.segment_id,
            "frame_index": self.frame_index,
            "video_timestamp_ms": self.video_timestamp_ms,
            "processing_size": self.processing_size,
            "tracks": [t.to_dict() for t in self.tracks],
        }


@dataclass
class DirectionRegion:
    id: str
    name: str
    polygon: List[List[int]]
    allowed_direction: List[float]  # [dx, dy] normalized or direction vector

    @classmethod
    def from_dict(cls, data: dict) -> DirectionRegion:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            polygon=[[int(p[0]), int(p[1])] for p in data["polygon"]],
            allowed_direction=[float(v) for v in data["allowed_direction"]],
        )


@dataclass
class StopLine:
    id: str
    direction_region_id: str
    line: List[List[int]]  # [[x1, y1], [x2, y2]]

    @classmethod
    def from_dict(cls, data: dict) -> StopLine:
        return cls(
            id=str(data["id"]),
            direction_region_id=str(data.get("direction_region_id", "")),
            line=[[int(p[0]), int(p[1])] for p in data["line"]],
        )


@dataclass
class RoadConfig:
    name: str
    signal_group: str  # "A" or "B"
    center_boundary: List[List[int]]  # [[x1, y1], [x2, y2]]
    direction_regions: List[DirectionRegion]
    stop_lines: List[StopLine]

    @classmethod
    def from_dict(cls, data: dict) -> RoadConfig:
        return cls(
            name=str(data.get("name", "")),
            signal_group=str(data.get("signal_group", "A")),
            center_boundary=[[int(p[0]), int(p[1])] for p in data.get("center_boundary", [])],
            direction_regions=[DirectionRegion.from_dict(r) for r in data.get("direction_regions", [])],
            stop_lines=[StopLine.from_dict(s) for s in data.get("stop_lines", [])],
        )


@dataclass
class SceneConfig:
    scene_id: str
    version: int
    source_id: str
    reference_size: List[int]
    reference_frame_ms: int
    roads: Dict[str, RoadConfig]
    intersection_polygon: List[List[int]]

    @classmethod
    def from_dict(cls, data: dict) -> SceneConfig:
        roads = {}
        for road_key, r_data in data.get("roads", {}).items():
            roads[road_key] = RoadConfig.from_dict(r_data)
        return cls(
            scene_id=str(data.get("scene_id", "default_scene")),
            version=int(data.get("version", 1)),
            source_id=str(data.get("source_id", "")),
            reference_size=[int(v) for v in data.get("reference_size", [1920, 1080])],
            reference_frame_ms=int(data.get("reference_frame_ms", 0)),
            roads=roads,
            intersection_polygon=[[int(p[0]), int(p[1])] for p in data.get("intersection_polygon", [])],
        )


@dataclass
class SignalChange:
    at_video_ms: int
    phase: str  # "A_GREEN", "A_YELLOW", "ALL_RED", "B_GREEN", "B_YELLOW"
    source: str = "simulation"
    seq: int = 1

    @classmethod
    def from_dict(cls, data: dict) -> SignalChange:
        return cls(
            at_video_ms=int(data["at_video_ms"]),
            phase=str(data["phase"]),
            source=str(data.get("source", "simulation")),
            seq=int(data.get("seq", 1)),
        )

    def to_dict(self) -> dict:
        return {
            "at_video_ms": self.at_video_ms,
            "phase": self.phase,
            "source": self.source,
            "seq": self.seq,
        }


@dataclass
class SignalTimeline:
    timeline_id: str
    version: int
    video_id: str
    mode: str = "simulation"
    changes: List[SignalChange] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> SignalTimeline:
        return cls(
            timeline_id=str(data.get("timeline_id", "default_timeline")),
            version=int(data.get("version", 1)),
            video_id=str(data.get("video_id", "")),
            mode=str(data.get("mode", "simulation")),
            changes=[SignalChange.from_dict(c) for c in data.get("changes", [])],
        )

    def to_dict(self) -> dict:
        return {
            "timeline_id": self.timeline_id,
            "version": self.version,
            "video_id": self.video_id,
            "mode": self.mode,
            "changes": [c.to_dict() for c in self.changes],
        }

    def get_phase_at(self, timestamp_ms: int) -> str:
        if not self.changes:
            return "UNKNOWN"
        # Find latest change at or before timestamp_ms
        sorted_changes = sorted(self.changes, key=lambda c: c.at_video_ms)
        current_phase = "UNKNOWN"
        for change in sorted_changes:
            if change.at_video_ms <= timestamp_ms:
                current_phase = change.phase
            else:
                break
        return current_phase


@dataclass
class ViolationEvent:
    event_id: str
    tracking_run_id: str
    rule_run_id: str
    segment_id: str
    rule_type: str  # "wrong_way", "lane_encroachment", "red_light"
    track_id: int
    vehicle_type: str
    event_timestamp_ms: int
    bbox_xyxy: List[int]
    scene_config_version: int
    signal_source: str
    reason: str
    full_image_path: str = ""
    crop_image_path: str = ""
    review_status: str = "pending"
    review_note: str = ""

    @classmethod
    def generate_id(cls, rule_run_id: str, segment_id: str, track_id: int, rule_type: str) -> str:
        """Deterministic stable event ID formula."""
        return f"{rule_run_id}_{segment_id}_trk{track_id}_{rule_type}"

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "tracking_run_id": self.tracking_run_id,
            "rule_run_id": self.rule_run_id,
            "segment_id": self.segment_id,
            "rule_type": self.rule_type,
            "track_id": self.track_id,
            "vehicle_type": self.vehicle_type,
            "event_timestamp_ms": self.event_timestamp_ms,
            "bbox_xyxy": self.bbox_xyxy,
            "scene_config_version": self.scene_config_version,
            "signal_source": self.signal_source,
            "reason": self.reason,
            "full_image_path": self.full_image_path,
            "crop_image_path": self.crop_image_path,
            "review_status": self.review_status,
            "review_note": self.review_note,
        }
