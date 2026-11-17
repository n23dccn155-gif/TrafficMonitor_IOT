"""Subprocess tracking job execution service.
Strictly 1 CPU job at a time, mapping --output/--output-dir without --show.
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

from ..models import TrackingJob


class JobManager:
    _lock = threading.Lock()
    _active_job_id: Optional[str] = None

    @classmethod
    def get_active_job_id(cls) -> Optional[str]:
        return cls._active_job_id

    @classmethod
    def start_job(
        cls,
        source_name: str,
        algorithm: str = "3",
        width: int = 1280,
        tile_imgsz: int = 640,
    ) -> TrackingJob:
        # Determine source path
        raw_dir = settings.DATA_RAW_DIR
        source_path = (raw_dir / os.path.basename(source_name)).resolve()
        if not source_path.is_file() and not source_name.startswith(("http://", "https://", "rtsp://")):
            raise FileNotFoundError(f"Source file not found: {source_name}")

        run_id = f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
        output_dir = settings.BASE_DIR / "outputs" / "runs" / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        job = TrackingJob.objects.create(
            job_id=run_id,
            source_path=str(source_path if source_path.is_file() else source_name),
            algorithm=str(algorithm),
            width=int(width),
            tile_imgsz=int(tile_imgsz),
            status="QUEUED",
            output_dir=str(output_dir),
        )

        # Launch in background worker thread
        t = threading.Thread(target=cls._run_worker, args=(job.job_id,), daemon=True)
        t.start()
        return job

    @classmethod
    def _run_worker(cls, job_id: str) -> None:
        with cls._lock:
            cls._active_job_id = job_id
            job = TrackingJob.objects.get(job_id=job_id)
            job.status = "RUNNING"
            job.save()

            project_root = settings.BASE_DIR
            venv_py = project_root / ".venv" / "Scripts" / "python.exe"
            py_exe = str(venv_py) if venv_py.is_file() else sys.executable

            src_dir = project_root / "src" / "traffic_monitor"

            # Command mapping per prompt contract
            if job.algorithm == "1":
                script = str(src_dir / "tiled_yolo11_camera.py")
                cmd = [
                    py_exe,
                    script,
                    "--source",
                    job.source_path,
                    "--output-dir",
                    job.output_dir,
                    "--width",
                    str(job.width),
                    "--tile-imgsz",
                    str(job.tile_imgsz),
                ]
            elif job.algorithm == "2":
                script = str(src_dir / "motion_camera.py")
                cmd = [
                    py_exe,
                    script,
                    "--source",
                    job.source_path,
                    "--output",
                    job.output_dir,
                    "--width",
                    str(job.width),
                ]
            else:  # Default algo 3: YOLOv8n baseline
                script = str(src_dir / "yolo_camera.py")
                cmd = [
                    py_exe,
                    script,
                    "--source",
                    job.source_path,
                    "--output",
                    job.output_dir,
                    "--width",
                    str(job.width),
                ]

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(project_root),
                )
                stdout, stderr = proc.communicate()

                job.log_text = stdout or ""
                if proc.returncode == 0:
                    job.status = "DONE"
                else:
                    job.status = "FAILED"
                    job.error_text = stderr or f"Process exited with code {proc.returncode}"
            except Exception as e:
                job.status = "FAILED"
                job.error_text = str(e)
            finally:
                job.finished_at = timezone.now()
                job.save()
                cls._active_job_id = None
