"""API and UI Views for TrafficMonitor IoT.
Implements the contract defined in docs/WEB_API_CONTRACT.md.
"""
from __future__ import annotations

import json
import ntpath
import os
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from src.traffic_monitor.traffic_rules.engine import RuleEngine
from src.traffic_monitor.traffic_rules.schemas import SceneConfig, SignalTimeline

from .models import (
    RuleRunRecord,
    SceneConfigRecord,
    SignalTimelineRecord,
    TrackingJob,
    VideoAsset,
    ViolationEventRecord,
)
from .services.droidcam_service import DroidCamManager
from .services.arduino_signal_service import ArduinoSignalService, PHASES
from .services.evidence_service import create_violation_evidence
from .services.job_service import JobManager
from .services.live_processing_service import LiveProcessingManager
from .services.track_service import get_windowed_tracks, list_tracking_runs
from .services.video_service import (
    extract_snapshot_jpeg,
    get_safe_video_path,
    list_raw_videos,
    stream_video_with_range,
)


def index_view(request):
    """Main surveillance monitoring dashboard."""
    return render(request, "dashboard.html")


# --- VIDEO APIS ---

def video_list_api(request):
    videos = list_raw_videos()
    return JsonResponse({"videos": videos})


@csrf_exempt
def video_upload_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    file_obj = request.FILES.get("file")
    if not file_obj:
        return JsonResponse({"error": "No file uploaded"}, status=400)
    if not file_obj.name.lower().endswith(".mp4"):
        return JsonResponse({"error": "Only .mp4 files are accepted"}, status=400)

    # Safe destination path
    clean_filename = os.path.basename(file_obj.name)
    dest_path = settings.DATA_RAW_DIR / clean_filename

    with open(dest_path, "wb+") as destination:
        for chunk in file_obj.chunks():
            destination.write(chunk)

    return JsonResponse({"status": "success", "filename": clean_filename})


def video_stream_api(request, filename: str):
    return stream_video_with_range(request, filename)


def video_snapshot_api(request, filename: str):
    at_ms = int(request.GET.get("at_ms", 0))
    jpeg_bytes = extract_snapshot_jpeg(filename, at_ms=at_ms)
    if not jpeg_bytes:
        return HttpResponse("Unable to extract snapshot", status=404)
    response = HttpResponse(jpeg_bytes, content_type="image/jpeg")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


# --- TRACKING JOBS APIS ---

@csrf_exempt
def tracking_jobs_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        source = data.get("source", "vd3.mp4")
        algo = str(data.get("algorithm", "techgar"))
        width = int(data.get("width", 1280))
        tile_imgsz = int(data.get("tile_imgsz", 640))

        try:
            job = JobManager.start_job(source_name=source, algorithm=algo, width=width, tile_imgsz=tile_imgsz)
            return JsonResponse(job.to_dict(), status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    # GET: List recent jobs
    jobs = [j.to_dict() for j in TrackingJob.objects.order_by("-created_at")[:20]]
    return JsonResponse({"jobs": jobs})


def tracking_job_detail_api(request, job_id: str):
    try:
        job = TrackingJob.objects.get(job_id=job_id)
        return JsonResponse(job.to_dict())
    except TrackingJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)


def track_window_api(request, run_id: str):
    from_ms = int(request.GET.get("from_ms", 0))
    to_ms = int(request.GET.get("to_ms", 5000))
    result = get_windowed_tracks(run_id, from_ms=from_ms, to_ms=to_ms)
    return JsonResponse(result)


def tracking_runs_api(request):
    return JsonResponse({"runs": list_tracking_runs(request.GET.get("source", ""))})


# --- SCENE CONFIG APIS ---

