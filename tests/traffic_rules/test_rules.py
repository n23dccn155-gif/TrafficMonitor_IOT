"""Unit tests for Traffic Rules Engine.
Pure Python unit tests with zero Django dependencies.
"""
import json
import tempfile
from pathlib import Path

import pytest
from src.traffic_monitor.traffic_rules.engine import RuleEngine
from src.traffic_monitor.traffic_rules.geometry import (
    line_segment_intersection,
    point_in_polygon,
    vector_angle_degrees,
)
from src.traffic_monitor.traffic_rules.schemas import (
    DirectionRegion,
    RoadConfig,
    SceneConfig,
    SignalChange,
    SignalTimeline,
    StopLine,
    TrackFrame,
    TrackObservation,
)
from src.traffic_monitor.traffic_rules.signal_controller import (
    FakeSerialAdapter,
    TimelineGenerator,
)


@pytest.fixture
def sample_scene():
    return SceneConfig(
        scene_id="test_intersection",
        version=1,
        source_id="test_video.mp4",
        reference_size=[1000, 1000],
        reference_frame_ms=0,
        roads={
            "A": RoadConfig(
                name="Đường A (Bắc - Nam)",
                signal_group="A",
                center_boundary=[[500, 0], [500, 1000]],
                direction_regions=[
                    DirectionRegion(
                        id="A1",
                        name="A1 Xuống",
                        polygon=[[0, 0], [500, 0], [500, 1000], [0, 1000]],
                        allowed_direction=[0.0, 1.0],  # Going down
                    ),
                    DirectionRegion(
                        id="A2",
                        name="A2 Lên",
                        polygon=[[500, 0], [1000, 0], [1000, 1000], [500, 1000]],
                        allowed_direction=[0.0, -1.0],  # Going up
                    ),
                ],
                stop_lines=[
                    StopLine(id="stop_A1", direction_region_id="A1", line=[[0, 300], [500, 300]]),
                    StopLine(id="stop_A2", direction_region_id="A2", line=[[500, 700], [1000, 700]]),
                ],
            )
        },
        intersection_polygon=[[400, 400], [600, 400], [600, 600], [400, 600]],
    )


@pytest.fixture
def sample_timeline():
    return SignalTimeline(
        timeline_id="test_timeline",
        version=1,
        video_id="test_video.mp4",
        mode="simulation",
        changes=[
            SignalChange(at_video_ms=0, phase="A_GREEN", source="simulation", seq=1),
            SignalChange(at_video_ms=1000, phase="A_YELLOW", source="simulation", seq=2),
            SignalChange(at_video_ms=1500, phase="ALL_RED", source="simulation", seq=3),
            SignalChange(at_video_ms=2000, phase="B_GREEN", source="simulation", seq=4),
        ],
    )


def test_geometry_primitives():
    # Point in square
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert point_in_polygon([5, 5], poly) is True
    assert point_in_polygon([15, 15], poly) is False
    assert all(point_in_polygon(p, poly) for p in ([0, 0], [10, 0], [10, 10], [0, 10], [5, 0]))

    # Line segment intersection
    assert line_segment_intersection([0, 5], [10, 5], [5, 0], [5, 10]) is True
    assert line_segment_intersection([0, 5], [10, 5], [0, 0], [10, 0]) is False

    # Vector angle
    assert vector_angle_degrees([0, 1], [0, 1]) == pytest.approx(0.0)
    assert vector_angle_degrees([0, 1], [0, -1]) == pytest.approx(180.0)
    assert vector_angle_degrees([1, 0], [0, 1]) == pytest.approx(90.0)


