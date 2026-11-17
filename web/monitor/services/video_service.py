"""Video streaming, path safety validation, and snapshot extraction service.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Generator, Optional, Tuple

import cv2
from django.conf import settings
from django.http import Http404, HttpResponse, StreamingHttpResponse

from ..models import VideoAsset

RANGE_RE = re.compile(r"bytes\s*=\s*(\d+)-(\d*)", re.I)


def get_safe_video_path(filename: str) -> Path:
    """Validate that filename resides strictly inside DATA_RAW_DIR.
    Prevents path traversal attacks.
    """
    clean_name = os.path.basename(filename)
    raw_dir = settings.DATA_RAW_DIR.resolve()
    target_path = (raw_dir / clean_name).resolve()

    # Verify that target_path is within raw_dir
    try:
        target_path.relative_to(raw_dir)
    except ValueError:
        raise PermissionError(f"Access denied: path traversal attempt detected for {filename}")

    if not target_path.is_file():
        raise Http404(f"Video file not found: {clean_name}")

    return target_path


def get_video_metadata(file_path: Path) -> dict:
    cap = cv2.VideoCapture(str(file_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_ms = int((frame_count / fps) * 1000) if fps > 0 else 0
    cap.release()
    size_bytes = file_path.stat().st_size
    return {
        "filename": file_path.name,
        "duration_ms": duration_ms,
        "fps": round(fps, 2),
        "width": width,
        "height": height,
        "size_bytes": size_bytes,
    }


def list_raw_videos() -> list:
    raw_dir = settings.DATA_RAW_DIR
    videos = []
    for f in sorted(raw_dir.glob("*.mp4")):
        # Sync or get from VideoAsset
        asset, created = VideoAsset.objects.get_or_create(filename=f.name)
        if created or asset.duration_ms == 0:
            meta = get_video_metadata(f)
            asset.duration_ms = meta["duration_ms"]
            asset.fps = meta["fps"]
            asset.width = meta["width"]
            asset.height = meta["height"]
            asset.size_bytes = meta["size_bytes"]
            asset.save()
        videos.append(asset.to_dict())
    return videos


def file_iterator(file_path: Path, offset: int = 0, length: Optional[int] = None, chunk_size: int = 65536) -> Generator[bytes, None, None]:
    with open(file_path, "rb") as f:
        f.seek(offset, os.SEEK_SET)
        remaining = length
        while True:
            read_size = chunk_size if remaining is None else min(chunk_size, remaining)
            data = f.read(read_size)
            if not data:
                break
            if remaining is not None:
                remaining -= len(data)
            yield data
            if remaining is not None and remaining <= 0:
                break


def stream_video_with_range(request, filename: str) -> HttpResponse:
    """Stream MP4 video with HTTP 206 Partial Content (HTTP Range) support."""
    file_path = get_safe_video_path(filename)
    file_size = file_path.stat().st_size
    range_header = request.META.get("HTTP_RANGE", "").strip()

    range_match = RANGE_RE.match(range_header) if range_header else None
    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else file_size - 1
        if last_byte >= file_size:
            last_byte = file_size - 1
        length = last_byte - first_byte + 1

        response = StreamingHttpResponse(
            file_iterator(file_path, offset=first_byte, length=length),
            status=206,
            content_type="video/mp4",
        )
        response["Content-Range"] = f"bytes {first_byte}-{last_byte}/{file_size}"
        response["Content-Length"] = str(length)
    else:
        response = StreamingHttpResponse(
            file_iterator(file_path, offset=0, length=file_size),
            status=200,
            content_type="video/mp4",
        )
        response["Content-Length"] = str(file_size)

    response["Accept-Ranges"] = "bytes"
    return response


def extract_snapshot_jpeg(filename: str, at_ms: int = 0) -> Optional[bytes]:
    if filename in ("live", "droidcam") or filename.startswith("http"):
        from .droidcam_service import DroidCamManager
        mgr = DroidCamManager.get_instance()
        jpeg = mgr.get_latest_jpeg(wait_timeout=2.5, max_age_ms=2000)
        if jpeg:
            return jpeg
        return None

    file_path = get_safe_video_path(filename)
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return None

    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, at_ms))
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return None

    success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if success:
        return buffer.tobytes()
    return None
