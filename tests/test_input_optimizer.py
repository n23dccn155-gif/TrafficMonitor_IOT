from monitor.services.input_optimizer import (
    TrackFilter, box_to_frame, point_in_roi, roi_rect, scene_polygons, yolo_input_size,
)
from src.traffic_monitor.traffic_rules.schemas import SceneConfig


def _scene(intersection=None):
    return SceneConfig.from_dict({
        "reference_size": [1000, 500],
        "roads": {"A": {"signal_group": "A", "direction_regions": [{
            "id": "A1", "polygon": [[400, 100], [600, 100], [600, 400], [400, 400]],
            "allowed_direction": [0, 1],
        }], "stop_lines": []}},
        "intersection_polygon": intersection or [],
    })


def test_scene_polygons_scale_reference_to_frame():
    polygons = scene_polygons(_scene(), [500, 250])
    assert polygons == [[[200, 50], [300, 50], [300, 200], [200, 200]]]


def test_roi_rect_adds_margin_and_clamps_to_frame():
    assert roi_rect([[[0, 0], [100, 0], [100, 50]]], [100, 50]) == (0, 0, 100, 50)
    assert roi_rect([[[200, 50], [300, 50], [300, 200]]], [500, 250], margin=0.1) == (190, 35, 310, 215)


def test_roi_rect_falls_back_to_full_frame():
    assert roi_rect([], [640, 480]) == (0, 0, 640, 480)
    assert roi_rect([[[10, 10], [20, 10], [20, 20]]], [640, 480]) == (0, 0, 640, 480)


def test_yolo_input_size_downscales_long_side_only():
    assert yolo_input_size(1920, 1080) == (960, 540)
    assert yolo_input_size(600, 1200) == (480, 960)
    assert yolo_input_size(400, 300) == (400, 300)


def test_box_to_frame_restores_scale_and_offset():
    # ROI 200x100 tại (100, 50) được thu còn 100x50.
    assert box_to_frame([10, 10, 20, 30], (100, 50), (100, 50, 300, 150)) == [120, 70, 140, 110]


def test_point_in_roi():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert point_in_roi([5, 5], [square])
    assert not point_in_roi([50, 5], [square])
    assert point_in_roi([50, 5], [])


def test_track_filter_confirms_after_min_frames_and_smooths():
    tracks = TrackFilter(min_frames=3, smooth_points=3)
    states = []
    for y, cls in ((0, "car"), (30, "truck"), (60, "car"), (90, "car")):
        tracks.next_frame()
        states.append(tracks.update(7, cls, [10, y]))
    assert [s["confirmed"] for s in states] == [False, False, True, True]
    assert states[1]["ground_point_xy"] == [10, 15]
    assert states[3]["ground_point_xy"] == [10, 60]
    assert states[3]["vehicle_type"] == "car"
    assert len(states[3]["trajectory_xy"]) == 4


def test_track_filter_spike_is_damped():
    tracks = TrackFilter(min_frames=1, smooth_points=3)
    for y in (100, 100, 100):
        tracks.next_frame()
        tracks.update(1, "car", [0, y])
    tracks.next_frame()
    assert tracks.update(1, "car", [0, 160])["ground_point_xy"] == [0, 120]


def test_track_filter_forgets_lost_tracks():
    tracks = TrackFilter()
    tracks.next_frame()
    tracks.update(1, "car", [0, 0])
    for _ in range(200):
        tracks.next_frame()
    assert tracks.update(1, "car", [0, 0])["confirmed"] is False


def test_track_filter_stitches_new_bytetrack_id_near_lost_track():
    tracks = TrackFilter(min_frames=3, smooth_points=1)
    for frame, y in enumerate((100, 110, 120)):
        tracks.next_frame()
        state = tracks.update(5, "car", [50, y], [30, y - 20, 70, y], frame * 100)
    assert state["track_id"] == 5 and state["confirmed"]
    tracks.next_frame()  # ByteTrack loses the car for one frame
    tracks.next_frame()
    state = tracks.update(9, "car", [50, 150], [30, 130, 70, 150], 500)
    assert state["track_id"] == 5
    assert state["confirmed"] is True  # keeps its age: no new 3-frame wait
    assert state["trajectory_xy"][-1] == [50, 150]
    tracks.next_frame()
    assert tracks.update(9, "car", [50, 160], [30, 140, 70, 160], 600)["track_id"] == 5


