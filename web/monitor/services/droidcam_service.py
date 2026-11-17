"""DroidCam live streaming reader and mock disconnect tester.
Single backend thread reads latest frame with 0-buffer latency,
automatic reconnection, thread-safe release, and direct HTTP snapshot fallback.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional, Tuple
from urllib.parse import urlparse

import cv2
import numpy as np


def normalize_droidcam_url(url: str) -> str:
    """Normalize input URL for DroidCam or RTSP stream."""
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("mock:"):
        return url

    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("rtsp://")):
        url = "http://" + url

    try:
        p = urlparse(url)
        # If user only typed http://192.168.1.12:4747 without path, append /video
        if (p.port == 4747 or "4747" in p.netloc) and (not p.path or p.path == "/"):
            url = f"{p.scheme}://{p.netloc}/video"
    except Exception:
        pass

    return url


class DroidCamManager:
    _instance: Optional[DroidCamManager] = None
    _lock = threading.Lock()

    def __init__(self):
        self.url = ""
        self.connected = False
        self.is_mock = False
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_timestamp_ms: int = 0
        self.dropped_frames: int = 0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None

    @classmethod
    def get_instance(cls) -> DroidCamManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = DroidCamManager()
            return cls._instance

    def connect(self, url: str) -> dict:
        """Connect to stream with clean teardown of prior session and immediate state reset."""
        normalized_url = normalize_droidcam_url(url)
        if not normalized_url:
            raise ValueError("Bạn chưa nhập địa chỉ camera")
        if normalized_url == self.url and self.get_status()["connected"]:
            return {"status": "connected", "mode": "mock" if self.is_mock else "real", "url": self.url}
        self.stop()
        self.url = normalized_url
        self._stop_event = threading.Event()
        stop_event = self._stop_event

        # Reset state completely so no old frame is ever served
        with self._lock:
            self.connected = False
            self.latest_frame = None
            self.latest_timestamp_ms = 0
            self.dropped_frames = 0

        if self.url == "mock://droidcam":
            self.is_mock = True
            self.connected = True
            self._thread = threading.Thread(target=self._mock_worker, args=(stop_event,), daemon=True)
            self._thread.start()
            # Wait briefly for first mock frame
            for _ in range(10):
                if self.latest_frame is not None:
                    break
                time.sleep(0.05)
            return {"status": "connected", "mode": "mock", "url": self.url}

        # Real DroidCam connection
        self.is_mock = False
        self._thread = threading.Thread(target=self._real_worker, args=(self.url, stop_event), daemon=True)
        self._thread.start()

        # Give the worker up to 1.5s to establish connection and grab frame 1
        for _ in range(15):
            if self.connected and self.latest_frame is not None:
                break
            time.sleep(0.1)

        # If OpenCV is still negotiating, also try direct HTTP snapshot
        if self.latest_frame is None and self.url.startswith("http"):
            direct_frame = self._fetch_direct_snapshot(self.url)
            if direct_frame is not None and not stop_event.is_set():
                with self._lock:
                    if self._stop_event is stop_event:
                        self.latest_frame = direct_frame
                        self.latest_timestamp_ms = int(time.time() * 1000)
                        self.connected = True

        status = "connected" if self.get_status()["connected"] else "connecting"
        return {"status": status, "mode": "real", "url": self.url}

    @staticmethod
    def _snapshot_candidates(url: str) -> list[str]:
        if not url or not url.startswith("http"):
            return []
        try:
            p = urlparse(url)
            base = f"{p.scheme}://{p.netloc}"
            return [
                f"{base}/cam/1/frame.jpg",
                f"{base}/frame.jpg",
                f"{base}/cam/0/frame.jpg",
                f"{base}/snapshot",
            ]
        except Exception:
            return []

    @staticmethod
    def _fetch_snapshot_candidate(candidate: str) -> Optional[np.ndarray]:
        try:
            import urllib.request
            req = urllib.request.Request(candidate, headers={"User-Agent": "TrafficMonitor"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status != 200:
                    return None
                data = resp.read()
                if len(data) <= 1000:
                    return None
                arr = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None and frame.size > 0:
                    return frame
        except Exception:
            pass
        return None

    def _fetch_direct_snapshot(self, url: str) -> Optional[np.ndarray]:
        """Fetch a fresh JPEG from the first working DroidCam snapshot endpoint."""
        for candidate in self._snapshot_candidates(url):
            frame = self._fetch_snapshot_candidate(candidate)
            if frame is not None:
                return frame
        return None

    def _real_worker(self, url: str, stop_event: threading.Event) -> None:
        """Worker thread for continuous live capture with zero buffer lag and auto-reconnect."""
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;2000000"

        while not stop_event.is_set():
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self._stop_event is stop_event:
                self._cap = cap
            if stop_event.is_set():
                cap.release()
                break

            if not cap.isOpened():
                cap.release()
                if self._cap is cap:
                    self._cap = None
                with self._lock:
                    if self._stop_event is stop_event:
                        self.connected = False
                # If the video stream is unavailable, keep polling the working
                # snapshot endpoint. A single still followed by reconnect delays
                # made the live preview appear frozen.
                for candidate in self._snapshot_candidates(url):
                    direct = self._fetch_snapshot_candidate(candidate)
                    if direct is None:
                        continue
                    while direct is not None and not stop_event.is_set():
                        with self._lock:
                            if self._stop_event is stop_event:
                                self.latest_frame = direct
                                self.latest_timestamp_ms = int(time.time() * 1000)
                                self.connected = True
                        if stop_event.wait(0.1):
                            break
                        direct = self._fetch_snapshot_candidate(candidate)
                    with self._lock:
                        if self._stop_event is stop_event:
                            self.connected = False
                    break
                stop_event.wait(0.5)
                continue

            with self._lock:
                if self._stop_event is stop_event:
                    self.connected = True

            consecutive_failures = 0
            while not stop_event.is_set():
                ret, frame = cap.read()
                if stop_event.is_set():
                    break
                if not ret or frame is None:
                    consecutive_failures += 1
                    self.dropped_frames += 1
                    if consecutive_failures > 25:  # ~1.2s without frames
                        with self._lock:
                            if self._stop_event is stop_event:
                                self.connected = False
                        break  # Break inner loop to release and reconnect
                    time.sleep(0.04)
                    continue

                consecutive_failures = 0
                with self._lock:
                    if self._stop_event is stop_event:
                        self.latest_frame = frame
                        self.latest_timestamp_ms = int(time.time() * 1000)
                        self.connected = True

                time.sleep(0.005)

            # Cleanup cap before reconnect or exit
            try:
                cap.release()
            except Exception:
                pass
            if self._cap is cap:
                self._cap = None

            if stop_event.is_set():
                break

            time.sleep(0.5)

        if self._stop_event is stop_event:
            with self._lock:
                self.connected = False

    def _mock_worker(self, stop_event: threading.Event) -> None:
        frame_idx = 0
        while not stop_event.is_set():
            frame_idx += 1
            # Generate simulated mock camera frame
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            x = (frame_idx * 5) % 500
            cv2.rectangle(img, (x, 200), (x + 80, 260), (0, 255, 0), -1)
            cv2.putText(
                img,
                f"DROIDCAM MOCK #{frame_idx} @ {time.strftime('%H:%M:%S')}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            with self._lock:
                if self._stop_event is stop_event and not stop_event.is_set():
                    self.latest_frame = img
                    self.latest_timestamp_ms = int(time.time() * 1000)
            time.sleep(0.033)  # ~30 FPS

    def get_latest_jpeg(self, wait_timeout: float = 0.0, max_age_ms: int = 0) -> Optional[bytes]:
        """Return the latest frame as JPEG bytes.
        If wait_timeout > 0, waits up to that duration for a frame to become available.
        """
        # The camera worker owns network access. A preview request must not open
        # another connection or block Django for several snapshot timeouts.
        if wait_timeout > 0 and self.latest_frame is None:
            deadline = time.time() + wait_timeout
            while time.time() < deadline:
                with self._lock:
                    if self.latest_frame is not None:
                        break
                time.sleep(0.05)

        with self._lock:
            if self.latest_frame is None:
                return None
            if max_age_ms and int(time.time() * 1000) - self.latest_timestamp_ms > max_age_ms:
                return None
            frame = self.latest_frame.copy()
        # JPEG encoding can take tens of milliseconds; never block camera capture.
        success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if success:
            return buffer.tobytes()
        return None

    def get_status(self) -> dict:
        with self._lock:
            age_ms = int(time.time() * 1000) - self.latest_timestamp_ms if self.latest_timestamp_ms > 0 else -1
            return {
                "connected": self.connected and 0 <= age_ms < 2000,
                "url": self.url,
                "is_mock": self.is_mock,
                "frame_age_ms": age_ms,
                "dropped_frames": self.dropped_frames,
            }

    def stop(self) -> None:
        self._stop_event.set()
        # The capture thread owns VideoCapture and releases it after read returns.
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.6)
        self._thread = None
        with self._lock:
            self.connected = False
            self.latest_frame = None
            self.latest_timestamp_ms = 0
