"""Process the latest DroidCam frame without opening a second camera connection."""
from __future__ import annotations

import datetime
import os
import threading
import time
from pathlib import Path

import cv2
from django.conf import settings
from django.db import close_old_connections

from src.traffic_monitor.model_assets import ensure_official_weights
from src.traffic_monitor.traffic_rules.engine import RuleEngine
from src.traffic_monitor.traffic_rules.geometry import scale_bbox
from src.traffic_monitor.traffic_rules.schemas import SceneConfig, SignalTimeline, TrackFrame

from ..models import RuleRunRecord, SceneConfigRecord, ViolationEventRecord
from .droidcam_service import DroidCamManager
from .arduino_signal_service import ArduinoSignalService
from .live_signal_timer import LiveSignalTimer, parse_signal_config
from .input_optimizer import (
    TrackFilter, box_to_frame, point_in_roi, roi_rect, scene_polygons, yolo_input_size,
)

TRACKER_CONFIG = str(Path(__file__).with_name("bytetrack_live.yaml"))
DETECT_CONF = 0.1  # thấp để ByteTrack có box cho bước ghép thứ hai; lọc thật ở TrackFilter


def is_usable_vehicle_box(bbox: list[int], frame_width: int, frame_height: int) -> bool:
    """Discard invalid or nearly full-frame detections before tracking rules/UI."""
    x1, y1, x2, y2 = bbox
    box_width, box_height = x2 - x1, y2 - y1
    if box_width <= 0 or box_height <= 0 or frame_width <= 0 or frame_height <= 0:
        return False
    if (x1 < 0 or y1 < 0 or x2 > frame_width or y2 > frame_height):
        return False
    # This overhead camera monitors small vehicles on a tabletop/road scene.
    # A single vehicle covering a quarter of the whole view is not usable as
    # a traffic track, even if an off-the-shelf detector calls it a car.
    return box_width * box_height < 0.25 * frame_width * frame_height


