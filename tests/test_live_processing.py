import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import numpy as np
from django.test import override_settings

from monitor.models import RuleRunRecord, SceneConfigRecord, ViolationEventRecord
from monitor.services.arduino_signal_service import ArduinoSignalService
from monitor.services.droidcam_service import DroidCamManager
from monitor.services.live_signal_timer import LiveSignalTimer
from monitor.services.live_processing_service import LiveProcessingManager, is_usable_vehicle_box
from src.traffic_monitor.traffic_rules.schemas import SignalTimeline


def test_camera_reuses_live_reader_and_rejects_stale_frame():
    camera = DroidCamManager.get_instance()
    try:
        camera.connect("mock://droidcam")
        previous_stop = camera._stop_event
        previous_thread = camera._thread
        camera.connect("mock://droidcam")
        assert camera._stop_event is previous_stop
        assert camera._thread is previous_thread
        camera._stop_event.set()
        camera._thread.join(timeout=1)
        with camera._lock:
            camera.latest_timestamp_ms = int(time.time() * 1000) - 3000
        assert camera.get_latest_jpeg(max_age_ms=2000) is None
        assert camera.get_status()["connected"] is False
    finally:
        camera.stop()


def test_snapshot_fallback_keeps_advancing_frames():
    class ClosedCapture:
        def set(self, *args):
            pass

        def isOpened(self):
            return False

        def release(self):
            pass

    camera = DroidCamManager()
    frames_fetched = [0]

    def fetch_snapshot(_candidate):
        frames_fetched[0] += 1
        return np.full((24, 32, 3), frames_fetched[0] % 255, dtype=np.uint8)

    try:
        with patch("monitor.services.droidcam_service.cv2.VideoCapture", return_value=ClosedCapture()), \
                patch.object(camera, "_snapshot_candidates", return_value=["http://camera/frame.jpg"]), \
                patch.object(camera, "_fetch_snapshot_candidate", side_effect=fetch_snapshot):
            camera.connect("http://camera/video")
            with camera._lock:
                first = int(camera.latest_frame[0, 0, 0])
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and frames_fetched[0] < 3:
                time.sleep(0.02)
            with camera._lock:
                later = int(camera.latest_frame[0, 0, 0])
            assert frames_fetched[0] >= 3
            assert later != first
            assert camera.get_status()["connected"] is True
    finally:
        camera.stop()


def test_full_frame_car_detection_is_not_used_for_violations():
    assert is_usable_vehicle_box([1, 1, 639, 479], 640, 480) is False
    assert is_usable_vehicle_box([646, 0, 1275, 610], 1280, 709) is False
    assert is_usable_vehicle_box([100, 100, 180, 150], 640, 480) is True


def test_live_manual_phase_uses_change_time_not_last_processed_frame():
    manager = LiveProcessingManager()
    manager.status = "RUNNING"
    manager._start_monotonic_ms = int(time.monotonic() * 1000) - 5000
    manager.latest_tracks = {"video_timestamp_ms": 100}
    manager.timeline = SignalTimeline(timeline_id="live_test", version=1, video_id="live", mode="live", changes=[])
    manager.signal_timer = LiveSignalTimer(manager.timeline, {"mode": "manual", "phase": "A_GREEN"})
    assert manager.set_signal({"mode": "manual", "phase": "B_GREEN"}) is True
    assert manager.timeline.changes[-1].phase == "B_GREEN"
    assert manager.timeline.changes[-1].at_video_ms >= 4900
    manager.set_signal({"mode": "manual", "phase": "ALL_YELLOW"})
    assert manager.timeline.changes[-1].phase == "ALL_YELLOW"
    with pytest.raises(ValueError):
        manager.set_signal({"mode": "manual", "phase": "UNKNOWN"})


@pytest.mark.django_db
def test_live_start_is_accepted_without_waiting_for_model(client):
    camera = DroidCamManager.get_instance()
    camera.connect("mock://droidcam")
    scene = SceneConfigRecord.objects.create(
        scene_id="scene_live", source_id="live", version=1,
        data_json={"scene_id": "scene_live", "source_id": "live", "reference_size": [640, 480], "roads": {}},
    )
    manager = LiveProcessingManager.get_instance()
    try:
        with patch.object(LiveProcessingManager, "_worker") as worker, patch.object(LiveProcessingManager, "prepare"):
            response = client.post(
                "/api/live/processing/",
                data=json.dumps({"scene_config_id": scene.scene_id, "signal": {"mode": "manual", "phase": "A_GREEN"}}),
                content_type="application/json",
            )
            assert response.status_code == 202
            assert response.json()["status"] == "STARTING"
            assert response.json()["run_id"].startswith("live_")
            worker.assert_called_once()
            status = client.get("/api/live/processing/").json()
            assert status["phase"] == "A_GREEN"
            phase = client.post(
                "/api/live/phase/", data=json.dumps({"mode": "manual", "phase": "B_GREEN"}),
                content_type="application/json",
            )
            assert phase.status_code == 200
            assert manager.timeline.changes[-1].phase == "B_GREEN"
    finally:
        manager.stop()
        camera.stop()


