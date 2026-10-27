"""Visual P0 comparison: MOG2 and adjacent-frame difference, each with Kalman IDs.

This intentionally uses no learned detector. Foreground blobs are not vehicle
classes and may include shadows, people, compression changes, or merged vehicles.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MOG2 vs FrameDiff, both with Kalman tracking")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--min-area", type=int, default=80)
    parser.add_argument("--max-distance", type=float, default=65)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"Input video not found: {args.source}")
    if min(args.width, args.max_frames, args.min_area) <= 0 or args.max_distance <= 0:
        parser.error("Width, max-frames, min-area, and max-distance must be positive")
    return args


@dataclass
class Track:
    track_id: int
    kalman: cv2.KalmanFilter
    bbox: tuple[int, int, int, int]
    hits: int = 1
    missed: int = 0
    trail: deque[tuple[int, int]] = field(default_factory=lambda: deque(maxlen=15))
    predicted_xy: tuple[float, float] = (0.0, 0.0)

    @classmethod
    def from_detection(cls, track_id: int, bbox: tuple[int, int, int, int]) -> "Track":
        x, y, w, h = bbox
        cx, cy = x + w / 2, y + h / 2
        kf = cv2.KalmanFilter(4, 2)
        kf.transitionMatrix = np.array(
            [[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32
        )
        kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        kf.processNoiseCov = np.diag([2, 2, 12, 12]).astype(np.float32)
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 8
        kf.errorCovPost = np.eye(4, dtype=np.float32) * 100
        kf.statePost = np.array([[cx], [cy], [0], [0]], np.float32)
        track = cls(track_id, kf, bbox, predicted_xy=(cx, cy))
        track.trail.append((round(cx), round(cy)))
        return track


class KalmanBlobTracker:
    def __init__(self, max_distance: float) -> None:
        self.max_distance = max_distance
        self.next_id = 1
        self.active: dict[int, Track] = {}
        self.total_created = 0

    def update(self, detections: list[tuple[int, int, int, int]]) -> list[dict]:
        tracks = list(self.active.values())
        for track in tracks:
            predicted = track.kalman.predict()
            track.predicted_xy = (float(predicted[0, 0]), float(predicted[1, 0]))
            track.missed += 1

        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()
        if tracks and detections:
            centers = np.array([(x + w / 2, y + h / 2) for x, y, w, h in detections])
            predicted = np.array([track.predicted_xy for track in tracks])
            distances = np.linalg.norm(predicted[:, None, :] - centers[None, :, :], axis=2)
            rows, cols = linear_sum_assignment(distances)
            for row, col in zip(rows, cols):
                if distances[row, col] > self.max_distance:
                    continue
                track = tracks[row]
                box = detections[col]
                cx, cy = centers[col]
                track.kalman.correct(np.array([[cx], [cy]], np.float32))
                track.bbox = box
                track.hits += 1
                track.missed = 0
                track.trail.append((round(cx), round(cy)))
                matched_tracks.add(track.track_id)
                matched_detections.add(col)

        for index, box in enumerate(detections):
            if index not in matched_detections:
                self.active[self.next_id] = Track.from_detection(self.next_id, box)
                self.next_id += 1
                self.total_created += 1
        for track in tracks:
            if track.track_id not in matched_tracks and track.missed > 5:
                self.active.pop(track.track_id, None)

        records: list[dict] = []
        for track in self.active.values():
            if track.hits < 2:
                continue
            x, y, w, h = track.bbox
            if track.missed:
                cx, cy = track.predicted_xy
                x, y = round(cx - w / 2), round(cy - h / 2)
                kind = "kalman_prediction"
                point = [round(cx), round(cy)]
            else:
                kind = "detection"
                point = list(track.trail[-1])
            records.append(
                {
                    "track_id": track.track_id,
                    "bbox_xyxy": [x, y, x + w, y + h],
                    "center_xy": point,
                    "trajectory_xy": [list(point) for point in track.trail],
                    "hits": track.hits,
                    "observation_kind": kind,
                    "missing_frames": track.missed,
                }
            )
        return records


def clean_mask(mask: np.ndarray) -> np.ndarray:
    mask = cv2.medianBlur(mask, 3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))


def boxes_from_mask(mask: np.ndarray, min_area: int) -> list[tuple[int, int, int, int]]:
    boxes = []
    max_area = mask.size * 0.12
    for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        area = cv2.contourArea(contour)
        if not min_area <= area <= max_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 7 or h < 7 or w > mask.shape[1] * 0.4 or h > mask.shape[0] * 0.4:
            continue
        boxes.append((x, y, w, h))
    return boxes


def panel(
    frame: np.ndarray,
    title: str,
    records: list[dict],
    mask: np.ndarray | None,
    color: tuple[int, int, int],
    frame_index: int,
    timestamp_s: float,
    detection_count: int = 0,
) -> np.ndarray:
    height, width = frame.shape[:2]
    strip_height = 120
    image = np.zeros((height + strip_height, width, 3), np.uint8)
    image[:height] = frame
    for record in records:
        x1, y1, x2, y2 = record["bbox_xyxy"]
        predicted = record["observation_kind"] == "kalman_prediction"
        box_color = (180, 90, 255) if predicted else color
        cv2.rectangle(image, (x1, y1), (x2, y2), box_color, 1)
        cv2.putText(
            image, f"{'P' if predicted else ''}{record['track_id']}",
            (x1, max(45, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, box_color, 1,
        )
        points = record["trajectory_xy"]
        for start, end in zip(points, points[1:]):
            cv2.line(image, tuple(start), tuple(end), color, 1)
    cv2.rectangle(image, (0, 0), (width, 35), (0, 0, 0), -1)
    header = f"{title} | frame {frame_index} | {timestamp_s:.2f}s"
    if mask is not None:
        header += f" | blobs {detection_count} | tracks {len(records)}"
    cv2.putText(image, header, (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (255, 255, 255), 2)
    if mask is not None:
        mask_small = cv2.resize(mask, (width, strip_height), interpolation=cv2.INTER_NEAREST)
        image[height:] = cv2.cvtColor(mask_small, cv2.COLOR_GRAY2BGR)
        cv2.putText(
            image, "MOTION MASK", (12, height + 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
        )
    else:
        cv2.putText(
            image, "WHITE = changed pixels in each method's mask", (12, height + 32),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
        )
        cv2.putText(
            image, "Blob ID is not a vehicle class or violation", (12, height + 72),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
        )
        cv2.putText(
            image, "Purple P = Kalman prediction without a new blob", (12, height + 105),
            cv2.FONT_HERSHEY_SIMPLEX, 0.53, (180, 90, 255), 2,
        )
    return image


def preview_frame(combined: np.ndarray, paused: bool) -> tuple[bool, bool]:
    cv2.imshow("vd2: RAW | MOG2 + Kalman | FrameDiff + Kalman", combined)
    key = cv2.waitKey(30 if paused else 1) & 0xFF
    if key in (ord("q"), 27):
        return False, paused
    if key == ord(" "):
        paused = not paused
    if paused:
        while True:
            key = cv2.waitKey(30) & 0xFF
            if key in (ord("q"), 27):
                return False, paused
            if key == ord("n"):
                return True, paused
            if key == ord(" "):
                return True, False
    return True, paused


def main() -> None:
    args = parse_args()
    cap = cv2.VideoCapture(str(args.source))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {args.source}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    source_size = [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))]
    if fps <= 0 or min(source_size) <= 0:
        cap.release()
        raise SystemExit("Video metadata is incomplete")
    width = min(args.width, source_size[0])
    height = round(source_size[1] * width / source_size[0])
    height -= height % 2  # MP4 codecs require an even video height.
    args.output.mkdir(parents=True, exist_ok=True)
    video_path = args.output / "comparison.mp4"
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width * 3, height + 120)
    )
    if not writer.isOpened():
        cap.release()
        raise SystemExit(f"Could not write video: {video_path}")

    mog2 = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=24, detectShadows=True)
    trackers = {
        "mog2": KalmanBlobTracker(args.max_distance),
        "frame_diff": KalmanBlobTracker(args.max_distance),
    }
    previous_gray = None
    frame_index = 0
    observations = {name: 0 for name in trackers}
    predictions = {name: 0 for name in trackers}
    no_blobs = {name: 0 for name in trackers}
    paused = False
    started = time.perf_counter()
    if args.show:
        cv2.namedWindow("vd2: RAW | MOG2 + Kalman | FrameDiff + Kalman", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("vd2: RAW | MOG2 + Kalman | FrameDiff + Kalman", 1600, 340)
    try:
        with (args.output / "tracks.jsonl").open("w", encoding="utf-8") as sink:
            while frame_index < args.max_frames:
                ok, source_frame = cap.read()
                if not ok:
                    break
                frame = cv2.resize(source_frame, (width, height))
                gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
                raw_mog = mog2.apply(frame)
                mog_mask = clean_mask(cv2.inRange(raw_mog, 254, 255))
                if previous_gray is None:
                    diff_mask = np.zeros_like(mog_mask)
                else:
                    delta = cv2.absdiff(previous_gray, gray)
                    _, diff_mask = cv2.threshold(delta, 22, 255, cv2.THRESH_BINARY)
                    diff_mask = clean_mask(diff_mask)
                previous_gray = gray

                masks = {"mog2": mog_mask, "frame_diff": diff_mask}
                detections = {
                    name: boxes_from_mask(mask, args.min_area) for name, mask in masks.items()
                }
                tracks = {
                    name: trackers[name].update(detections[name]) for name in trackers
                }
                for name in trackers:
                    observations[name] += sum(
                        item["observation_kind"] == "detection" for item in tracks[name]
                    )
                    predictions[name] += sum(
                        item["observation_kind"] == "kalman_prediction" for item in tracks[name]
                    )
                    no_blobs[name] += not detections[name]
                timestamp_s = frame_index / fps
                sink.write(json.dumps({
                    "frame_index": frame_index,
                    "video_timestamp_ms": round(timestamp_s * 1000),
                    "mog2": {"detection_count": len(detections["mog2"]), "tracks": tracks["mog2"]},
                    "frame_diff": {
                        "detection_count": len(detections["frame_diff"]),
                        "tracks": tracks["frame_diff"],
                    },
                }, ensure_ascii=False) + "\n")
                combined = cv2.hconcat((
                    panel(frame, "RAW", [], None, (255, 255, 255), frame_index, timestamp_s),
                    panel(frame, "MOG2 + KALMAN", tracks["mog2"], mog_mask,
                          (0, 230, 0), frame_index, timestamp_s, len(detections["mog2"])),
                    panel(frame, "FRAMEDIFF + KALMAN", tracks["frame_diff"], diff_mask,
                          (0, 190, 255), frame_index, timestamp_s,
                          len(detections["frame_diff"])),
                ))
                writer.write(combined)
                frame_index += 1
                if args.show:
                    keep_going, paused = preview_frame(combined, paused)
                    if not keep_going:
                        break
                if frame_index % 100 == 0:
                    print(f"Processed {frame_index} frames...", flush=True)
    finally:
        cap.release()
        writer.release()
        if args.show:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - started
    summary = {
        "source": str(args.source.resolve()),
        "source_fps": fps,
        "source_size": source_size,
        "processing_size": [width, height],
        "processed_frames": frame_index,
        "processed_seconds_of_video": round(frame_index / fps, 3),
        "elapsed_seconds": round(elapsed, 3),
        "processing_fps": round(frame_index / elapsed, 3) if elapsed else 0,
        "algorithms": {
            "mog2": "OpenCV MOG2 foreground + morphology + contours + Kalman + global assignment",
            "frame_diff": "adjacent grayscale absdiff + threshold 22 + morphology + contours + Kalman + global assignment",
        },
        "settings": {"min_area": args.min_area, "max_distance": args.max_distance},
        "results": {
            name: {
                "created_ids": tracker.total_created,
                "confirmed_observations": observations[name],
                "kalman_only_predictions": predictions[name],
                "frames_without_blobs": no_blobs[name],
            }
            for name, tracker in trackers.items()
        },
        "warning": "Blob IDs are not ground-truth vehicles; no traffic violations are inferred.",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