def test_track_filter_does_not_stitch_far_active_or_old_tracks():
    tracks = TrackFilter(min_frames=1, smooth_points=1)
    tracks.next_frame()
    tracks.update(1, "car", [100, 100], [80, 80, 120, 100], 0)
    tracks.next_frame()
    # Far from the predicted position: a different vehicle.
    assert tracks.update(2, "car", [400, 400], [380, 380, 420, 400], 100)["track_id"] == 2
    # Track 2 is visible in this frame, so a new ID next to it is not merged into it.
    assert tracks.update(3, "car", [405, 400], [385, 380, 425, 400], 100)["track_id"] == 3
    tracks.next_frame()
    # Track 1 has been gone longer than the stitch window.
    assert tracks.update(4, "car", [100, 100], [80, 80, 120, 100], 2000)["track_id"] == 4


def test_red_light_is_caught_when_bytetrack_switches_id_at_stop_line():
    """The car is lost just before the stop line and returns past it with a new ID."""
    from src.traffic_monitor.traffic_rules.engine import RuleEngine
    from src.traffic_monitor.traffic_rules.schemas import SceneConfig, SignalChange, SignalTimeline, TrackFrame

    scene = SceneConfig.from_dict({
        "scene_id": "s", "source_id": "live", "reference_size": [640, 480],
        "roads": {"A": {
            "name": "A", "signal_group": "A", "center_boundary": [],
            "direction_regions": [{"id": "A1", "name": "A1", "allowed_direction": [0, 1],
                                   "polygon": [[0, 0], [300, 0], [300, 480], [0, 480]]}],
            "stop_lines": [{"id": "stop_A1", "direction_region_id": "A1", "line": [[0, 260], [300, 260]]}],
        }},
    })
    timeline = SignalTimeline(timeline_id="t", version=1, video_id="live", mode="live",
                              changes=[SignalChange(at_video_ms=0, phase="B_GREEN")])
    engine = RuleEngine(scene, timeline, rule_run_id="r")
    tracks = TrackFilter(min_frames=3, smooth_points=1)
    events = []
    for frame, (raw_id, y) in enumerate(((7, 200), (7, 220), (7, 240), (None, 0), (12, 290))):
        tracks.next_frame()
        if raw_id is None:
            continue
        state = tracks.update(raw_id, "car", [125, y], [100, y - 40, 150, y], frame * 100)
        if not state["confirmed"]:
            continue
        events += engine.process_frame(TrackFrame.from_dict({
            "camera_id": "c", "frame_index": frame, "segment_id": "seg0",
            "video_timestamp_ms": frame * 100, "processing_size": [640, 480],
            "tracks": [{"track_id": state["track_id"], "vehicle_type": "car", "class_confidence": 0.9,
                        "bbox_xyxy": [100, y - 40, 150, y], "ground_point_xy": state["ground_point_xy"],
                        "observation_kind": "detection"}],
        }))
    assert [(e.rule_type, e.track_id) for e in events] == [("red_light", 7)]


def test_track_filter_old_bytetrack_id_returning_gets_its_own_stable_id():
    tracks = TrackFilter(min_frames=1, smooth_points=1)
    tracks.next_frame()
    tracks.update(5, "car", [100, 100], [80, 80, 120, 100], 0)
    tracks.next_frame()
    assert tracks.update(9, "car", [100, 105], [80, 85, 120, 105], 100)["track_id"] == 5
    # ByteTrack recovers raw ID 5 far away, while stable 5 is still the car seen as raw 9.
    assert tracks.update(5, "car", [500, 400], [480, 380, 520, 400], 100)["track_id"] not in (5, 9)
    tracks.next_frame()
    assert tracks.update(9, "car", [100, 110], [80, 90, 120, 110], 200)["track_id"] == 5