@pytest.mark.django_db
def test_events_can_be_filtered_by_live_run(client):
    first = RuleRunRecord.objects.create(rule_run_id="live_first")
    second = RuleRunRecord.objects.create(rule_run_id="live_second")
    for run, event_id in ((first, "first"), (second, "second")):
        ViolationEventRecord.objects.create(
            event_id=event_id, rule_run=run, rule_type="wrong_way",
            track_id=1, event_timestamp_ms=100, bbox_xyxy=[0, 0, 1, 1],
        )
    response = client.get("/api/events/?run_id=live_first")
    assert response.status_code == 200
    assert [event["event_id"] for event in response.json()["events"]] == ["first"]


@pytest.mark.django_db(transaction=True)
def test_live_worker_processes_shared_camera_frames(client):
    camera = DroidCamManager.get_instance()
    camera.connect("mock://droidcam")
    scene = SceneConfigRecord.objects.create(
        scene_id="scene_live_worker", source_id="live", version=1,
        data_json={"scene_id": "scene_live_worker", "source_id": "live", "reference_size": [640, 480], "roads": {}},
    )
    manager = LiveProcessingManager.get_instance()
    manager.stop()
    previous_model = manager._model
    previous_error = manager._model_error
    previous_ready = manager._model_ready.is_set()
    class OversizedBoxes(list):
        id = np.array([1])

    oversized = SimpleNamespace(
        id=np.array([1]), xyxy=np.array([[0, 0, 640, 480]]),
        cls=np.array([2]), conf=np.array([0.9]),
    )
    fake_model = SimpleNamespace(
        predict=lambda *args, **kwargs: [],
        track=lambda *args, **kwargs: [SimpleNamespace(
            boxes=OversizedBoxes([oversized]), names={2: "car"},
        )],
        predictor=None,
    )
    try:
        manager._model = (fake_model, "cpu")
        manager._model_error = ""
        manager._model_ready.set()
        with patch.object(manager, "prepare"):
            response = client.post(
                "/api/live/processing/",
                data=json.dumps({"scene_config_id": scene.scene_id, "signal": {"mode": "manual", "phase": "A_GREEN"}}),
                content_type="application/json",
            )
            assert response.status_code == 202
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                status = client.get("/api/live/processing/").json()
                if status["status"] == "RUNNING":
                    break
                time.sleep(0.05)
            assert status["status"] == "RUNNING", status
            assert status["frame"]["processing_size"] == [640, 480]
            assert status["frame"]["tracks"] == []
            assert status["frame"]["detection_stats"]["rejected_boxes"] == 1
            assert RuleRunRecord.objects.filter(rule_run_id=status["run_id"]).exists()
    finally:
        manager.stop()
        camera.stop()
        manager._model = previous_model
        manager._model_error = previous_error
        if not previous_ready:
            manager._model_ready.clear()


@pytest.mark.django_db(transaction=True)
def test_live_reports_yolo_unavailable_without_motion_fallback():
    camera = DroidCamManager.get_instance()
    camera.connect("mock://droidcam")
    scene = SceneConfigRecord.objects.create(
        scene_id="scene_motion_without_yolo", source_id="live", version=1,
        data_json={"scene_id": "scene_motion_without_yolo", "source_id": "live",
                   "reference_size": [640, 480], "roads": {}},
    )
    manager = LiveProcessingManager.get_instance()
    manager.stop()
    previous_model = manager._model
    previous_error = manager._model_error
    previous_ready = manager._model_ready.is_set()
    try:
        manager._model = None
        manager._model_error = "YOLO unavailable in test"
        manager._model_ready.set()
        with patch.object(manager, "prepare"):
            run_id = manager.start(scene, {"mode": "manual", "phase": "A_GREEN"})["run_id"]
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                status = manager.get_status()
                if status["status"] == "RUNNING" and status["frame"]:
                    break
                time.sleep(0.05)
            assert status["status"] == "RUNNING", status
            assert status["run_id"] == run_id
            assert status["frame"]["detection_stats"]["raw_boxes"] == 0
            assert status["detector_warning"] == "YOLO unavailable in test"
            assert status["frame"]["tracks"] == []
            assert status["frame"]["yolo_detections"] == []
            assert status["frame"]["detection_stats"]["motion_tracks"] == 0
    finally:
        manager.stop()
        camera.stop()
        manager._model = previous_model
        manager._model_error = previous_error
        if not previous_ready:
            manager._model_ready.clear()