@csrf_exempt
def scene_configs_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        source_id = data.get("source_id", "default")
        scene_id = data.get("scene_id", f"scene_{source_id}")

        # Auto-increment version
        latest = SceneConfigRecord.objects.filter(scene_id=scene_id).order_by("-version").first()
        version = (latest.version + 1) if latest else 1

        rec = SceneConfigRecord.objects.create(
            scene_id=scene_id,
            version=version,
            source_id=source_id,
            data_json=data,
        )
        return JsonResponse(rec.to_dict(), status=201)

    # GET: List configs
    source_id = request.GET.get("source_id")
    qs = SceneConfigRecord.objects.all()
    if source_id:
        qs = qs.filter(source_id=source_id)
    configs = [c.to_dict() for c in qs.order_by("-created_at")]
    if not configs and source_id in (None, "vd3.mp4"):
        fixture_file = settings.BASE_DIR / "web" / "fixtures" / "sample_scene_config.json"
        if fixture_file.is_file():
            try:
                with open(fixture_file, "r", encoding="utf-8") as f:
                    configs = [json.load(f)]
            except Exception:
                pass
    return JsonResponse({"scene_configs": configs})


# --- SIGNAL TIMELINE APIS ---

@csrf_exempt
def signal_timelines_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        video_id = data.get("video_id", "default")
        timeline_id = data.get("timeline_id", f"timeline_{video_id}")
        mode = data.get("mode", "simulation")

        latest = SignalTimelineRecord.objects.filter(timeline_id=timeline_id).order_by("-version").first()
        version = (latest.version + 1) if latest else 1

        rec = SignalTimelineRecord.objects.create(
            timeline_id=timeline_id,
            version=version,
            video_id=video_id,
            mode=mode,
            data_json=data,
        )
        return JsonResponse(rec.to_dict(), status=201)

    video_id = request.GET.get("video_id")
    qs = SignalTimelineRecord.objects.all()
    if video_id:
        qs = qs.filter(video_id=video_id)
    timelines = [t.to_dict() for t in qs.order_by("-created_at")]
    return JsonResponse({"timelines": timelines})


@csrf_exempt
def arduino_signal_api(request):
    """Local USB control. The response always comes from the Uno, not a web timer."""
    if request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}:
        return JsonResponse({"error": "Arduino control is local only"}, status=403)
    origin = request.META.get("HTTP_ORIGIN")
    if origin and origin.rstrip("/") != f"{request.scheme}://{request.get_host()}":
        return JsonResponse({"error": "Cross-origin Arduino control is forbidden"}, status=403)
    if request.method == "POST" and request.content_type != "application/json":
        return JsonResponse({"error": "JSON required"}, status=415)
    service = ArduinoSignalService.get_instance()
    try:
        if request.method == "GET":
            result = service.status()
            if not result.get("connected"):
                result["ports"] = service.available_ports()
        elif request.method == "POST":
            data = json.loads(request.body)
            if not isinstance(data, dict):
                raise ValueError("JSON object required")
            action = data.get("action")
            if action == "connect":
                result = service.connect(data.get("port"))
            elif action == "disconnect":
                result = service.disconnect()
            elif action == "auto":
                values = []
                for name, lower, upper in (
                    ("a_green", 3, 120), ("a_yellow", 1, 10),
                    ("b_green", 3, 120), ("b_yellow", 1, 10),
                ):
                    value = data.get(name)
                    if type(value) is not int or not lower <= value <= upper:
                        raise ValueError(f"{name} must be between {lower} and {upper}")
                    values.append(value)
                result = service.command("AUTO " + " ".join(map(str, values)))
            elif action == "manual":
                phase = data.get("phase")
                if phase not in PHASES:
                    raise ValueError("Invalid phase")
                result = service.command(f"MANUAL {phase}")
            else:
                raise ValueError("Invalid action")
        else:
            return JsonResponse({"error": "GET or POST required"}, status=405)
        if result.get("connected") and result.get("phase"):
            LiveProcessingManager.get_instance().set_phase(result["phase"], source="arduino")
        elif request.method == "POST" and data.get("action") == "disconnect":
            LiveProcessingManager.get_instance().set_phase("UNKNOWN")
        return JsonResponse(result)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except (ConnectionError, OSError, ImportError) as exc:
        LiveProcessingManager.get_instance().set_phase("UNKNOWN")
        return JsonResponse({"error": str(exc), "connected": False}, status=503)


# --- RULE ENGINE & VIOLATION EVENTS APIS ---

