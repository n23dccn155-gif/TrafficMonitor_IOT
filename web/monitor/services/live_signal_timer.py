"""Server-side traffic signal timer for live detection.

The rule engine reads phases from this timer instead of the Arduino, so every
phase change is recorded at the exact millisecond it was scheduled.

ALL_YELLOW (both roads yellow) pauses detection. Leaving it keeps both roads
yellow for WARMUP_MS more while YOLO restarts, then applies the requested phase.
"""
from __future__ import annotations

from src.traffic_monitor.traffic_rules.schemas import SignalChange, SignalTimeline

from .arduino_signal_service import PHASES

PAUSE_PHASE = "ALL_YELLOW"
WARMUP_MS = 2000
MANUAL_PHASES = PHASES - {"ALL_RED"}  # cả hai đỏ không còn là lựa chọn thủ công
CYCLE = ("A_GREEN", "A_YELLOW", "B_GREEN", "B_YELLOW")  # same order as signal.js
DURATION_LIMITS = {"a_green": (3, 120), "a_yellow": (1, 10), "b_green": (3, 120), "b_yellow": (1, 10)}


def parse_signal_config(data) -> dict:
    """Validate a signal config from the web: timed durations or one manual phase."""
    if not isinstance(data, dict):
        raise ValueError("Cấu hình đèn không hợp lệ")
    mode = data.get("mode")
    if mode == "manual":
        if data.get("phase") not in MANUAL_PHASES:
            raise ValueError("Tín hiệu đèn không hợp lệ")
        return {"mode": "manual", "phase": data["phase"]}
    if mode == "timed":
        config = {"mode": "timed"}
        for name, (lower, upper) in DURATION_LIMITS.items():
            value = data.get(name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"{name} phải trong khoảng {lower}-{upper} giây")
            config[name] = value
        return config
    raise ValueError("Chế độ đèn phải là timed hoặc manual")


class LiveSignalTimer:
    """Phase schedule on the run's clock (ms since detection started)."""

    def __init__(self, timeline: SignalTimeline, config: dict, now_ms: int = 0):
        self.timeline = timeline
        self._pending = None  # (config, due_ms) waiting for YOLO to warm up
        self.configure(config, now_ms)

    def configure(self, config: dict, now_ms: int) -> None:
        """Apply a new config at now_ms, or after the warm-up when leaving the pause."""
        if config == {"mode": "manual", "phase": PAUSE_PHASE}:
            self._pending = None
        elif self.timeline.changes and self.phase == PAUSE_PHASE:
            # Keep the first due time if the user changes their mind during warm-up.
            due_ms = self._pending[1] if self._pending else now_ms + WARMUP_MS
            self._pending = (config, due_ms)
            return
        self._apply(config, now_ms)

    @property
    def paused(self) -> bool:
        """Both roads yellow and no resume pending: detection is stopped."""
        return self.phase == PAUSE_PHASE and self._pending is None

    def _apply(self, config: dict, now_ms: int) -> None:
        self.mode = config["mode"]
        if self.mode == "timed":
            self._steps = [(phase, config[key] * 1000) for phase, key in zip(
                CYCLE, ("a_green", "a_yellow", "b_green", "b_yellow"))]
            self.durations = {key: config[key] for key in DURATION_LIMITS}
            phase = CYCLE[0]
        else:
            self._steps = None
            phase = config["phase"]
        self._next_change_ms = now_ms + self._steps[0][1] if self._steps else None
        self._step_index = 0
        self._record(now_ms, phase)

    @property
    def phase(self) -> str:
        return self.timeline.changes[-1].phase

    def _record(self, at_ms: int, phase: str) -> None:
        if self.timeline.changes and self.timeline.changes[-1].phase == phase:
            return
        seq = len(self.timeline.changes) + 1
        self.timeline.changes.append(SignalChange(at_video_ms=at_ms, phase=phase, source="timer", seq=seq))

    def advance(self, now_ms: int) -> list[str]:
        """Record every scheduled change up to now_ms at its exact time."""
        changed = []
        if self._pending and now_ms >= self._pending[1]:
            config, due_ms = self._pending
            self._pending = None
            self._apply(config, due_ms)
            changed.append(self.phase)
        while self._steps and now_ms >= self._next_change_ms:
            at_ms = self._next_change_ms
            self._step_index = (self._step_index + 1) % len(self._steps)
            phase, duration = self._steps[self._step_index]
            self._next_change_ms = at_ms + duration
            self._record(at_ms, phase)
            changed.append(phase)
        return changed

    def state(self, now_ms: int) -> dict:
        if self._pending:
            remaining = max(0, self._pending[1] - now_ms)
        else:
            remaining = max(0, self._next_change_ms - now_ms) if self._steps else 0
        state = {"mode": self.mode, "phase": self.phase, "remaining_ms": remaining,
                 "paused": self.paused, "warming_up": self._pending is not None}
        if self._steps:
            state["durations"] = dict(self.durations)
        return state
