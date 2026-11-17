"""URL routing for monitor app.
"""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index_view, name="dashboard"),
    # Video APIs
    path("api/videos/", views.video_list_api, name="video_list"),
    path("api/videos/upload/", views.video_upload_api, name="video_upload"),
    path("api/videos/<str:filename>/stream/", views.video_stream_api, name="video_stream"),
    path("api/videos/<str:filename>/snapshot/", views.video_snapshot_api, name="video_snapshot"),
    # Tracking Jobs APIs
    path("api/tracking/jobs/", views.tracking_jobs_api, name="tracking_jobs"),
    path("api/tracking/runs/", views.tracking_runs_api, name="tracking_runs"),
    path("api/tracking/jobs/<str:job_id>/", views.tracking_job_detail_api, name="tracking_job_detail"),
    path("api/tracking/runs/<str:run_id>/tracks/", views.track_window_api, name="track_window"),
    # Scene Config APIs
    path("api/scene-configs/", views.scene_configs_api, name="scene_configs"),
    # Signal Timeline APIs
    path("api/signal-timelines/", views.signal_timelines_api, name="signal_timelines"),
    path("api/arduino/signal/", views.arduino_signal_api, name="arduino_signal"),
    # Rules & Events APIs
    path("api/rules/run/", views.rules_run_api, name="rules_run"),
    path("api/events/", views.events_list_api, name="events_list"),
    path("api/events/<str:event_id>/review/", views.event_review_api, name="event_review"),
    # DroidCam Live APIs
    path("api/live/connect/", views.live_connect_api, name="live_connect"),
    path("api/live/preview/", views.live_preview_api, name="live_preview"),
    path("api/live/status/", views.live_status_api, name="live_status"),
    path("api/live/processing/", views.live_processing_api, name="live_processing"),
    path("api/live/phase/", views.live_phase_api, name="live_phase"),
]
