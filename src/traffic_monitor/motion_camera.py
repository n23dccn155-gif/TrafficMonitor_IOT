"""Self-contained MOG2 foreground tracking for menu option 2.

Reuses the blob tracker already implemented in classical_compare.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

from classical_compare import KalmanBlobTracker, boxes_from_mask, clean_mask
from debug_preview import DebugPreview, ProcessingMeter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MOG2 foreground + Kalman blob tracking")
    parser.add_argument("--source", required=True, help="MP4 path or camera URL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--min-area", type=int, default=80)
    parser.add_argument("--max-distance", type=float, default=65)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--save-video", action="store_true")
    args = parser.parse_args()
    is_live = args.source.startswith(("http://", "https://", "rtsp://"))
    if not is_live and not Path(args.source).is_file():
        parser.error(f"Input video not found: {args.source}")
    if args.width <= 0 or args.min_area <= 0 or args.max_distance <= 0:
        parser.error("width, min-area and max-distance must be positive")
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("max-frames must be positive")
    return args


def observation(record: dict) -> dict:
    x1, y1, x2, y2 = record["bbox_xyxy"]
    # The tracker stores blob centers. Estimate contact points with the current
    # box height; there is no camera calibration in this baseline.
    half_height = (y2 - y1) / 2
    trail = [[x, round(y + half_height)] for x, y in record["trajectory_xy"]]
    predicted = record["observation_kind"] == "kalman_prediction"
    return {
        "track_id": record["track_id"],
        "vehicle_type": "unknown",
        "bbox_xyxy": record["bbox_xyxy"],
        "ground_point_xy": [(x1 + x2) // 2, y2],
        "trajectory_xy": trail,
        "track_quality": "predicted" if predicted else "confirmed",
        "observation_kind": record["observation_kind"],
        "missing_frames": record["missing_frames"],
    }


def draw_tracks(frame, records: list[dict], frame_index: int, timestamp_ms: int):
    annotated = frame.copy()
    for item in records:
        x1, y1, x2, y2 = item["bbox_xyxy"]
        predicted = item["track_quality"] == "predicted"
        color = (180, 90, 255) if predicted else (0, 230, 0)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated, f"ID {item['track_id']}{' P' if predicted else ''} unknown",
            (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1,
        )
        for start, end in zip(item["trajectory_xy"], item["trajectory_xy"][1:]):
            cv2.line(annotated, tuple(start), tuple(end), (0, 220, 255), 2)
    cv2.putText(
        annotated, f"MOG2 + Kalman | frame {frame_index} | {timestamp_ms / 1000:.2f}s",
        (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
    )
    return annotated


def main() -> None:
    args = parse_args()
    is_live = args.source.startswith(("http://", "https://", "rtsp://"))
    capture = cv2.VideoCapture(args.source)
    if not capture.isOpened():
        raise SystemExit(f"Could not open video source: {args.source}")

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
    # MP4 writers require even dimensions. The same size is used for every output.
    width -= width % 2
    height -= height % 2
    if width < 2 or height < 2:
        capture.release()
        raise SystemExit("Video dimensions are too small")

    args.output.mkdir(parents=True, exist_ok=True)
    writer = None
    if args.save_video:
        writer = cv2.VideoWriter(
            str(args.output / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
            fps, (width, height),
        )
        if not writer.isOpened():
            capture.release()
            raise SystemExit("Could not create output video")

    mog2 = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=24, detectShadows=True)
    tracker = KalmanBlobTracker(args.max_distance)
    preview = DebugPreview(
        args.show, "TrafficMonitor - MOG2 + Kalman", show_mask=True,
        snapshot_dir=str(args.output / "snapshots"),
    )
    meter = ProcessingMeter(fps)
    frame_index = 0
    observed_count = 0
    predicted_count = 0
    frames_without_blobs = 0
    max_simultaneous = 0
    distinct_ids: set[int] = set()
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
                raw_mask = mog2.apply(frame)
                mask = clean_mask(cv2.inRange(raw_mask, 254, 255))
                boxes = boxes_from_mask(mask, args.min_area)
                records = [observation(item) for item in tracker.update(boxes)]
                timestamp_ms = (
                    round((time.perf_counter() - started) * 1000) if is_live
                    else round(frame_index * 1000 / fps)
                )
                sink.write(json.dumps({
                    "camera_id": "CAM_01",
                    "frame_index": frame_index,
                    "video_timestamp_ms": timestamp_ms,
                    "processing_size": [width, height],
                    "tracks": records,
                }, ensure_ascii=False) + "\n")

                annotated = draw_tracks(frame, records, frame_index, timestamp_ms)
                if writer is not None:
                    writer.write(annotated)
                distinct_ids.update(item["track_id"] for item in records)
                observed_count += sum(item["observation_kind"] == "detection" for item in records)
                predicted_count += sum(item["observation_kind"] == "kalman_prediction" for item in records)
                frames_without_blobs += not boxes
                max_simultaneous = max(max_simultaneous, len(records))
                frame_index += 1
                stats = meter.sample(time.perf_counter() - frame_started)
                if not preview.show(frame, annotated, mask=mask, stats=stats):
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
        "algorithm": "MOG2 foreground + Kalman blob tracking (independent baseline)",
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
        "total_confirmed_observations": observed_count,
        "kalman_only_predictions": predicted_count,
        "frames_without_blobs": frames_without_blobs,
        "settings": {"min_area": args.min_area, "max_distance": args.max_distance},
        "warning": "Motion blobs are not verified vehicles or traffic violations.",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