@pytest.mark.django_db(transaction=True)
def test_live_untracked_yolo_detection_is_displayed_but_not_scored():
    class UntrackedBoxes(list):
        id = None

    box = SimpleNamespace(
        id=None, xyxy=np.array([[100, 100, 180, 160]]),
        cls=np.array([2]), conf=np.array([0.8]),
    )
    fake_model = SimpleNamespace(
        track=lambda *args, **kwargs: [SimpleNamespace(
            boxes=UntrackedBoxes([box]), names={2: "car"},
        )], predictor=None,
    )
    scene = SceneConfigRecord.objects.create(
        scene_id="scene_untracked_yolo", source_id="live", version=1,
        data_json={"scene_id": "scene_untracked_yolo", "source_id": "live",
                   "reference_size": [640, 480], "roads": {}},
    )
    camera = DroidCamManager.get_instance()
    manager = LiveProcessingManager.get_instance()
    camera.connect("mock://droidcam")
    manager.stop()
    previous_model = manager._model
    previous_ready = manager._model_ready.is_set()
    try:
        manager._model = (fake_model, "cpu")
        manager._model_ready.set()
        with patch.object(manager, "prepare"):
            run_id = manager.start(scene, {"mode": "manual", "phase": "A_GREEN"})["run_id"]
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                status = manager.get_status()
                if status["status"] == "RUNNING" and status["frame"]:
                    break
                time.sleep(0.05)
            frame = status["frame"]
            assert frame["tracks"] == []
            assert frame["yolo_detections"] == [{
                "vehicle_type": "car", "class_confidence": 0.8,
                "bbox_xyxy": [100, 100, 180, 160],
            }]
            assert frame["detection_stats"]["yolo_detections"] == 1
            assert not ViolationEventRecord.objects.filter(rule_run_id=run_id).exists()
    finally:
        manager.stop()
        camera.stop()
        manager._model = previous_model
        if not previous_ready:
            manager._model_ready.clear()


@pytest.mark.django_db(transaction=True)
def test_live_vehicle_crossing_red_line_saves_current_frame_evidence(tmp_path):
    class FakeValue:
        def __init__(self, value):
            self.value = value

        def item(self):
            return self.value

        def tolist(self):
            return self.value

    class FakeBoxes(list):
        id = FakeValue(42)

    class FakeModel:
        predictor = None
        calls = 0

        def track(self, *args, **kwargs):
            y = (210, 230, 250, 270, 290)[min(self.calls, 4)]
            self.calls += 1
            box = SimpleNamespace(
                id=FakeValue(42), xyxy=[FakeValue([100, y - 40, 150, y])],
                cls=FakeValue(2), conf=FakeValue(0.9),
            )
            return [SimpleNamespace(boxes=FakeBoxes([box]), names={2: "car"})]

    scene = SceneConfigRecord.objects.create(
        scene_id="scene_live_red_crossing", source_id="live", version=1,
        data_json={
            "scene_id": "scene_live_red_crossing", "source_id": "live",
            "reference_size": [640, 480],
            "roads": {"A": {
                "name": "A", "signal_group": "A", "center_boundary": [],
                "direction_regions": [{
                    "id": "A1", "name": "A1", "polygon": [[0, 0], [300, 0], [300, 480], [0, 480]],
                    "allowed_direction": [0, 1],
                }],
                "stop_lines": [{"id": "stop_A1", "direction_region_id": "A1",
                                "line": [[0, 260], [300, 260]]}],
            }},
        },
    )
    camera = DroidCamManager.get_instance()
    manager = LiveProcessingManager.get_instance()
    camera.connect("mock://droidcam")
    manager.stop()
    previous_model = manager._model
    previous_error = manager._model_error
    previous_ready = manager._model_ready.is_set()
    fake_model = FakeModel()
    try:
        manager._model = (fake_model, "cpu")
        manager._model_error = None
        manager._model_ready.set()
        # Lỗi được tính theo timer: worker không được hỏi pha từ Arduino.
        with patch.object(manager, "prepare"), override_settings(MEDIA_ROOT=tmp_path),                 patch.object(ArduinoSignalService, "status", side_effect=AssertionError("Arduino polled")):
            run_id = manager.start(scene, {"mode": "manual", "phase": "B_GREEN"})["run_id"]
            deadline = time.monotonic() + 4
            event = None
            while time.monotonic() < deadline:
                event = ViolationEventRecord.objects.filter(
                    rule_run_id=run_id, rule_type="red_light",
                ).first()
                if event:
                    break
                time.sleep(0.05)
            assert event is not None, manager.get_status()
            assert event.track_id == 42
            # Track được xét từ frame thứ 3 và điểm chân là trung bình 3 frame,
            # nên lần cắt vạch y=260 rơi vào frame 5 (box đáy y=290).
            assert event.bbox_xyxy == [100, 250, 150, 290]
            assert (tmp_path / "evidence" / f"{event.event_id}_full.jpg").is_file()
            assert (tmp_path / "evidence" / f"{event.event_id}_crop.jpg").is_file()
            assert fake_model.calls >= 4
            assert manager.get_status()["event_count"] == 1
    finally:
        manager.stop()
        camera.stop()
        manager._model = previous_model
        manager._model_error = previous_error
        if not previous_ready:
            manager._model_ready.clear()