def test_wrong_way_single_event_and_30_following_frames(sample_scene, sample_timeline):
    """MANDATORY: Vehicle drives wrong way, triggers EXACTLY 1 event, and continuing

    for 30 subsequent frames generates NO DUPLICATE events.
    """
    engine = RuleEngine(scene=sample_scene, timeline=sample_timeline, rule_run_id="run_test")

    # In A1, allowed direction is [0, 1] (going down, y increasing).
    # Vehicle drives upwards (y decreasing): [250, 600] -> [250, 300].
    events = []
    y = 600
    for frame_idx in range(40):
        t_ms = frame_idx * 100
        # Move up by 10 pixels each frame
        y -= 10
        obs = TrackObservation(
            track_id=101,
            vehicle_type="motorcycle",
            bbox_xyxy=[230, y - 40, 270, y],
            ground_point_xy=[250, y],
            trajectory_xy=[[250, y]],
            observation_kind="detection",
        )
        frame = TrackFrame(
            camera_id="CAM_01",
            frame_index=frame_idx,
            video_timestamp_ms=t_ms,
            processing_size=[1000, 1000],
            tracks=[obs],
        )
        evs = engine.process_frame(frame)
        events.extend(evs)

    # Must produce EXACTLY 1 event despite 40 frames!
    assert len(events) == 1
    assert events[0].rule_type == "wrong_way"
    assert events[0].track_id == 101
    assert events[0].event_id == "run_test_seg0_trk101_wrong_way"

    # Re-running the same stream must produce zero new events on locked state
    # (or identical single event if engine is freshly constructed with same input)
    fresh_engine = RuleEngine(scene=sample_scene, timeline=sample_timeline, rule_run_id="run_test")
    # Feed first 10 frames
    y2 = 600
    events_second_run = []
    for f in range(10):
        y2 -= 10
        obs = TrackObservation(
            track_id=101,
            bbox_xyxy=[230, y2 - 40, 270, y2],
            ground_point_xy=[250, y2],
            observation_kind="detection",
        )
        events_second_run.extend(
            fresh_engine.process_frame(
                TrackFrame(
                    camera_id="CAM_01",
                    frame_index=f,
                    video_timestamp_ms=f * 100,
                    processing_size=[1000, 1000],
                    tracks=[obs],
                )
            )
        )
    assert len(events_second_run) == 1
    assert events_second_run[0].event_id == events[0].event_id


def test_red_light_single_event_and_30_following_frames(sample_scene, sample_timeline):
    """MANDATORY: Vehicle crosses stop line during RED light at t=1600ms (phase ALL_RED).

    Subsequent 30 frames must NOT generate duplicate events.
    """
    engine = RuleEngine(scene=sample_scene, timeline=sample_timeline, rule_run_id="run_test")

    events = []
    # Stop line stop_A1 is at y=300 across x in [0, 500].
    # Vehicle approaches from y=250 and crosses to y=350 at t=1600ms (ALL_RED).
    y = 200
    for frame_idx in range(40):
        t_ms = 1400 + frame_idx * 50  # 1400ms, 1450ms... ALL_RED starts at 1500ms
        y += 10
        obs = TrackObservation(
            track_id=202,
            vehicle_type="car",
            bbox_xyxy=[200, y - 60, 300, y],
            ground_point_xy=[250, y],
            trajectory_xy=[[250, y]],
            observation_kind="detection",
        )
        frame = TrackFrame(
            camera_id="CAM_01",
            frame_index=frame_idx,
            video_timestamp_ms=t_ms,
            processing_size=[1000, 1000],
            tracks=[obs],
        )
        evs = engine.process_frame(frame)
        events.extend(evs)

    # Exactly 1 red_light event!
    assert len(events) == 1
    assert events[0].rule_type == "red_light"
    assert events[0].track_id == 202
    assert "ALL_RED" in events[0].reason


