"""Backend tests for TrafficMonitor IoT.
Tests HTTP Range, Path Traversal security, Evidence extraction, Job states, and Event deduplication.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest
from django.conf import settings
from django.db import IntegrityError
from django.test import Client
from django.test import override_settings

from monitor.models import (
    RuleRunRecord,
    SceneConfigRecord,
    SignalTimelineRecord,
    TrackingJob,
    VideoAsset,
    ViolationEventRecord,
)
from monitor.services.droidcam_service import DroidCamManager
from monitor.services.evidence_service import create_violation_evidence
from monitor.services.video_service import get_safe_video_path


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_dashboard_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"TRAFFIC MONITOR IoT" in res.content
    assert b"mainVideo" in res.content
    assert b"overlayCanvas" in res.content


@pytest.mark.django_db
def test_scene_config_and_timeline_apis(client):
    # Create scene config
    res = client.post(
        "/api/scene-configs/",
        data=json.dumps({"source_id": "vd3.mp4", "scene_id": "scene_vd3_test", "roads": {}}),
        content_type="application/json",
    )
    assert res.status_code == 201
    assert res.json()["version"] == 1

    # Create timeline
    res = client.post(
        "/api/signal-timelines/",
        data=json.dumps({"video_id": "vd3.mp4", "timeline_id": "timeline_vd3_test", "changes": []}),
        content_type="application/json",
    )
    assert res.status_code == 201
    assert res.json()["version"] == 1



@pytest.mark.django_db
def test_video_http_range_streaming(client):
    """Test HTTP 206 Partial Content Range streaming for video seeking."""
    res = client.get("/api/videos/vd3.mp4/stream/", HTTP_RANGE="bytes=0-1023")
    assert res.status_code == 206
    assert "Content-Range" in res.headers
    assert res.headers["Content-Range"].startswith("bytes 0-1023/")
    assert res.headers["Accept-Ranges"] == "bytes"
    assert len(b"".join(res.streaming_content)) == 1024


@pytest.mark.django_db
def test_path_traversal_prevention(client):
    """Attempting path traversal must be rejected."""
    with pytest.raises((PermissionError, Exception)):
        get_safe_video_path("../../windows/system32/cmd.exe")

    # API request with forbidden path
    res = client.get("/api/videos/..%2F..%2Fwindows/stream/")
    assert res.status_code in (400, 403, 404)


@pytest.mark.django_db
def test_evidence_service_generates_full_and_crop_images():
    """Verify evidence service extracts 1 panoramic full-frame with box + 1 crop image."""
    video_path = settings.DATA_RAW_DIR / "vd3.mp4"
    if not video_path.is_file():
        pytest.skip("vd3.mp4 not present")

    full_url, crop_url = create_violation_evidence(
        video_path=video_path,
        event_id="test_evidence_event_01",
        timestamp_ms=1000,
        track_id=77,
        bbox_xyxy=[300, 200, 450, 350],
        rule_type="red_light",
    )

    assert full_url.startswith("/media/evidence/test_evidence_event_01_full.jpg")
    assert crop_url.startswith("/media/evidence/test_evidence_event_01_crop.jpg")

    # Verify physical existence on disk
    full_disk = settings.MEDIA_ROOT / "evidence" / "test_evidence_event_01_full.jpg"
    crop_disk = settings.MEDIA_ROOT / "evidence" / "test_evidence_event_01_crop.jpg"
    assert full_disk.is_file()
    assert crop_disk.is_file()
    assert full_disk.stat().st_size > 0
    assert crop_disk.stat().st_size > 0


@pytest.mark.django_db
def test_duplicate_event_prevention_constraint():
    """Verify database unique constraint strictly rejects duplicate event_id."""
    ViolationEventRecord.objects.create(
        event_id="unique_run_01_trk5_red_light",
        rule_type="red_light",
        track_id=5,
        event_timestamp_ms=5000,
        bbox_xyxy=[100, 100, 200, 200],
    )

    from django.db import transaction
    # Attempt duplicate insert inside atomic block
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ViolationEventRecord.objects.create(
                event_id="unique_run_01_trk5_red_light",
                rule_type="red_light",
                track_id=5,
                event_timestamp_ms=5033,  # Next frame
                bbox_xyxy=[105, 100, 205, 200],
            )

    # Count must remain exactly 1
    assert ViolationEventRecord.objects.filter(event_id="unique_run_01_trk5_red_light").count() == 1


@pytest.mark.django_db
def test_droidcam_mock_connection():
    """Test DroidCam manager mock stream connect, frame buffer, and status."""
    mgr = DroidCamManager.get_instance()
    res = mgr.connect("mock://droidcam")
    assert res["status"] == "connected"

    status = mgr.get_status()
    assert status["connected"] is True
    assert status["is_mock"] is True

    # Check JPEG preview
    import time
    time.sleep(0.1)
    jpeg = mgr.get_latest_jpeg()
    assert jpeg is not None
    assert len(jpeg) > 100
    mgr.stop()


@pytest.mark.django_db
def test_empty_camera_url_does_not_start_mock(client):
    response = client.post("/api/live/connect/", data=json.dumps({"url": ""}),
                           content_type="application/json")
    assert response.status_code == 400
    assert DroidCamManager.get_instance().get_status()["connected"] is False


@pytest.mark.django_db
def test_droidcam_reconnect_and_snapshot(client):
    """Test connecting, fetching snapshot, stopping, reconnecting, and verifying fresh frame."""
    mgr = DroidCamManager.get_instance()
    mgr.connect("mock://droidcam")
    import time
    time.sleep(0.1)

    # Test snapshot API
    res = client.get("/api/videos/live/snapshot/")
    assert res.status_code == 200
    assert res.headers["Cache-Control"].startswith("no-cache")
    assert len(res.content) > 100

    # Test stop and reconnect
    mgr.connect("mock://droidcam")
    time.sleep(0.1)
    res2 = client.get("/api/videos/live/snapshot/")
    assert res2.status_code == 200
    assert len(res2.content) > 100
    mgr.stop()


@pytest.mark.django_db
def test_tracking_runs_choose_complete_matching_video(client, tmp_path):
    runs_dir = tmp_path / "outputs" / "runs"
    for run_id, source, processed in (
        ("run_001", r"C:\data\vd3.mp4", 100),
        ("run_002", r"C:\data\vd3.mp4", 40),
        ("run_003", r"C:\data\vd2.mp4", 100),
    ):
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(json.dumps({
            "source": source, "source_frames": 100, "processed_frames": processed,
        }), encoding="utf-8")
        (run_dir / "tracks.jsonl").write_text("", encoding="utf-8")
    with override_settings(BASE_DIR=tmp_path):
        response = client.get("/api/tracking/runs/?source=vd3.mp4")
        assert response.status_code == 200
        runs = response.json()["runs"]
        assert [run["run_id"] for run in runs] == ["run_001", "run_002"]
        assert [run["complete"] for run in runs] == [True, False]
        rejected = client.post("/api/rules/run/", data=json.dumps({
            "tracking_run_id": "run_001", "source_id": "vd2.mp4",
        }), content_type="application/json")
        assert rejected.status_code == 400
        assert "không thuộc video" in rejected.json()["error"]
