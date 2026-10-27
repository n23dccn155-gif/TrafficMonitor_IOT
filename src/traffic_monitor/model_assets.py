"""Locate or download the two official model checkpoints used by the menu."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS_DIR = PROJECT_ROOT / "weights"
OFFICIAL_WEIGHTS = frozenset({"yolo11s.pt", "yolov8n.pt"})


def ensure_official_weights(name: str) -> Path:
    if name not in OFFICIAL_WEIGHTS:
        raise ValueError(f"Unsupported model checkpoint: {name}")
    target = WEIGHTS_DIR / name
    if target.is_file():
        if target.stat().st_size < 100_000:
            raise RuntimeError(f"Model file appears incomplete: {target}")
        return target

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Model] First use: downloading official {name} to {target}", flush=True)
    try:
        from ultralytics.utils.downloads import attempt_download_asset

        downloaded = Path(attempt_download_asset(target, repo="ultralytics/assets", release="v8.4.0"))
    except Exception as exc:
        raise RuntimeError(
            f"Could not download {name}. Check internet access, then retry; "
            f"or place the official checkpoint at {target}."
        ) from exc
    if not downloaded.is_file() or downloaded.stat().st_size < 100_000:
        raise RuntimeError(f"Model download failed or is incomplete: {target}")
    return downloaded