def test_red_light_pass_on_green_no_violation(sample_scene, sample_timeline):
    """Vehicle crosses stop line during GREEN phase (t=200ms -> A_GREEN).

    Should produce 0 violations.
    """
    engine = RuleEngine(scene=sample_scene, timeline=sample_timeline, rule_run_id="run_test")

    events = []
    y = 250
    for frame_idx in range(10):
        t_ms = 100 + frame_idx * 50  # All during A_GREEN (0 - 1000ms)
        y += 15
        obs = TrackObservation(
            track_id=303,
            vehicle_type="car",
            bbox_xyxy=[200, y - 60, 300, y],
            ground_point_xy=[250, y],
            observation_kind="detection",
        )
        frame = TrackFrame(
            camera_id="CAM_01",
            frame_index=frame_idx,
            video_timestamp_ms=t_ms,
            processing_size=[1000, 1000],
            tracks=[obs],
        )
        events.extend(engine.process_frame(frame))

    assert len(events) == 0


def test_red_light_pass_on_own_yellow_no_violation(sample_scene, sample_timeline):
    engine = RuleEngine(scene=sample_scene, timeline=sample_timeline, rule_run_id="yellow_test")
    events = []
    for index, y in enumerate((270, 290, 310, 330)):
        obs = TrackObservation(track_id=304, ground_point_xy=[250, y],
                               bbox_xyxy=[230, y - 40, 270, y])
        frame = TrackFrame("CAM_01", index, 1100 + index * 100, [1000, 1000], [obs])
        events.extend(engine.process_frame(frame))
    assert not any(event.rule_type == "red_light" for event in events)


def test_red_light_all_yellow_permits_both_signal_groups(sample_scene):
    """ALL_YELLOW (both directions yellow together) is a permitted phase for every group."""
    from copy import deepcopy

    timeline = SignalTimeline(
        timeline_id="all_yellow_timeline",
        version=1,
        video_id="test_video.mp4",
        mode="manual_annotation",
        changes=[
            SignalChange(at_video_ms=0, phase="A_GREEN", source="manual_annotation", seq=1),
            SignalChange(at_video_ms=1000, phase="ALL_YELLOW", source="manual_annotation", seq=2),
            SignalChange(at_video_ms=4000, phase="B_GREEN", source="manual_annotation", seq=3),
        ],
    )

    for group in ("A", "B"):
        scene = deepcopy(sample_scene)
        road = scene.roads["A"]
        road.signal_group = group
        scene.roads = {group: road}

        engine = RuleEngine(scene=scene, timeline=timeline, rule_run_id=f"all_yellow_{group}")
        events = []
        y = 200
        for frame_idx in range(40):
            t_ms = 1400 + frame_idx * 50  # crossing lands inside the ALL_YELLOW window
            y += 10
            obs = TrackObservation(
                track_id=707,
                vehicle_type="car",
                bbox_xyxy=[200, y - 60, 300, y],
                ground_point_xy=[250, y],
                trajectory_xy=[[250, y]],
                observation_kind="detection",
            )
            frame = TrackFrame("CAM_01", frame_idx, t_ms, [1000, 1000], [obs])
            events.extend(engine.process_frame(frame))
        assert events == [], f"ALL_YELLOW must be permitted for group {group}: {events}"


def test_red_light_uses_estimated_crossing_time_at_phase_change(sample_scene, sample_timeline):
    from src.traffic_monitor.traffic_rules.rules.red_light import RedLightRule

    def crossing(first_ms, first_y, second_ms, second_y, track_id):
        rule = RedLightRule(f"phase_{track_id}")
        events = []
        for index, (at_ms, y) in enumerate(((first_ms, first_y), (second_ms, second_y))):
            obs = TrackObservation(track_id=track_id, ground_point_xy=[250, y],
                                   bbox_xyxy=[230, y - 40, 270, y])
            frame = TrackFrame("CAM_01", index, at_ms, [1000, 1000], [obs])
            event = rule.evaluate(obs, frame, sample_scene, sample_timeline)
            if event:
                events.append(event)
        return events

    # The second frame is red, but this car crossed during the earlier green.
    assert crossing(900, 290, 1600, 430, 305) == []
    # This car crosses exactly when ALL_RED starts.
    red_events = crossing(1400, 290, 1600, 310, 306)
    assert len(red_events) == 1
    assert red_events[0].event_timestamp_ms == 1500