@csrf_exempt
def rules_run_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    tracking_run_id = data.get("tracking_run_id")
    source_id = data.get("source_id", "")
    scene_config_id = data.get("scene_config_id")
    signal_timeline_id = data.get("signal_timeline_id")

    if not tracking_run_id:
        return JsonResponse({"error": "tracking_run_id is required"}, status=400)
    if not source_id:
        return JsonResponse({"error": "source_id is required"}, status=400)

    run_dir = settings.BASE_DIR / "outputs" / "runs" / tracking_run_id
    tracks_file = run_dir / "tracks.jsonl"
    if not tracks_file.is_file():
        return JsonResponse({"error": f"tracks.jsonl not found for run {tracking_run_id}"}, status=404)
    summary_file = run_dir / "summary.json"
    if not summary_file.is_file():
        return JsonResponse({"error": "Thiếu thông tin nguồn của bản tracking"}, status=400)
    try:
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return JsonResponse({"error": "Không đọc được thông tin bản tracking"}, status=400)
    if ntpath.basename(str(summary.get("source", ""))) != source_id:
        return JsonResponse({"error": "Bản tracking không thuộc video đã chọn"}, status=400)

    scene_record = SceneConfigRecord.objects.filter(
        scene_id=scene_config_id, source_id=source_id
    ).order_by("-version").first()

    if not scene_record:
        return JsonResponse({
            "error": "Chưa có quy ước ngã tư! Vui lòng vẽ các vạch dừng/tim đường rồi bấm 'Lưu Quy Ước' trước khi chấm vi phạm."
        }, status=400)

    scene = SceneConfig.from_dict(scene_record.to_dict())

    # Recorded video has no signal evidence unless a synchronized timeline is supplied.
    timeline = None
    timeline_record = None
    if signal_timeline_id:
        timeline_record = SignalTimelineRecord.objects.filter(
            timeline_id=signal_timeline_id, video_id=scene_record.source_id
        ).order_by("-version").first()
        if not timeline_record:
            return JsonResponse({"error": "Chưa có lịch sử pha đèn cho video đã chọn"}, status=400)
        timeline = SignalTimeline.from_dict(timeline_record.to_dict())

    # Create RuleRunRecord
    rule_run_id = f"rulerun_{tracking_run_id}_s{scene_record.version}_t{timeline_record.version if timeline_record else 0}"
    rule_run_rec, _ = RuleRunRecord.objects.get_or_create(
        rule_run_id=rule_run_id,
        defaults={
            "scene_config": scene_record,
            "signal_timeline": timeline_record,
        },
    )

    # Execute RuleEngine
    engine = RuleEngine(scene=scene, timeline=timeline, rule_run_id=rule_run_id)
    generated_events = engine.process_tracks_file(tracks_file)

    # Determine source video for evidence capture
    source_video_path = settings.DATA_RAW_DIR / source_id
    if not source_video_path.is_file():
        return JsonResponse({"error": "Không tìm thấy video gốc để tạo bằng chứng"}, status=404)

    saved_events = []
    for ev in generated_events:
        # Create evidence images
        full_url, crop_url = create_violation_evidence(
            video_path=source_video_path,
            event_id=ev.event_id,
            timestamp_ms=ev.event_timestamp_ms,
            track_id=ev.track_id,
            bbox_xyxy=ev.bbox_xyxy,
            rule_type=ev.rule_type,
        )

        rec, created = ViolationEventRecord.objects.get_or_create(
            event_id=ev.event_id,
            defaults={
                "rule_run": rule_run_rec,
                "segment_id": ev.segment_id,
                "rule_type": ev.rule_type,
                "track_id": ev.track_id,
                "vehicle_type": ev.vehicle_type,
                "event_timestamp_ms": ev.event_timestamp_ms,
                "bbox_xyxy": ev.bbox_xyxy,
                "scene_config_version": ev.scene_config_version,
                "signal_source": ev.signal_source,
                "reason": ev.reason,
                "full_image_path": full_url,
                "crop_image_path": crop_url,
            },
        )
        saved_events.append(rec.to_dict())

    return JsonResponse(
        {
            "rule_run_id": rule_run_id,
            "events_count": len(saved_events),
            "events": saved_events,
        }
    )


