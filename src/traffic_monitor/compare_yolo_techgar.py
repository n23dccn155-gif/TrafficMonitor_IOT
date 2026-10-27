"""Place source, YOLO, and the existing TechGAR output on the same frame index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Make a synchronized three-panel comparison MP4")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--yolo", type=Path, required=True)
    parser.add_argument("--techgar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--panel-width", type=int, default=640)
    args = parser.parse_args()
    for path in (args.source, args.yolo, args.techgar):
        if not path.is_file():
            parser.error(f"Video not found: {path}")
    if args.panel_width <= 0 or (args.max_frames is not None and args.max_frames <= 0):
        parser.error("panel-width and max-frames must be positive")
    return args


def main() -> None:
    args = parse_args()
    paths = [args.source, args.yolo, args.techgar]
    captures = [cv2.VideoCapture(str(path)) for path in paths]
    try:
        if not all(cap.isOpened() for cap in captures):
            raise SystemExit("Could not open all three videos")
        fps_values = [float(cap.get(cv2.CAP_PROP_FPS)) for cap in captures]
        if min(fps_values) <= 0 or max(fps_values) - min(fps_values) > 0.1:
            raise SystemExit(f"FPS mismatch: {fps_values}")
        source_width = int(captures[0].get(cv2.CAP_PROP_FRAME_WIDTH))
        source_height = int(captures[0].get(cv2.CAP_PROP_FRAME_HEIGHT))
        panel_height = round(source_height * args.panel_width / source_width)
        panel_height -= panel_height % 2
        header_height = 38
        args.output.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps_values[0],
            (args.panel_width * 3, panel_height + header_height),
        )
        if not writer.isOpened():
            raise SystemExit(f"Could not create output: {args.output}")
        labels = ("RAW vd3", "YOLOv8n + ByteTrack", "TechGAR MotionVehicleTracker")
        frame_index = 0
        try:
            while args.max_frames is None or frame_index < args.max_frames:
                decoded = [cap.read() for cap in captures]
                if not all(ok for ok, _ in decoded):
                    break
                panels = []
                for label, (_, frame) in zip(labels, decoded):
                    panel = cv2.resize(frame, (args.panel_width, panel_height))
                    header = cv2.copyMakeBorder(
                        panel, header_height, 0, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0)
                    )
                    cv2.putText(
                        header, f"{label} | f{frame_index} | {frame_index / fps_values[0]:.2f}s",
                        (9, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2,
                    )
                    panels.append(header)
                writer.write(cv2.hconcat(panels))
                frame_index += 1
        finally:
            writer.release()
        report = {
            "source": str(args.source.resolve()),
            "yolo": str(args.yolo.resolve()),
            "techgar": str(args.techgar.resolve()),
            "output": str(args.output.resolve()),
            "frames": frame_index,
            "fps": fps_values[0],
            "duration_seconds": round(frame_index / fps_values[0], 3),
            "note": "Panels align by frame index; track IDs are independent across algorithms.",
        }
        args.output.with_suffix(".json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for cap in captures:
            cap.release()


if __name__ == "__main__":
    main()
