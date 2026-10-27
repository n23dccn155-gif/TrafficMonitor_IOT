"""Small OpenCV preview for comparing raw and annotated P0 frames."""

from __future__ import annotations

from collections import deque

import cv2


class ProcessingMeter:
    """Rolling processing speed, excluding time spent paused in the viewer."""

    def __init__(self, source_fps: float, window: int = 30) -> None:
        self.source_fps = source_fps
        self.samples = deque(maxlen=window)

    def sample(self, elapsed_seconds: float) -> str:
        self.samples.append(max(elapsed_seconds, 0.000001))
        process_fps = len(self.samples) / sum(self.samples)
        ratio = self.source_fps / process_fps if process_fps else 0
        return (
            f"SOURCE {self.source_fps:.1f} FPS | PROCESS {process_fps:.1f} FPS"
            f" | {ratio:.1f}x slower than source"
        )


class DebugPreview:
    def __init__(self, enabled: bool, title: str, show_mask: bool = False, snapshot_dir=None) -> None:
        self.enabled = enabled
        self.title = title
        self.show_mask = show_mask
        self.snapshot_dir = snapshot_dir
        self.paused = False
        self.mask_title = f"{title} - motion mask"
        self._last_combined = None
        if enabled:
            try:
                cv2.namedWindow(title, cv2.WINDOW_NORMAL)
                if show_mask:
                    cv2.namedWindow(self.mask_title, cv2.WINDOW_NORMAL)
            except cv2.error as exc:
                print(f"Preview unavailable; continuing with saved video: {exc}")
                self.enabled = False

    def _save_snapshot(self):
        if self._last_combined is not None and self.snapshot_dir:
            import os, time
            os.makedirs(self.snapshot_dir, exist_ok=True)
            ts = int(time.time() * 1000)
            path = os.path.join(self.snapshot_dir, f"snapshot_{ts}.jpg")
            cv2.imwrite(path, self._last_combined)
            print(f"  [Snapshot saved] -> {path}")

    def show(self, raw, annotated, mask=None, stats: str | None = None) -> bool:
        """Return False when the viewer presses Q/Escape, otherwise continue."""
        if not self.enabled:
            return True
        try:
            panel_width = min(640, raw.shape[1])
            panel_height = round(raw.shape[0] * panel_width / raw.shape[1])
            left = cv2.resize(raw, (panel_width, panel_height))
            right = cv2.resize(annotated, (panel_width, panel_height))
            combined = cv2.hconcat((left, right))
            cv2.rectangle(combined, (0, 0), (combined.shape[1], 25), (0, 0, 0), -1)
            cv2.putText(
                combined,
                "RAW INPUT",
                (8, 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
            )
            cv2.putText(
                combined,
                "DEBUG OUTPUT   SPACE pause | N next | S snapshot | Q quit",
                (panel_width + 8, 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
            )
            if stats:
                cv2.rectangle(
                    combined, (0, combined.shape[0] - 28),
                    (combined.shape[1], combined.shape[0]), (0, 0, 0), -1,
                )
                cv2.putText(
                    combined, stats, (8, combined.shape[0] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                )
            self._last_combined = combined
            cv2.imshow(self.title, combined)
            if self.show_mask and mask is not None:
                cv2.imshow(self.mask_title, mask)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                return False
            if key in (ord("s"), ord("S")):
                self._save_snapshot()
            if key == ord(" "):
                self.paused = not self.paused
            while self.paused:
                key = cv2.waitKey(30) & 0xFF
                if key in (ord("q"), 27):
                    return False
                if key in (ord("s"), ord("S")):
                    self._save_snapshot()
                if key == ord("n"):
                    return True
                if key == ord(" "):
                    self.paused = False
            return True
        except cv2.error as exc:
            print(f"Preview closed or unavailable; continuing with saved video: {exc}")
            self.close()
            return True

    def close(self) -> None:
        if self.enabled:
            try:
                cv2.destroyAllWindows()
                # Bơm thêm 1 vòng event queue để Windows hủy cửa sổ sạch,
                # tránh treo "Not Responding" sau khi bấm Q/Escape.
                cv2.waitKey(1)
            except cv2.error:
                pass
            self.enabled = False
