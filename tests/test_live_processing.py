import json
import time
from unittest.mock import patch

import pytest
import numpy as np
from django.test import override_settings

from monitor.models import RuleRunRecord, SceneConfigRecord, ViolationEventRecord
from monitor.services.droidcam_service import DroidCamManager
from monitor.services.live_processing_service import LiveProcessingManager
from src.traffic_monitor.traffic_rules.schemas import SignalChange, SignalTimeline


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


def test_live_phase_uses_change_time_not_last_processed_frame():
    manager = LiveProcessingManager()
    manager.status = "RUNNING"
    manager._start_monotonic_ms = int(time.monotonic() * 1000) - 5000
    manager.latest_tracks = {"video_timestamp_ms": 100}
    manager.timeline = SignalTimeline(
        timeline_id="live_test", version=1, video_id="live", mode="live",
        changes=[SignalChange(at_video_ms=0, phase="A_GREEN")],
    )
    manager.set_phase("B_GREEN")
    assert manager.timeline.changes[-1].at_video_ms >= 4900
    manager.set_phase("ALL_YELLOW", source="arduino")
    assert manager.timeline.changes[-1].phase == "ALL_YELLOW"
    manager.set_phase("UNKNOWN", source="arduino")
    assert manager.timeline.changes[-1].phase == "UNKNOWN"


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
                data=json.dumps({"scene_config_id": scene.scene_id, "phase": "A_GREEN"}),
                content_type="application/json",
            )
            assert response.status_code == 202
            assert response.json()["status"] == "STARTING"
            assert response.json()["run_id"].startswith("live_")
            worker.assert_called_once()
            status = client.get("/api/live/processing/").json()
            assert status["phase"] == "A_GREEN"
            phase = client.post(
                "/api/live/phase/", data=json.dumps({"phase": "B_GREEN"}),
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
def test_live_worker_uses_techgar_ids(client):
    camera = DroidCamManager.get_instance()
    camera.connect("mock://droidcam")
    scene = SceneConfigRecord.objects.create(
        scene_id="scene_techgar_worker", source_id="live", version=1,
        data_json={"scene_id": "scene_techgar_worker", "source_id": "live",
                   "reference_size": [640, 480], "roads": {}},
    )
    manager = LiveProcessingManager.get_instance()
    manager.stop()

    class FakeTechGar:
        def process(self, frame, timestamp_ms, frame_index):
            return ([{"track_id": 42, "track_source": "techgar",
                      "vehicle_type": "vehicle", "bbox_xyxy": [100, 100, 150, 140],
                      "ground_point_xy": [125, 140], "trajectory_xy": [[125, 140]],
                      "observation_kind": "detection"}], [640, 480])
        def reset(self):
            pass

    try:
        with patch("monitor.services.live_processing_service.TechGarMotionAdapter",
                   return_value=FakeTechGar()):
            run_id = manager.start(scene, "A_GREEN")["run_id"]
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                status = manager.get_status()
                if status["status"] == "RUNNING" and status["frame"]:
                    break
                time.sleep(0.05)
            assert status["status"] == "RUNNING", status
            assert status["run_id"] == run_id
            assert status["frame"]["tracks"][0]["track_id"] == 42
            assert status["frame"]["tracks"][0]["track_source"] == "techgar"
            assert status["frame"]["detection_stats"]["motion_tracks"] == 1
            assert RuleRunRecord.objects.filter(rule_run_id=run_id).exists()
    finally:
        manager.stop()
        camera.stop()


@pytest.mark.django_db(transaction=True)
def test_live_techgar_crossing_red_line_saves_evidence(tmp_path):
    scene = SceneConfigRecord.objects.create(
        scene_id="scene_techgar_red", source_id="live", version=1,
        data_json={
            "scene_id": "scene_techgar_red", "source_id": "live",
            "reference_size": [640, 480],
            "roads": {"A": {
                "name": "A", "signal_group": "A", "center_boundary": [],
                "direction_regions": [{
                    "id": "A1", "name": "A1",
                    "polygon": [[0, 0], [300, 0], [300, 480], [0, 480]],
                    "allowed_direction": [0, 1],
                }],
                "stop_lines": [{"id": "stop_A1", "direction_region_id": "A1",
                                "line": [[0, 260], [300, 260]]}],
            }},
        },
    )
    class MovingTechGar:
        def __init__(self):
            self.calls = 0
        def reset(self):
            pass
        def process(self, frame, timestamp_ms, frame_index):
            y = 210 + 20 * min(self.calls, 5)
            self.calls += 1
            return ([{"track_id": 42, "track_source": "techgar",
                      "vehicle_type": "vehicle", "bbox_xyxy": [100, y - 40, 150, y],
                      "ground_point_xy": [125, y],
                      "trajectory_xy": [[125, y - 20], [125, y]],
                      "observation_kind": "detection"}], [640, 480])

    camera = DroidCamManager.get_instance()
    manager = LiveProcessingManager.get_instance()
    camera.connect("mock://droidcam")
    manager.stop()
    fake = MovingTechGar()
    try:
        with override_settings(MEDIA_ROOT=tmp_path), patch(
            "monitor.services.live_processing_service.TechGarMotionAdapter",
            return_value=fake,
        ):
            run_id = manager.start(scene, "B_GREEN")["run_id"]
            deadline = time.monotonic() + 5
            event = None
            while time.monotonic() < deadline:
                event = ViolationEventRecord.objects.filter(
                    rule_run_id=run_id, rule_type="red_light").first()
                if event:
                    break
                time.sleep(0.05)
            assert event is not None, manager.get_status()
            assert event.track_id == 42
            assert fake.calls >= 4
            assert (tmp_path / "evidence" / f"{event.event_id}_full.jpg").is_file()
            assert (tmp_path / "evidence" / f"{event.event_id}_crop.jpg").is_file()
    finally:
        manager.stop()
        camera.stop()
