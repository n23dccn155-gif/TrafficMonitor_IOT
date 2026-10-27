"""Run the existing TechGAR motion tracker on one recorded traffic camera.

This is a P0 baseline and deliberately does not classify traffic violations.
It imports TechGAR from the sibling reference project without changing its code.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2

from debug_preview import DebugPreview, ProcessingMeter


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TECHGAR_ROOT = Path(os.environ.get(
    "TECHGAR_ROOT",
    str(PROJECT_ROOT.parent / "TechGAR_Parking" / "TechGAR_Parking" / "backend" / "main_detect"),
)).expanduser().resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TechGAR baseline on one MP4 camera")
    parser.add_argument("--source", type=Path, required=True, help="Input MP4 path")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--width", type=int, default=1280, help="Processing width in pixels")
    parser.add_argument("--max-frames", type=int, default=None, help="Limit for a short probe")
    parser.add_argument("--min-area", type=int, default=180, help="Minimum motion blob area")
    parser.add_argument("--min-width", type=int, default=9)
    parser.add_argument("--min-height", type=int, default=9)
    parser.add_argument("--min-displacement", type=float, default=6.0)
    parser.add_argument("--max-distance", type=float, default=100.0)
    parser.add_argument("--show", action="store_true", help="Show raw and annotated frames live")
    parser.add_argument("--save-video", action="store_true", help="Save annotated MP4 (off by default)")
    parser.add_argument("--show-mask", action="store_true", help="Show MOG2 motion mask with --show")
    args = parser.parse_args()
    if args.width <= 0 or (args.max_frames is not None and args.max_frames <= 0):
        parser.error("--width and --max-frames must be positive")
    if not args.source.is_file():
        parser.error(f"Input video not found: {args.source}")
    if not (TECHGAR_ROOT / "src" / "techgar" / "motion_tracker.py").is_file():
        parser.error(
            f"TechGAR reference missing: {TECHGAR_ROOT}. "
            "Option 2 needs the separate TechGAR repository; set TECHGAR_ROOT to its backend/main_detect directory."
        )
    return args


def track_record(track: object) -> dict:
    x, y, w, h = track.bbox
    return {
        "track_id": int(track.track_id),
        "vehicle_type": "unknown",  # Motion blobs do not identify a vehicle class.
        "bbox_xyxy": [int(x), int(y), int(x + w), int(y + h)],
        "ground_point_xy": [int(track.cx), int(track.cy)],
        "trajectory_xy": [[int(px), int(py)] for px, py in track.history],
        "track_quality": track.status.value,
        "observation_kind": getattr(track, "observation_kind", "unknown"),
        "prediction_source": getattr(track, "prediction_source", "unknown"),
    }


def draw_overlay(frame, records: list[dict], frame_index: int, timestamp_ms: int):
    for item in records:
        x1, y1, x2, y2 = item["bbox_xyxy"]
        cx, cy = item["ground_point_xy"]
        color = (0, 140, 255) if item["observation_kind"] == "prediction" else (0, 230, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (cx, cy), 3, (0, 0, 255), -1)
        trail = item["trajectory_xy"]
        for start, end in zip(trail, trail[1:]):
            cv2.line(frame, tuple(start), tuple(end), (0, 220, 255), 2)
        cv2.putText(
            frame,
            f"ID {item['track_id']}",
            (x1, max(18, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )
    cv2.putText(
        frame,
        f"P0 motion baseline | frame {frame_index} | {timestamp_ms / 1000:.2f}s",
        (15, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )
    return frame


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(TECHGAR_ROOT / "src"))
    from techgar.motion_tracker import MotionVehicleTracker

    capture = cv2.VideoCapture(str(args.source))
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {args.source}")
    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    if source_fps <= 0:
        capture.release()
        raise SystemExit("Video does not report a usable FPS")
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    source_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if source_width <= 0 or source_height <= 0:
        capture.release()
        raise SystemExit("Video does not report a usable frame size")
    width = min(args.width, source_width)
    height = round(source_height * width / source_width)

    args.output.mkdir(parents=True, exist_ok=True)
    video_path = args.output / "annotated.mp4"
    jsonl_path = args.output / "tracks.jsonl"
    summary_path = args.output / "summary.json"
    writer = None
    if args.save_video:
        writer = cv2.VideoWriter(
            str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), source_fps, (width, height)
        )
        if not writer.isOpened():
            capture.release()
            raise SystemExit(f"Could not create output video: {video_path}")

    tracker = MotionVehicleTracker(
        min_area=args.min_area,
        min_width=args.min_width,
        min_height=args.min_height,
        min_confirm_displacement=args.min_displacement,
        max_distance=args.max_distance,
        history_len=60,
        enable_multiscale_motion=True,
        reject_cast_shadows=True,
    )
    preview = DebugPreview(
        args.show, "TrafficMonitor P0 - TechGAR", args.show_mask,
        snapshot_dir=str(args.output / "snapshots"),
    )
    meter = ProcessingMeter(source_fps)
    started = time.perf_counter()
    frame_index = 0
    track_ids: set[int] = set()
    max_simultaneous = 0
    total_observations = 0
    try:
        with jsonl_path.open("w", encoding="utf-8") as sink:
            while args.max_frames is None or frame_index < args.max_frames:
                frame_started = time.perf_counter()
                ok, source_frame = capture.read()
                if not ok:
                    break
                frame = cv2.resize(source_frame, (width, height))
                timestamp_ms = round(frame_index * 1000 / source_fps)
                _, mask, _ = tracker.process_frame(frame, timestamp_s=timestamp_ms / 1000)
                records = [track_record(t) for t in tracker.active_tracks.values()]
                track_ids.update(item["track_id"] for item in records)
                max_simultaneous = max(max_simultaneous, len(records))
                total_observations += len(records)
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
                annotated = draw_overlay(frame.copy(), records, frame_index, timestamp_ms)
                if writer is not None:
                    writer.write(annotated)
                frame_index += 1
                stats = meter.sample(time.perf_counter() - frame_started)
                if not preview.show(frame, annotated, mask, stats=stats):
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
        "source": str(args.source.resolve()),
        "source_fps": source_fps,
        "source_size": [source_width, source_height],
        "source_frames": source_frames,
        "processing_size": [width, height],
        "processed_frames": frame_index,
        "processed_seconds_of_video": round(frame_index / source_fps, 3),
        "elapsed_seconds": round(elapsed, 3),
        "processing_fps": round(frame_index / elapsed, 3) if elapsed else 0,
        "distinct_confirmed_track_ids": len(track_ids),
        "max_simultaneous_confirmed_tracks": max_simultaneous,
        "total_confirmed_observations": total_observations,
        "tracker_settings": {
            "min_area": args.min_area,
            "min_width": args.min_width,
            "min_height": args.min_height,
            "min_displacement": args.min_displacement,
            "max_distance": args.max_distance,
        },
        "outputs": {
            "video": str(video_path.resolve()) if args.save_video else None,
            "tracks": str(jsonl_path.resolve()),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
