"""Evidence capture service.
Extracts 1 panoramic full-frame image with vehicle box/ID + 1 vehicle crop image.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
from django.conf import settings

RULE_LABELS = {
    "wrong_way": "Ngược Chiều",
    "lane_encroachment": "Lấn Vạch",
    "red_light": "Vượt Đèn Đỏ",
}


def violation_rule_label(rule_type: str) -> str:
    return RULE_LABELS.get(rule_type, "Vượt Đèn Đỏ")


def create_violation_evidence(
    video_path: str | Path,
    event_id: str,
    timestamp_ms: int,
    track_id: int,
    bbox_xyxy: List[int],
    rule_type: str = "violation",
) -> Tuple[str, str]:
    """Capture full frame with violation box and vehicle crop.
    Returns (full_image_url, crop_image_url).
    """
    evidence_dir = settings.MEDIA_ROOT / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    full_filename = f"{event_id}_full.jpg"
    crop_filename = f"{event_id}_crop.jpg"

    full_file_path = evidence_dir / full_filename
    crop_file_path = evidence_dir / crop_filename

    # If already created, return safe paths
    if full_file_path.is_file() and crop_file_path.is_file():
        return (f"/media/evidence/{full_filename}", f"/media/evidence/{crop_filename}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return ("", "")

    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, timestamp_ms))
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return ("", "")

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox_xyxy
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(x1 + 1, min(w, int(x2)))
    y2 = max(y1 + 1, min(h, int(y2)))

    # 1. Full image with box and label
    annotated_frame = frame.copy()
    box_color = (0, 0, 255)
    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 3)

    label = f"ID:{track_id} · {violation_rule_label(rule_type)} @ {timestamp_ms}ms"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    cv2.rectangle(annotated_frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), box_color, -1)
    cv2.putText(
        annotated_frame,
        label,
        (x1 + 3, y1 - 4),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(full_file_path), annotated_frame)

    # 2. Crop image with safety margin from annotated frame (enlarged vehicle with box)
    margin = 25
    cx1 = max(0, x1 - margin)
    cy1 = max(0, y1 - margin)
    cx2 = min(w, x2 + margin)
    cy2 = min(h, y2 + margin)

    crop_img = annotated_frame[cy1:cy2, cx1:cx2]
    if crop_img.size > 0:
        cv2.imwrite(str(crop_file_path), crop_img)
    else:
        cv2.imwrite(str(crop_file_path), annotated_frame[y1:y2, x1:x2])

    return (f"/media/evidence/{full_filename}", f"/media/evidence/{crop_filename}")