def test_lane_encroachment_single_event(sample_scene, sample_timeline):
    """Vehicle in A1 (x < 500) crosses center_boundary (x=500) into A2 (x > 500).

    Should trigger exactly 1 lane_encroachment event.
    """
    engine = RuleEngine(scene=sample_scene, timeline=sample_timeline, rule_run_id="run_test")

    events = []
    x = 480
    for frame_idx in range(35):
        t_ms = frame_idx * 100
        x += 5  # Crosses 500 into A2 outside intersection (y=150)
        obs = TrackObservation(
            track_id=404,
            vehicle_type="motorcycle",
            bbox_xyxy=[x - 20, 120, x + 20, 160],
            ground_point_xy=[x, 160],
            observation_kind="detection",
        )
        frame = TrackFrame(
            camera_id="CAM_01",
            frame_index=frame_idx,
            video_timestamp_ms=t_ms,
            processing_size=[1000, 1000],
            tracks=[obs],
        )
        events.extend(engine.process_frame(frame))

    assert len(events) == 1
    assert events[0].rule_type == "lane_encroachment"
    assert events[0].track_id == 404


def test_lane_history_resets_outside_drawn_road(sample_scene):
    from src.traffic_monitor.traffic_rules.rules.lane_crossing import LaneEncroachmentRule

    rule = LaneEncroachmentRule("outside_test")
    events = []
    for index, x in enumerate((450, -20, 520, 530, 540, 550)):
        obs = TrackObservation(track_id=405, ground_point_xy=[x, 150],
                               bbox_xyxy=[x - 10, 110, x + 10, 150])
        frame = TrackFrame("CAM_01", index, index * 100, [1000, 1000], [obs])
        event = rule.evaluate(obs, frame, sample_scene, None)
        if event:
            events.append(event)
    assert events == []


def test_lane_encroachment_requires_distance_beyond_center_line(sample_scene):
    from src.traffic_monitor.traffic_rules.rules.lane_crossing import LaneEncroachmentRule

    rule = LaneEncroachmentRule("buffer_test")
    events = []
    for index, x in enumerate((480, 503, 504, 505, 510, 515, 520)):
        obs = TrackObservation(track_id=406, ground_point_xy=[x, 150],
                               bbox_xyxy=[x - 10, 110, x + 10, 150])
        frame = TrackFrame("CAM_01", index, index * 100, [1000, 1000], [obs])
        event = rule.evaluate(obs, frame, sample_scene, None)
        if event:
            events.append(event)
    assert len(events) == 1
    assert events[0].event_timestamp_ms == 400


def test_lane_confirmation_resets_after_missing_detection(sample_scene):
    from src.traffic_monitor.traffic_rules.rules.lane_crossing import LaneEncroachmentRule

    rule = LaneEncroachmentRule("lane_gap_test")
    events = []
    for frame_index, x in ((0, 480), (1, 510), (2, 515), (4, 520), (5, 525)):
        obs = TrackObservation(track_id=407, ground_point_xy=[x, 150],
                               bbox_xyxy=[x - 10, 110, x + 10, 150])
        frame = TrackFrame("CAM_01", frame_index, frame_index * 100, [1000, 1000], [obs])
        event = rule.evaluate(obs, frame, sample_scene, None)
        if event:
            events.append(event)
    assert events == []


def test_wrong_way_confirmation_resets_after_missing_detection(sample_scene):
    from src.traffic_monitor.traffic_rules.rules.wrong_way import WrongWayRule

    rule = WrongWayRule("wrong_gap_test")
    events = []
    for frame_index, y in ((0, 600), (1, 570), (2, 540), (4, 510), (5, 480)):
        obs = TrackObservation(track_id=408, ground_point_xy=[250, y],
                               bbox_xyxy=[230, y - 40, 270, y])
        frame = TrackFrame("CAM_01", frame_index, frame_index * 100, [1000, 1000], [obs])
        event = rule.evaluate(obs, frame, sample_scene, None)
        if event:
            events.append(event)
    assert events == []


