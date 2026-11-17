"""Track streaming and windowed query service.
Reads tracks.jsonl without loading entire 10MB+ file into memory.
"""
from __future__ import annotations

import json
import ntpath
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from ..models import TrackingJob


def list_tracking_runs(source_name: str) -> List[Dict[str, Any]]:
    """Return finished local tracking outputs for the selected MP4 only."""
    runs_dir = settings.BASE_DIR / "outputs" / "runs"
    runs = []
    if not source_name or not runs_dir.is_dir():
        return runs
    for run_dir in sorted(runs_dir.glob("run_*"), reverse=True):
        summary_file = run_dir / "summary.json"
        if not summary_file.is_file() or not (run_dir / "tracks.jsonl").is_file():
            continue
        try:
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            if ntpath.basename(str(summary.get("source", ""))) != source_name:
                continue
            processed_frames = int(summary.get("processed_frames", 0))
            source_frames = int(summary.get("source_frames", 0))
            complete = (processed_frames >= source_frames - 1 if source_frames > 0
                        else TrackingJob.objects.filter(job_id=run_dir.name, status="DONE").exists())
            runs.append({
                "run_id": run_dir.name,
                "processed_frames": processed_frames,
                "source_frames": source_frames,
                "processed_seconds": summary.get("processed_seconds_of_video"),
                "complete": complete,
            })
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return sorted(runs, key=lambda run: (run["complete"], run["run_id"]), reverse=True)


def find_run_output_dir(run_id: str) -> Optional[Path]:
    runs_dir = settings.BASE_DIR / "outputs" / "runs"
    target = runs_dir / run_id
    if target.is_dir():
        return target
    return None


def get_windowed_tracks(run_id: str, from_ms: int = 0, to_ms: int = 5000) -> Dict[str, Any]:
    run_dir = find_run_output_dir(run_id)
    if not run_dir:
        return {"run_id": run_id, "tracks": [], "found": False}

    tracks_file = run_dir / "tracks.jsonl"
    if not tracks_file.is_file():
        return {"run_id": run_id, "tracks": [], "found": False}

    frames = []
    with open(tracks_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                frame_data = json.loads(line)
                t_ms = frame_data.get("video_timestamp_ms", 0)
                if from_ms <= t_ms <= to_ms:
                    frames.append(frame_data)
                elif t_ms > to_ms and len(frames) > 0:
                    # Past window, stop reading for efficiency
                    break
            except Exception:
                continue

    summary_file = run_dir / "summary.json"
    summary_data = {}
    if summary_file.is_file():
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
        except Exception:
            pass

    return {
        "run_id": run_id,
        "from_ms": from_ms,
        "to_ms": to_ms,
        "frames_count": len(frames),
        "frames": frames,
        "summary": summary_data,
        "found": True,
    }
