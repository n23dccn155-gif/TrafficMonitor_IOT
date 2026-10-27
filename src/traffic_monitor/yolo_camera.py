"""Optional YOLO + ByteTrack comparison for the same P0 video window."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

import cv2
import torch

from debug_preview import DebugPreview, ProcessingMeter
from model_assets import ensure_official_weights


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = "yolov8n.pt"
os.environ.setdefault("YOLO_CONFIG_DIR", str(PROJECT_ROOT / "outputs" / ".ultralytics"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO + ByteTrack baseline on one MP4 camera")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--show", action="store_true", help="Show raw and annotated frames live")
    parser.add_argument("--save-video", action="store_true", help="Save annotated MP4 (off by default)")
    args = parser.parse_args()
    is_live = args.source.startswith(("http://", "https://", "rtsp://"))
    if not is_live and not Path(args.source).is_file():
        parser.error(f"Input video not found: {args.source}")
    if args.weights != DEFAULT_WEIGHTS and not Path(args.weights).is_file():
        parser.error(f"Model weights not found: {args.weights}")
    if args.width <= 0 or (args.max_frames is not None and args.max_frames <= 0):
        parser.error("--width and --max-frames must be positive")
    if not 0 < args.confidence < 1:
        parser.error("--confidence must be between 0 and 1")
    return args


def main() -> None:
    args = parse_args()
    from ultralytics import YOLO

    capture = cv2.VideoCapture(args.source)
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {args.source}")
    is_live = args.source.startswith(("http://", "https://", "rtsp://"))
    reported_fps = float(capture.get(cv2.CAP_PROP_FPS))
    fps = reported_fps if reported_fps > 0 else 30.0
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    source_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    first_frame = None
    if source_width <= 0 or source_height <= 0:
        ok, first_frame = capture.read()
        if ok and first_frame is not None:
            source_height, source_width = first_frame.shape[:2]
    if source_width <= 0 or source_height <= 0:
        capture.release()
        raise SystemExit("Could not read a frame from the video source")
    width = min(args.width, source_width)
    height = round(source_height * width / source_width)
    args.output.mkdir(parents=True, exist_ok=True)
    writer = None
    if args.save_video:
        writer = cv2.VideoWriter(
            str(args.output / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        if not writer.isOpened():
            capture.release()
            raise SystemExit("Could not create output video")

    weights_path = ensure_official_weights(args.weights) if args.weights == DEFAULT_WEIGHTS else Path(args.weights)
    model = YOLO(str(weights_path))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    preview = DebugPreview(
        args.show, "TrafficMonitor P0 - YOLO+ByteTrack",
        snapshot_dir=str(args.output / "snapshots"),
    )
    meter = ProcessingMeter(fps)
    history: dict[int, deque[tuple[int, int]]] = defaultdict(lambda: deque(maxlen=60))
    distinct_ids: set[int] = set()
    max_simultaneous = 0
    total_observations = 0
    frame_index = 0
    started = time.perf_counter()
    try:
        with (args.output / "tracks.jsonl").open("w", encoding="utf-8") as sink:
            while args.max_frames is None or frame_index < args.max_frames:
                frame_started = time.perf_counter()
                if first_frame is not None:
                    ok, source_frame = True, first_frame
                    first_frame = None
                else:
                    ok, source_frame = capture.read()
                if not ok:
                    break
                frame = cv2.resize(source_frame, (width, height))
                result = model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=[2, 3, 5, 7],
                    conf=args.confidence,
                    imgsz=width,
                    device=device,
                    verbose=False,
                )[0]
                records = []
                boxes = result.boxes
                if boxes is not None and boxes.id is not None:
                    for box in boxes:
                        if box.id is None:
                            continue
                        track_id = int(box.id.item())
                        x1, y1, x2, y2 = [int(round(v)) for v in box.xyxy[0].tolist()]
                        px, py = (x1 + x2) // 2, y2
                        history[track_id].append((px, py))
                        records.append(
                            {
                                "track_id": track_id,
                                "vehicle_type": result.names[int(box.cls.item())],
                                "class_confidence": round(float(box.conf.item()), 4),
                                "bbox_xyxy": [x1, y1, x2, y2],
                                "ground_point_xy": [px, py],
                                "trajectory_xy": [list(p) for p in history[track_id]],
                                "track_quality": "confirmed",
                                "observation_kind": "detection",
                            }
                        )
                timestamp_ms = round((time.perf_counter() - started) * 1000) if is_live else round(frame_index * 1000 / fps)
                sink.write(
                    json.dumps(
                        {
                            "camera_id": "CAM_01",
                            "frame_index": frame_index,
                            "video_timestamp_ms": timestamp_ms,
                            "processing_size": [width, height],
                            "tracks": records,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                annotated = frame.copy()
                for item in records:
                    x1, y1, x2, y2 = item["bbox_xyxy"]
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 230, 0), 2)
                    cv2.putText(
                        annotated,
                        f"ID {item['track_id']} {item['vehicle_type']}",
                        (x1, max(18, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 230, 0),
                        2,
                    )
                    trail = item["trajectory_xy"]
                    for start, end in zip(trail, trail[1:]):
                        cv2.line(annotated, tuple(start), tuple(end), (0, 220, 255), 2)
                cv2.putText(
                    annotated,
                    f"P0 YOLO+ByteTrack | frame {frame_index} | {timestamp_ms / 1000:.2f}s",
                    (15, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                )
                if writer is not None:
                    writer.write(annotated)
                distinct_ids.update(item["track_id"] for item in records)
                max_simultaneous = max(max_simultaneous, len(records))
                total_observations += len(records)
                frame_index += 1
                stats = meter.sample(time.perf_counter() - frame_started)
                if not preview.show(frame, annotated, stats=stats):
                    print("Stopped by viewer; partial output was saved.")
                    break
                if frame_index % 100 == 0:
                    print(f"Processed {frame_index} frames...", flush=True)
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        preview.close()

    elapsed = time.perf_counter() - started
    summary = {
        "source": args.source if is_live else str(Path(args.source).resolve()),
        "weights": str(weights_path.resolve()),
        "device": device,
        "source_fps": reported_fps if is_live else fps,
        "source_size": [source_width, source_height],
        "source_frames": source_frames,
        "processing_size": [width, height],
        "processed_frames": frame_index,
        "processed_seconds_of_video": None if is_live else round(frame_index / fps, 3),
        "elapsed_seconds": round(elapsed, 3),
        "processing_fps": round(frame_index / elapsed, 3) if elapsed else 0,
        "distinct_confirmed_track_ids": len(distinct_ids),
        "max_simultaneous_confirmed_tracks": max_simultaneous,
        "total_confirmed_observations": total_observations,
        "confidence_threshold": args.confidence,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
