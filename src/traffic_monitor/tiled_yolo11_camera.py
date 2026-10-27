"""Pipeline số 1 đã chọn: Tiled YOLO11s (2x2 grid, 960px) + ByteTrack (supervision).

Tối ưu phát hiện xe máy nhỏ góc camera trên cao và duy trì ID ổn định.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
import supervision as sv
import torch
from ultralytics import YOLO

from debug_preview import DebugPreview, ProcessingMeter
from model_assets import ensure_official_weights

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = "yolo11s.pt"
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tiled YOLO11 + ByteTrack on one MP4 camera")
    parser.add_argument("--source", required=True, help="Input MP4 path")
    parser.add_argument("--output-dir", required=True, help="Output directory for tracks.jsonl and summary.json")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--tile-imgsz", type=int, default=960)
    parser.add_argument("--frame-skip", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--show", action="store_true", help="Show raw and annotated frames live")
    parser.add_argument("--save-video", action="store_true", help="Also write annotated.mp4")
    args = parser.parse_args()
    args.weights = Path(args.weights)
    is_live = args.source.startswith(("http://", "https://", "rtsp://"))
    if not is_live and not Path(args.source).is_file():
        parser.error(f"Input video not found: {args.source}")
    if str(args.weights) != DEFAULT_WEIGHTS and not args.weights.is_file():
        parser.error(f"Model weights not found: {args.weights}")
    if args.width <= 0 or args.tile_imgsz <= 0 or args.frame_skip <= 0:
        parser.error("--width, --tile-imgsz and --frame-skip must be positive")
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("--max-frames must be positive")
    return args


def main() -> None:
    args = parse_args()
    run_tiled_yolo11(
        args.source,
        output_dir=args.output_dir,
        weights_path=args.weights,
        width=args.width,
        tile_imgsz=args.tile_imgsz,
        frame_skip=args.frame_skip,
        show=args.show,
        save_video=args.save_video,
        max_frames=args.max_frames,
    )


def tile_boxes(model, frame, tile_imgsz=960, tile_overlap=0.15, conf=0.25, iou=0.70, device="cpu"):
    H, W = frame.shape[:2]
    detections = []
    for ty in range(2):
        for tx in range(2):
            x1 = max(0, int(tx * W / 2) - int(tile_overlap * W / 2))
            x2 = min(W, int((tx + 1) * W / 2) + int(tile_overlap * W / 2))
            y1 = max(0, int(ty * H / 2) - int(tile_overlap * H / 2))
            y2 = min(H, int((ty + 1) * H / 2) + int(tile_overlap * H / 2))
            crop = frame[y1:y2, x1:x2]
            results = model.predict(
                crop, imgsz=tile_imgsz, conf=conf, iou=iou, verbose=False, device=device
            )[0]
            if results.boxes is None or not len(results.boxes):
                continue
            boxes_xyxy = results.boxes.xyxy.cpu().numpy()
            scores = results.boxes.conf.cpu().numpy()
            classes = results.boxes.cls.cpu().numpy().astype(int)
            mask = np.isin(classes, list(VEHICLE_CLASSES.keys()))
            if not np.any(mask):
                continue
            boxes_xyxy = boxes_xyxy[mask] + np.array([x1, y1, x1, y1])
            scores = scores[mask]
            classes = classes[mask]
            for (bx1, by1, bx2, by2), score, cls_id in zip(boxes_xyxy, scores, classes):
                detections.append([float(bx1), float(by1), float(bx2), float(by2), float(score), int(cls_id)])
    return detections


def run_tiled_yolo11(
    source_path: str,
    output_dir: str | Path,
    weights_path: str | Path = DEFAULT_WEIGHTS,
    width: int = 1280,
    tile_imgsz: int = 960,
    frame_skip: int = 1,
    show: bool = True,
    save_video: bool = False,
    max_frames: int | None = None,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    snapshot_dir = output_path / "snapshots"

    model_path = ensure_official_weights(str(weights_path)) if str(weights_path) == DEFAULT_WEIGHTS else Path(weights_path)
    model = YOLO(str(model_path))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise RuntimeError(f"Không thể mở nguồn video: {source_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    first_frame = None
    if orig_w <= 0 or orig_h <= 0:
        ok, first_frame = cap.read()
        if ok and first_frame is not None:
            orig_h, orig_w = first_frame.shape[:2]
    if orig_w <= 0 or orig_h <= 0:
        cap.release()
        raise RuntimeError(f"Không đọc được frame đầu từ nguồn: {source_path}")
    proc_w = min(width, orig_w)
    proc_h = round(orig_h * proc_w / orig_w)

    # Khi bỏ frame (frame_skip=N), tracker chỉ thấy 1/N video FPS nên
    # frame_rate của tracker phải gọi theo tốc độ frame đã qua xử lý.
    tracker = sv.ByteTrack(
        track_activation_threshold=0.25,
        lost_track_buffer=50,
        minimum_matching_threshold=0.75,
        frame_rate=max(1, int(round(fps / frame_skip))),
    )

    preview = DebugPreview(show, "TrafficMonitor — Pipeline 1: YOLO11s Tiling + ByteTrack", snapshot_dir=str(snapshot_dir))
    meter = ProcessingMeter(fps)
    writer = None
    if save_video:
        writer = cv2.VideoWriter(
            str(output_path / "annotated.mp4"),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (proc_w, proc_h),
        )

    jsonl_file = open(output_path / "tracks.jsonl", "w", encoding="utf-8")

    trajectories = defaultdict(lambda: deque(maxlen=40))
    distinct_ids = set()
    total_observations = 0
    max_simultaneous = 0
    census = defaultdict(int)
    frame_index = 0
    t0 = time.time()

    print(f"\n[Bắt đầu] Đang xử lý: {source_path}")
    print(
        f"  (Cấu hình: width={proc_w}, tile_imgsz={tile_imgsz}, frame_skip={frame_skip})"
    )
    print("  (Phím trong cửa sổ: Space = Tạm dừng, N = 1 Frame, S = Chụp ảnh, Q/Esc = Dừng)")

    frame_skip = max(1, int(frame_skip))
    physical_index = 0

    try:
        while max_frames is None or frame_index < max_frames:
            frame_started = time.perf_counter()
            if first_frame is not None:
                ok, raw_frame = True, first_frame
                first_frame = None
            else:
                ok, raw_frame = cap.read()
            if not ok or raw_frame is None:
                break
            phys_no = physical_index
            physical_index += 1
            if phys_no % frame_skip != 0:
                continue  # bỏ qua frame nhưng không đóng/mở tracker

            frame = cv2.resize(raw_frame, (proc_w, proc_h)) if (orig_w, orig_h) != (proc_w, proc_h) else raw_frame
            raw_detections = tile_boxes(model, frame, tile_imgsz=tile_imgsz, tile_overlap=0.15, device=device)

            if len(raw_detections):
                xyxy = np.array([d[:4] for d in raw_detections], dtype=np.float32)
                conf = np.array([d[4] for d in raw_detections], dtype=np.float32)
                cls_id = np.array([d[5] for d in raw_detections], dtype=int)
                sv_dets = sv.Detections(xyxy=xyxy, confidence=conf, class_id=cls_id)
                sv_dets = sv_dets.with_nms(threshold=0.50)
                tracked_dets = tracker.update_with_detections(sv_dets)
            else:
                tracked_dets = sv.Detections.empty()

            records = []
            timestamp_ms = round(phys_no * 1000 / fps)

            if len(tracked_dets) and tracked_dets.tracker_id is not None:
                for bx, conf_score, cid, tid in zip(
                    tracked_dets.xyxy, tracked_dets.confidence, tracked_dets.class_id, tracked_dets.tracker_id
                ):
                    if tid is None:
                        continue
                    tid = int(tid)
                    vtype = VEHICLE_CLASSES.get(int(cid), "vehicle")
                    gx = int((bx[0] + bx[2]) / 2)
                    gy = int(bx[3])
                    trajectories[tid].append([gx, gy])
                    distinct_ids.add(tid)
                    census[vtype] += 1
                    records.append({
                        "track_id": tid,
                        "vehicle_type": vtype,
                        "bbox_xyxy": [int(b) for b in bx],
                        "ground_point_xy": [gx, gy],
                        "trajectory_xy": list(trajectories[tid]),
                        "track_quality": "confirmed",
                        "observation_kind": "detection",
                    })

            jsonl_file.write(
                json.dumps({
                    "camera_id": "CAM_01",
                    "frame_index": frame_index,
                    "video_timestamp_ms": timestamp_ms,
                    "processing_size": [proc_w, proc_h],
                    "tracks": records,
                }, ensure_ascii=False) + "\n"
            )

            annotated = frame.copy()
            for rec in records:
                x1, y1, x2, y2 = rec["bbox_xyxy"]
                color = (0, 255, 100) if rec["vehicle_type"] == "motorcycle" else (0, 200, 255)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    annotated,
                    f"ID {rec['track_id']} {rec['vehicle_type']}",
                    (x1, max(18, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    color,
                    1,
                )
                trail = rec["trajectory_xy"]
                for p1, p2 in zip(trail, trail[1:]):
                    cv2.line(annotated, tuple(p1), tuple(p2), (255, 255, 0), 2)

            cv2.putText(
                annotated,
                f"Pipeline 1 (YOLO11s Tiling, skip {frame_skip}) | f{frame_index} | t{phys_no} | IDs: {len(distinct_ids)} | obs: {len(records)}",
                (12, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (255, 255, 255),
                2,
            )

            if writer is not None:
                writer.write(annotated)

            max_simultaneous = max(max_simultaneous, len(records))
            total_observations += len(records)
            frame_index += 1

            stats = meter.sample(time.perf_counter() - frame_started)
            if not preview.show(frame, annotated, stats=stats):
                print("\n[Dừng] Người dùng đã nhấn phím dừng hiển thị.")
                break

    finally:
        cap.release()
        if writer is not None:
            writer.release()
        jsonl_file.close()
        preview.close()

    elapsed = max(0.001, time.time() - t0)
    summary = {
        "source": str(source_path),
        "weights": str(model_path.resolve()),
        "device": device,
        "processed_frames": frame_index,
        "source_fps": fps,
        "read_frames": physical_index,
        "skipped_frames": physical_index - frame_index,
        "elapsed_seconds": round(elapsed, 2),
        "fps": round(frame_index / elapsed, 2),
        "processing_config": {
            "width": proc_w,
            "tile_imgsz": tile_imgsz,
            "frame_skip": frame_skip,
        },
        "distinct_track_ids": len(distinct_ids),
        "max_simultaneous_tracks": max_simultaneous,
        "total_observations": total_observations,
        "vehicle_census": dict(census),
    }

    with open(output_path / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n[Hoàn tất] {frame_index} frames | {summary['fps']} FPS | {len(distinct_ids)} distinct IDs")
    print(f"  Kết quả lưu tại: {output_path}")
    return summary


if __name__ == "__main__":
    main()
