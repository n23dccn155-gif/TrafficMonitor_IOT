import cv2
import numpy as np

from monitor.services.techgar_motion_service import TechGarMotionAdapter
from src.traffic_monitor.traffic_rules.engine import RuleEngine
from src.traffic_monitor.traffic_rules.schemas import SceneConfig, SignalChange, SignalTimeline, TrackFrame


def test_techgar_motion_keeps_id_for_moving_small_vehicle():
    adapter = TechGarMotionAdapter()
    seen = []
    for index in range(34):
        frame = np.full((360, 640, 3), 180, dtype=np.uint8)
        if index >= 8:
            x = 80 + (index - 8) * 5
            cv2.rectangle(frame, (x, 125), (x + 28, 165), (20, 20, 20), -1)
        tracks, size = adapter.process(frame, index * 50, index)
        if index >= 14:
            seen.extend(track["track_id"] for track in tracks
                        if abs(track["ground_point_xy"][1] - 165) < 18)
    assert size == [640, 360]
    assert len(seen) >= 5
    assert all(track_id > 0 for track_id in seen)
    assert len(set(seen)) == 1


def test_techgar_motion_can_feed_red_line_rule():
    adapter = TechGarMotionAdapter()
    scene = SceneConfig.from_dict({
        "scene_id": "motion_test", "source_id": "live", "reference_size": [640, 360],
        "roads": {"A": {
            "name": "A", "signal_group": "A", "center_boundary": [],
            "direction_regions": [{
                "id": "A1", "name": "A1", "polygon": [[0, 0], [300, 0], [300, 360], [0, 360]],
                "allowed_direction": [0, 1],
            }],
            "stop_lines": [{"id": "stop_A1", "direction_region_id": "A1",
                            "line": [[0, 190], [300, 190]]}],
        }},
    })
    timeline = SignalTimeline(
        timeline_id="red", version=1, video_id="live", mode="live",
        changes=[SignalChange(at_video_ms=0, phase="B_GREEN")],
    )
    engine = RuleEngine(scene, timeline, rule_run_id="motion_red_test")
    events = []
    for index in range(40):
        frame = np.full((360, 640, 3), 180, dtype=np.uint8)
        if index >= 8:
            y = 70 + (index - 8) * 5
            cv2.rectangle(frame, (100, y), (128, y + 40), (20, 20, 20), -1)
        tracks, size = adapter.process(frame, index * 50, index)
        data = {
            "camera_id": "CAM_01", "frame_index": index,
            "video_timestamp_ms": index * 50, "processing_size": size,
            "tracks": tracks,
        }
        events.extend(engine.process_frame(TrackFrame.from_dict(data)))
    red_events = [event for event in events if event.rule_type == "red_light"]
    assert len(red_events) == 1
    assert red_events[0].track_id > 0
