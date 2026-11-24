from monitor.services.input_optimizer import (
    TrackFilter, point_in_roi, roi_rect, scene_polygons,
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