def events_list_api(request):
    qs = ViolationEventRecord.objects.all()
    run_id = request.GET.get("run_id")
    if run_id:
        qs = qs.filter(rule_run_id=run_id)
    rule_type = request.GET.get("rule_type")
    review_status = request.GET.get("review_status")
    if rule_type:
        qs = qs.filter(rule_type=rule_type)
    if review_status:
        qs = qs.filter(review_status=review_status)

    events = [e.to_dict() for e in qs.order_by("-event_timestamp_ms")]
    return JsonResponse({"events": events, "total": len(events)})


@csrf_exempt
def event_review_api(request, event_id: str):
    if request.method not in ("PATCH", "POST"):
        return JsonResponse({"error": "PATCH or POST required"}, status=405)

    try:
        rec = ViolationEventRecord.objects.get(event_id=event_id)
    except ViolationEventRecord.DoesNotExist:
        return JsonResponse({"error": "Event not found"}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "review_status" in data:
        status = data["review_status"]
        if status in ("pending", "confirmed", "dismissed"):
            rec.review_status = status
    if "review_note" in data:
        rec.review_note = str(data["review_note"])

    rec.save()
    return JsonResponse(rec.to_dict())


# --- DROIDCAM LIVE APIS ---

@csrf_exempt
def live_connect_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    url = data.get("url", "mock://droidcam")
    if not isinstance(url, str) or not url.strip():
        return JsonResponse({"error": "Bạn chưa nhập địa chỉ camera"}, status=400)
    LiveProcessingManager.get_instance().stop()
    mgr = DroidCamManager.get_instance()
    try:
        res = mgr.connect(url)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    LiveProcessingManager.get_instance().prepare()
    return JsonResponse(res)


def live_preview_api(request):
    mgr = DroidCamManager.get_instance()
    jpeg_bytes = mgr.get_latest_jpeg(wait_timeout=0.1, max_age_ms=2000)
    if not jpeg_bytes:
        return HttpResponse("No live frame available", status=503)
    response = HttpResponse(jpeg_bytes, content_type="image/jpeg")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def live_status_api(request):
    mgr = DroidCamManager.get_instance()
    return JsonResponse(mgr.get_status())


@csrf_exempt
def live_processing_api(request):
    manager = LiveProcessingManager.get_instance()
    if request.method == "GET":
        return JsonResponse(manager.get_status())
    if request.method == "DELETE":
        manager.stop()
        return JsonResponse(manager.get_status())
    if request.method != "POST":
        return JsonResponse({"error": "GET, POST or DELETE required"}, status=405)
    try:
        data = json.loads(request.body)
        scene_id = data.get("scene_config_id")
        scene = SceneConfigRecord.objects.filter(scene_id=scene_id, source_id="live").order_by("-version").first()
        if not scene:
            return JsonResponse({"error": "Không tìm thấy quy ước camera đã lưu"}, status=404)
        hardware = ArduinoSignalService.get_instance().status()
        phase = hardware["phase"] if hardware.get("connected") else data.get("phase", "UNKNOWN")
        return JsonResponse(manager.start(scene, phase), status=202)
    except (ValueError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except (ConnectionError, OSError) as exc:
        manager.set_phase("UNKNOWN")
        return JsonResponse({"error": str(exc)}, status=503)


@csrf_exempt
def live_phase_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        phase = json.loads(request.body)["phase"]
        hardware = ArduinoSignalService.get_instance().status()
        if hardware.get("connected"):
            phase = hardware["phase"]
        if not LiveProcessingManager.get_instance().set_phase(phase, source="arduino" if hardware.get("connected") else "live"):
            return JsonResponse({"error": "Nhận diện trực tiếp chưa hoạt động"}, status=409)
        return JsonResponse({"status": "ok"})
    except (ValueError, KeyError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except (ConnectionError, OSError) as exc:
        LiveProcessingManager.get_instance().set_phase("UNKNOWN")
        return JsonResponse({"error": str(exc)}, status=503)