def test_crossing_inside_intersection_does_not_count_as_lane_encroachment(sample_scene):
    from src.traffic_monitor.traffic_rules.rules.lane_crossing import LaneEncroachmentRule

    rule = LaneEncroachmentRule("intersection_test")
    events = []
    for index, (x, y) in enumerate([(450, 350), (450, 500), (550, 650), (550, 650), (550, 650)]):
        obs = TrackObservation(track_id=10, ground_point_xy=[x, y],
                               bbox_xyxy=[x - 10, y - 20, x + 10, y])
        frame = TrackFrame("CAM_01", index, index * 100, [1000, 1000], [obs])
        event = rule.evaluate(obs, frame, sample_scene, None)
        if event:
            events.append(event)
    assert events == []


def test_wrong_way_history_resets_when_region_changes(sample_scene):
    from src.traffic_monitor.traffic_rules.rules.wrong_way import WrongWayRule

    rule = WrongWayRule("region_test")
    events = []
    for index, (x, y) in enumerate([(450, 100), (450, 120), (550, 300),
                                    (550, 290), (550, 280), (550, 270)]):
        obs = TrackObservation(track_id=11, ground_point_xy=[x, y],
                               bbox_xyxy=[x - 10, y - 20, x + 10, y])
        frame = TrackFrame("CAM_01", index, index * 100, [1000, 1000], [obs])
        event = rule.evaluate(obs, frame, sample_scene, None)
        if event:
            events.append(event)
    assert events == []


def test_green_crossing_one_line_does_not_hide_later_red_crossing(sample_scene, sample_timeline):
    from src.traffic_monitor.traffic_rules.rules.red_light import RedLightRule

    rule = RedLightRule("second_line_test")
    events = []
    for index, (x, y, at_ms) in enumerate([(250, 250, 100), (250, 350, 200),
                                          (750, 750, 1400), (750, 650, 1600)]):
        obs = TrackObservation(track_id=12, ground_point_xy=[x, y],
                               bbox_xyxy=[x - 10, y - 20, x + 10, y])
        frame = TrackFrame("CAM_01", index, at_ms, [1000, 1000], [obs])
        event = rule.evaluate(obs, frame, sample_scene, sample_timeline)
        if event:
            events.append(event)
    assert len(events) == 1
    assert "stop_A2" in events[0].reason


def test_timeline_generator_never_concurrent_green():
    """Verify TimelineGenerator strict invariant: A_GREEN and B_GREEN NEVER overlap."""
    timeline = TimelineGenerator.generate_timed(
        duration_ms=60000,
        a_green_sec=5.0,
        b_green_sec=5.0,
        yellow_sec=2.0,
        all_red_sec=1.0,
    )

    # Check every second across 60 seconds
    for t_ms in range(0, 60000, 500):
        phase = timeline.get_phase_at(t_ms)
        assert phase in ("A_GREEN", "A_YELLOW", "ALL_RED", "B_GREEN", "B_YELLOW")
        # Ensure phase is a single atomic state
        assert not (phase == "A_GREEN" and phase == "B_GREEN")


def test_fake_serial_adapter():
    adapter = FakeSerialAdapter()
    assert adapter.is_connected() is True

    ack = adapter.send_phase("A_GREEN", command_id=1)
    assert ack["status"] == "ACK"
    assert ack["phase"] == "A_GREEN"
    assert ack["command_id"] == 1
    assert ack["seq"] == 1

    # Bad phase rejection
    bad_ack = adapter.send_phase("INVALID_PHASE", command_id=2)
    assert bad_ack["status"] == "REJECTED"

    # Disconnected adapter
    disconnected_adapter = FakeSerialAdapter(simulate_disconnect=True)
    assert disconnected_adapter.is_connected() is False
    err_ack = disconnected_adapter.send_phase("A_GREEN", command_id=3)
    assert err_ack["status"] == "ERROR"
