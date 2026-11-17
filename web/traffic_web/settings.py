"""Django settings for traffic_web project.
"""
import os
from pathlib import Path

# BASE_DIR is TrafficMonitor_IoT/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get(
    "TRAFFIC_SECRET_KEY", "django-insecure-dev-only-local-runserver"
)
DEBUG = os.environ.get("TRAFFIC_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("TRAFFIC_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "monitor.apps.MonitorConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "traffic_web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.template.context_processors.media",
            ],
        },
    },
]

WSGI_APPLICATION = "traffic_web.wsgi.application"
ASGI_APPLICATION = "traffic_web.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "outputs" / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