def test_signal_worker_makes_arduino_follow_timer():
    class FakeArduino:
        def __init__(self):
            self.commands = []

        def is_connected(self):
            return True

        def command(self, text):
            self.commands.append(text)
            if len(self.commands) == 2:
                raise ConnectionError("USB unplugged")

    manager = LiveProcessingManager()
    manager.status = "RUNNING"
    manager._start_monotonic_ms = int(time.monotonic() * 1000)
    manager.timeline = SignalTimeline(timeline_id="t", version=1, video_id="live", mode="live", changes=[])
    manager.signal_timer = LiveSignalTimer(manager.timeline, {"mode": "manual", "phase": "A_GREEN"})
    arduino = FakeArduino()
    with patch.object(ArduinoSignalService, "get_instance", return_value=arduino):
        thread = threading.Thread(target=manager._signal_worker, args=(manager._stop,), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 2
            while not arduino.commands and time.monotonic() < deadline:
                time.sleep(0.01)
            manager.set_signal({"mode": "manual", "phase": "ALL_YELLOW"})
            while len(arduino.commands) < 3 and time.monotonic() < deadline:
                time.sleep(0.01)
        finally:
            manager._stop.set()
            thread.join(timeout=1)
    # A failed send is retried; the rule phase never depends on the Arduino.
    assert arduino.commands[:3] == ["MANUAL A_GREEN", "MANUAL ALL_YELLOW", "MANUAL ALL_YELLOW"]
    assert manager.signal_timer.phase == "ALL_YELLOW"
    assert manager.signal_warning == ""


@pytest.mark.django_db
def test_live_signal_apis_validate_and_block_arduino_override(client):
    manager = LiveProcessingManager.get_instance()
    bad = client.post("/api/live/phase/", data=json.dumps({"mode": "timed", "a_green": 999}),
                      content_type="application/json")
    assert bad.status_code == 400
    with patch.object(LiveProcessingManager, "is_running", return_value=True):
        blocked = client.post("/api/arduino/signal/", data=json.dumps({"action": "manual", "phase": "A_GREEN"}),
                              content_type="application/json")
    assert blocked.status_code == 409
    assert manager.set_signal({"mode": "manual", "phase": "A_GREEN"}) is False  # not running


@pytest.mark.django_db(transaction=True)
def test_both_yellow_stops_yolo_and_resume_runs_it_during_warm_up():
    class CountingModel:
        predictor = None
        calls = 0

        def track(self, *args, **kwargs):
            self.calls += 1
            return [SimpleNamespace(boxes=None, names={})]

    scene = SceneConfigRecord.objects.create(
        scene_id="scene_live_pause", source_id="live", version=1,
        data_json={"scene_id": "scene_live_pause", "source_id": "live", "reference_size": [640, 480], "roads": {}},
    )
    camera = DroidCamManager.get_instance()
    manager = LiveProcessingManager.get_instance()
    camera.connect("mock://droidcam")
    manager.stop()
    previous = (manager._model, manager._model_error, manager._model_ready.is_set())
    model = CountingModel()
    try:
        manager._model = (model, "cpu")
        manager._model_error = ""
        manager._model_ready.set()
        with patch.object(manager, "prepare"):
            manager.start(scene, {"mode": "manual", "phase": "ALL_YELLOW"})
            deadline = time.monotonic() + 3
            while manager.get_status()["status"] != "RUNNING" and time.monotonic() < deadline:
                time.sleep(0.02)
            time.sleep(0.3)
            assert manager.get_status()["signal"]["paused"] is True
            assert model.calls == 0
            manager.set_signal({"mode": "manual", "phase": "B_GREEN"})
            while model.calls == 0 and time.monotonic() < deadline:
                time.sleep(0.02)
            status = manager.get_status()
            assert model.calls > 0  # YOLO restarts while the lights are still yellow
            assert status["signal"]["phase"] == "ALL_YELLOW" and status["signal"]["warming_up"] is True
    finally:
        manager.stop()
        camera.stop()
        manager._model, manager._model_error = previous[0], previous[1]
        if not previous[2]:
            manager._model_ready.clear()


def test_arduino_api_rejects_manual_both_red(client):
    response = client.post("/api/arduino/signal/", data=json.dumps({"action": "manual", "phase": "ALL_RED"}),
                           content_type="application/json")
    assert response.status_code == 400