class LiveProcessingManager:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.run_id = None
        self.status = "IDLE"
        self.error = ""
        self.latest_tracks = None
        self.timeline = None
        self.signal_timer = None
        self.signal_warning = ""
        self.event_count = 0
        self._signal_thread = None
        self._start_monotonic_ms = 0
        self.last_result_monotonic_ms = 0
        self._model_lock = threading.Lock()
        self._prepare_lock = threading.Lock()
        self._model_ready = threading.Event()
        self._model = None
        self._model_error = ""

    def prepare(self):
        """Load weights and warm inference while the user draws the scene."""
        with self._prepare_lock:
            if self._model == "loading" or (self._model_ready.is_set() and self._model is not None):
                return
            self._model_ready.clear()
            self._model_error = ""
            self._model = "loading"
            threading.Thread(target=self._prepare_worker, daemon=True).start()

    def _prepare_worker(self):
        try:
            os.environ.setdefault("YOLO_CONFIG_DIR", str(settings.BASE_DIR / "outputs" / ".ultralytics"))
            import numpy as np
            import torch
            from ultralytics import YOLO

            model = YOLO(str(ensure_official_weights("yolov8n.pt")))
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            model.predict(np.zeros((540, 960, 3), dtype=np.uint8), imgsz=960, device=device, verbose=False)
            with self._prepare_lock:
                self._model = (model, device)
        except Exception as exc:
            with self._prepare_lock:
                self._model = None
                self._model_error = str(exc)
        finally:
            self._model_ready.set()

    @classmethod
    def get_instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _run_ms(self) -> int:
        """Milliseconds since this run started, on the same clock as frame timestamps."""
        return max(0, int(time.monotonic() * 1000) - self._start_monotonic_ms)

    def start(self, scene_record: SceneConfigRecord, signal_config: dict) -> dict:
        camera = DroidCamManager.get_instance()
        if not camera.get_status()["connected"]:
            raise ValueError("Camera chưa có khung hình mới. Hãy kết nối lại trước khi chạy nhận diện.")
        signal_config = parse_signal_config(signal_config)
        self.stop()
        self.prepare()
        run_id = "live_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        timeline = SignalTimeline(
            timeline_id=f"timeline_{run_id}", version=1, video_id="live", mode="live", changes=[],
        )
        stop_event = threading.Event()
        with self._lock:
            self.run_id = run_id
            self.status = "STARTING"
            self.error = ""
            self.latest_tracks = None
            self.timeline = timeline
            self.signal_timer = LiveSignalTimer(timeline, signal_config, now_ms=0)
            self.signal_warning = ""
            self.event_count = 0
            self._start_monotonic_ms = int(time.monotonic() * 1000)
            self.last_result_monotonic_ms = 0
            self._stop = stop_event
        self._thread = threading.Thread(
            target=self._worker, args=(run_id, scene_record, camera, timeline, stop_event), daemon=True,
        )
        self._signal_thread = threading.Thread(target=self._signal_worker, args=(stop_event,), daemon=True)
        self._thread.start()
        self._signal_thread.start()
        return self.get_status()

    def stop(self):
        self._stop.set()
        for thread in (self._thread, self._signal_thread):
            if thread and thread.is_alive():
                thread.join(timeout=2)
        self._thread = None
        self._signal_thread = None
        with self._lock:
            self.status = "IDLE"
            self.latest_tracks = None
            self.timeline = None
            self.signal_timer = None

    def is_running(self) -> bool:
        with self._lock:
            return self.signal_timer is not None and self.status in {"STARTING", "RUNNING"}

    def set_signal(self, signal_config: dict) -> bool:
        """Change timer durations or switch to a manual phase during a live run."""
        signal_config = parse_signal_config(signal_config)
        with self._lock:
            if self.signal_timer is None or self.status not in {"STARTING", "RUNNING"}:
                return False
            self.signal_timer.configure(signal_config, self._run_ms())
            return True

    def _signal_worker(self, stop_event):
        """Advance the timer and make the Arduino lamps follow it.

        Runs apart from detection so serial I/O never delays YOLO. Serial errors
        only produce a warning: violations always use the timer's phases.
        """
        arduino = ArduinoSignalService.get_instance()
        sent_phase = None
        while not stop_event.is_set():
            with self._lock:
                if self.signal_timer is None:
                    break
                self.signal_timer.advance(self._run_ms())
                phase = self.signal_timer.phase
            if not arduino.is_connected():
                sent_phase = None
            elif phase != sent_phase:
                try:
                    arduino.command(f"MANUAL {phase}")
                    sent_phase = phase
                    self.signal_warning = ""
                except (ConnectionError, OSError) as exc:
                    self.signal_warning = f"Arduino không theo được timer: {exc}"
            stop_event.wait(0.05)

    def get_status(self):
        with self._lock:
            timer = self.signal_timer
            return {
                "run_id": self.run_id, "status": self.status, "error": self.error,
                "phase": timer.phase if timer else "UNKNOWN",
                "signal": timer.state(self._run_ms()) if timer else None,
                "signal_warning": self.signal_warning,
                "event_count": self.event_count,
                "frame": self.latest_tracks,
                "detector_warning": self._model_error,
                "model_ready": self._model_ready.is_set(),
                "model_loaded": isinstance(self._model, tuple),
                "result_age_ms": (int(time.monotonic() * 1000) - self.last_result_monotonic_ms)
                if self.last_result_monotonic_ms else -1,
            }

    def _worker(self, run_id, scene_record, camera, timeline, stop_event):
        close_old_connections()
        try:
            scene = SceneConfig.from_dict(scene_record.to_dict())
            engine = RuleEngine(scene, timeline, rule_run_id=run_id)
            run_record = RuleRunRecord.objects.create(rule_run_id=run_id, scene_config=scene_record)
            track_filter = TrackFilter()
            roi_cache = {}  # kích thước frame -> (polygons, rect); camera có thể đổi độ phân giải khi nối lại
            start_ms = self._start_monotonic_ms
            last_timestamp_ms = 0
            last_camera_timestamp = 0
            frame_index = 0
            model_reset = False
            segment_index = 0
            was_paused = False
            while not stop_event.is_set():
                with camera._lock:
                    camera_timestamp = camera.latest_timestamp_ms
                    source_frame = camera.latest_frame.copy() if camera.latest_frame is not None else None
                if (source_frame is None or camera_timestamp == last_camera_timestamp
                        or int(time.time() * 1000) - camera_timestamp > 2000):
                    stop_event.wait(0.03)
                    continue
                if last_camera_timestamp and camera_timestamp - last_camera_timestamp > 3000:
                    # A reconnect starts a fresh local-ID space and rule segment.
                    track_filter.clear()
                    model_reset = False
                    segment_index += 1
                last_camera_timestamp = camera_timestamp
                with self._lock:
                    timer = self.signal_timer
                    if timer is not None:
                        timer.advance(self._run_ms())
                    paused = timer is not None and timer.paused
                if paused and not was_paused:
                    # Cả hai vàng: dừng YOLO. Khi chạy lại, xe được nhận từ đầu ở segment mới
                    # để vị trí cũ trước lúc dừng không tạo ra lần cắt vạch giả.
                    track_filter.clear()
                    model_reset = False
                    segment_index += 1
                was_paused = paused
                # Mốc của frame là lúc camera nhận ảnh (trừ đi tuổi của frame), cùng đồng hồ
                # monotonic với các lần đổi pha đèn; không dùng lúc YOLO xử lý xong.
                frame_age_ms = max(0, int(time.time() * 1000) - camera_timestamp)
                timestamp_ms = max(last_timestamp_ms, int(time.monotonic() * 1000) - frame_age_ms - start_ms, 0)
                last_timestamp_ms = timestamp_ms
                track_filter.next_frame()
                source_h, source_w = source_frame.shape[:2]
                processing_size = [source_w, source_h]
                width, height = processing_size
                if (width, height) not in roi_cache:
                    polygons = scene_polygons(scene, processing_size)
                    roi_cache[(width, height)] = (polygons, roi_rect(polygons, processing_size))
                roi_polygons, roi = roi_cache[(width, height)]
                yolo_tracks = []
                yolo_detections = []
                raw_box_count = 0
                without_track_id = 0
                rejected_box_count = 0
                unconfirmed_count = 0
                if not paused and self._model_ready.is_set() and isinstance(self._model, tuple):
                    model, device = self._model
                    rx1, ry1, rx2, ry2 = roi
                    yolo_size = yolo_input_size(rx2 - rx1, ry2 - ry1)
                    yolo_width, yolo_height = yolo_size
                    yolo_frame = cv2.resize(source_frame[ry1:ry2, rx1:rx2], yolo_size, interpolation=cv2.INTER_AREA)
                    try:
                        with self._model_lock:
                            if stop_event.is_set():
                                break
                            if not model_reset:
                                for tracker in getattr(getattr(model, "predictor", None), "trackers", []):
                                    tracker.reset()
                                model_reset = True
                            result = model.track(
                                yolo_frame, persist=True, tracker=TRACKER_CONFIG, classes=[2, 3, 5, 7],
                                conf=DETECT_CONF, imgsz=960, agnostic_nms=True, device=device, verbose=False,
                            )[0]
                        boxes = result.boxes
                        raw_box_count = len(boxes) if boxes is not None else 0
                        without_track_id = raw_box_count if boxes is not None and boxes.id is None else 0
                        if boxes is not None:
                            for box in boxes:
                                yolo_box = [int(round(v)) for v in box.xyxy[0].tolist()]
                                if not is_usable_vehicle_box(yolo_box, yolo_width, yolo_height):
                                    rejected_box_count += 1
                                    continue
                                mapped_box = box_to_frame(yolo_box, yolo_size, roi)
                                x1, y1, x2, y2 = mapped_box
                                point = [(x1 + x2) // 2, y2]
                                if not point_in_roi(point, roi_polygons):
                                    # Chân xe ngoài mọi vùng hướng/nút giao (vỉa hè, nhà...).
                                    rejected_box_count += 1
                                    continue
                                vehicle_type = result.names[int(box.cls.item())]
                                confidence = float(box.conf.item())
                                detection = {
                                    "vehicle_type": vehicle_type,
                                    "class_confidence": confidence,
                                    "bbox_xyxy": mapped_box,
                                }
                                if box.id is None:
                                    yolo_detections.append(detection)
                                    continue
                                state = track_filter.update(
                                    int(box.id.item()), vehicle_type, point, mapped_box, timestamp_ms,
                                )
                                track_id = state["track_id"]  # ổn định qua các lần ByteTrack đổi ID
                                if not state["confirmed"]:
                                    # Track mới chớp tắt: chỉ hiển thị, chưa xét luật.
                                    unconfirmed_count += 1
                                    yolo_detections.append(detection)
                                    continue
                                yolo_tracks.append({
                                    "track_id": track_id,
                                    "track_source": "yolo",
                                    "vehicle_type": state["vehicle_type"],
                                    "class_confidence": confidence,
                                    "bbox_xyxy": mapped_box,
                                    "ground_point_xy": state["ground_point_xy"],
                                    "trajectory_xy": state["trajectory_xy"],
                                    "observation_kind": "detection",
                                })
                    except Exception as exc:
                        self._model_error = str(exc)
                        self._model = None
                tracks = yolo_tracks
                frame_data = {
                    "camera_id": "CAM_01", "frame_index": frame_index,
                    "segment_id": f"seg{segment_index}",
                    "video_timestamp_ms": timestamp_ms, "processing_size": [width, height],
                    "roi_xyxy": list(roi),
                    "tracks": tracks,
                    "yolo_detections": yolo_detections,
                    "detection_stats": {
                        "raw_boxes": raw_box_count,
                        "without_track_id": without_track_id,
                        "rejected_boxes": rejected_box_count,
                        "unconfirmed_tracks": unconfirmed_count,
                        "motion_tracks": 0,
                        "yolo_tracks": len(yolo_tracks),
                        "yolo_detections": len(yolo_detections),
                    },
                }
                with self._lock:
                    if stop_event.is_set() or self.run_id != run_id:
                        break
                    self.latest_tracks = frame_data
                    self.last_result_monotonic_ms = int(time.monotonic() * 1000)
                    self.status = "RUNNING"
                    # Ghi mọi lần đổi pha tới thời điểm này trước khi xét luật.
                    self.signal_timer.advance(self._run_ms())
                    events = engine.process_frame(TrackFrame.from_dict(frame_data))
                current_boxes = {track["track_id"]: track["bbox_xyxy"] for track in tracks}
                for event in events:
                    if event.track_id in current_boxes:
                        # Evidence is taken from this frame, so its box and time
                        # must refer to this frame rather than the first warning.
                        event.bbox_xyxy = scale_bbox(
                            current_boxes[event.track_id], [width, height], scene.reference_size,
                        )
                        event.event_timestamp_ms = timestamp_ms
                    self._save_event(event, source_frame, run_record)
                    with self._lock:
                        self.event_count += 1
                frame_index += 1
                if paused:
                    stop_event.wait(0.1)  # chỉ cập nhật ảnh, không cần chạy hết tốc độ
        except Exception as exc:
            with self._lock:
                if self.run_id == run_id:
                    self.status = "FAILED"
                    self.error = str(exc)
        finally:
            close_old_connections()

    @staticmethod
    def _save_event(event, frame, run_record):
        # Rule coordinates are in scene reference space; evidence uses source pixels.
        source_h, source_w = frame.shape[:2]
        ref_w, ref_h = run_record.scene_config.data_json["reference_size"]
        x1, y1, x2, y2 = event.bbox_xyxy
        x1 = max(0, min(source_w - 1, round(x1 * source_w / ref_w)))
        y1 = max(0, min(source_h - 1, round(y1 * source_h / ref_h)))
        x2 = max(x1 + 1, min(source_w, round(x2 * source_w / ref_w)))
        y2 = max(y1 + 1, min(source_h, round(y2 * source_h / ref_h)))
        evidence_dir = settings.MEDIA_ROOT / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        full_path = evidence_dir / f"{event.event_id}_full.jpg"
        crop_path = evidence_dir / f"{event.event_id}_crop.jpg"
        annotated = frame.copy()
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.imwrite(str(full_path), annotated)
        cv2.imwrite(str(crop_path), annotated[y1:y2, x1:x2])
        ViolationEventRecord.objects.get_or_create(event_id=event.event_id, defaults={
            "rule_run": run_record, "segment_id": event.segment_id,
            "rule_type": event.rule_type, "track_id": event.track_id,
            "vehicle_type": event.vehicle_type,
            "event_timestamp_ms": event.event_timestamp_ms,
            "bbox_xyxy": event.bbox_xyxy,
            "scene_config_version": event.scene_config_version,
            "signal_source": event.signal_source, "reason": event.reason,
            "full_image_path": f"/media/evidence/{full_path.name}",
            "crop_image_path": f"/media/evidence/{crop_path.name}",
        })
