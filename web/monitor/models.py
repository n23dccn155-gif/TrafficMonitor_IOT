"""Database models for TrafficMonitor IoT.
Stores video metadata, tracking jobs, scene configurations, signal timelines, and violation events.
"""
from django.db import models


class VideoAsset(models.Model):
    filename = models.CharField(max_length=255, unique=True)
    duration_ms = models.IntegerField(default=0)
    fps = models.FloatField(default=30.0)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.width}x{self.height}, {self.fps} fps)"

    def to_dict(self):
        return {
            "filename": self.filename,
            "duration_ms": self.duration_ms,
            "fps": round(self.fps, 2),
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TrackingJob(models.Model):
    STATUS_CHOICES = [
        ("QUEUED", "Queued"),
        ("RUNNING", "Running"),
        ("DONE", "Done"),
        ("FAILED", "Failed"),
    ]

    job_id = models.CharField(max_length=128, primary_key=True)
    source_path = models.CharField(max_length=512)
    algorithm = models.CharField(max_length=32, default="3")
    width = models.IntegerField(default=1280)
    tile_imgsz = models.IntegerField(default=640)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="QUEUED")
    output_dir = models.CharField(max_length=512, blank=True, default="")
    log_text = models.TextField(blank=True, default="")
    error_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Job {self.job_id} [{self.status}] algo={self.algorithm}"

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "source_path": self.source_path,
            "algorithm": self.algorithm,
            "width": self.width,
            "tile_imgsz": self.tile_imgsz,
            "status": self.status,
            "output_dir": self.output_dir,
            "log_text": self.log_text[-1000:] if self.log_text else "",
            "error_text": self.error_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class SceneConfigRecord(models.Model):
    scene_id = models.CharField(max_length=128)
    version = models.IntegerField(default=1)
    source_id = models.CharField(max_length=255)
    data_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scene_id", "version")

    def __str__(self):
        return f"{self.scene_id} (v{self.version}) for {self.source_id}"

    def to_dict(self):
        data = dict(self.data_json)
        data["scene_id"] = self.scene_id
        data["version"] = self.version
        data["source_id"] = self.source_id
        return data


class SignalTimelineRecord(models.Model):
    timeline_id = models.CharField(max_length=128)
    version = models.IntegerField(default=1)
    video_id = models.CharField(max_length=255)
    mode = models.CharField(max_length=32, default="simulation")
    data_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("timeline_id", "version")

    def __str__(self):
        return f"{self.timeline_id} (v{self.version}) - {self.mode}"

    def to_dict(self):
        data = dict(self.data_json)
        data["timeline_id"] = self.timeline_id
        data["version"] = self.version
        data["video_id"] = self.video_id
        data["mode"] = self.mode
        return data


class RuleRunRecord(models.Model):
    rule_run_id = models.CharField(max_length=128, primary_key=True)
    tracking_job = models.ForeignKey(TrackingJob, null=True, blank=True, on_delete=models.SET_NULL)
    scene_config = models.ForeignKey(SceneConfigRecord, null=True, blank=True, on_delete=models.SET_NULL)
    signal_timeline = models.ForeignKey(SignalTimelineRecord, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RuleRun {self.rule_run_id}"


class ViolationEventRecord(models.Model):
    REVIEW_CHOICES = [
        ("pending", "Chờ duyệt"),
        ("confirmed", "Xác nhận"),
        ("dismissed", "Bác bỏ"),
    ]

    # Ràng buộc chống trùng cứng: primary_key và unique
    event_id = models.CharField(max_length=128, primary_key=True, unique=True)
    rule_run = models.ForeignKey(RuleRunRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    segment_id = models.CharField(max_length=64, default="seg0")
    rule_type = models.CharField(max_length=64)
    track_id = models.IntegerField()
    vehicle_type = models.CharField(max_length=64, default="vehicle")
    event_timestamp_ms = models.IntegerField()
    bbox_xyxy = models.JSONField(default=list)
    scene_config_version = models.IntegerField(default=1)
    signal_source = models.CharField(max_length=64, default="simulation")
    reason = models.TextField(blank=True, default="")
    full_image_path = models.CharField(max_length=512, blank=True, default="")
    crop_image_path = models.CharField(max_length=512, blank=True, default="")
    review_status = models.CharField(max_length=32, choices=REVIEW_CHOICES, default="pending")
    review_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_timestamp_ms"]

    def __str__(self):
        return f"Event {self.event_id} ({self.rule_type}, trk={self.track_id}, {self.review_status})"

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "rule_run_id": self.rule_run_id,
            "segment_id": self.segment_id,
            "rule_type": self.rule_type,
            "track_id": self.track_id,
            "vehicle_type": self.vehicle_type,
            "event_timestamp_ms": self.event_timestamp_ms,
            "bbox_xyxy": self.bbox_xyxy,
            "scene_config_version": self.scene_config_version,
            "signal_source": self.signal_source,
            "reason": self.reason,
            "full_image_path": self.full_image_path,
            "crop_image_path": self.crop_image_path,
            "review_status": self.review_status,
            "review_note": self.review_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
