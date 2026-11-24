"""Signal timeline generation with the same safety rule as the Uno firmware.
Handing right of way to the other road always runs own yellow -> ALL_RED -> target.
Real hardware is driven only by web/monitor/services/arduino_signal_service.py.
"""
from __future__ import annotations

from typing import List

from .schemas import SignalChange, SignalTimeline

VALID_PHASES = {"A_GREEN", "A_YELLOW", "ALL_RED", "B_GREEN", "B_YELLOW", "ALL_YELLOW"}


class TimelineGenerator:
    """Generates strictly safe signal sequences with zero concurrent greens."""

    @staticmethod
    def generate_timed(
        duration_ms: int,
        a_green_sec: float = 15.0,
        b_green_sec: float = 15.0,
        yellow_sec: float = 3.0,
        all_red_sec: float = 3.0,
        video_id: str = "video.mp4",
        timeline_id: str = "timed_simulation",
    ) -> SignalTimeline:
        if any(t <= 0 for t in (a_green_sec, b_green_sec, yellow_sec, all_red_sec)):
            raise ValueError("All phase durations must be strictly positive (> 0)")

        changes: List[SignalChange] = []
        t_ms = 0
        seq = 1

        cycle_sequence = [
            ("A_GREEN", int(a_green_sec * 1000)),
            ("A_YELLOW", int(yellow_sec * 1000)),
            ("ALL_RED", int(all_red_sec * 1000)),
            ("B_GREEN", int(b_green_sec * 1000)),
            ("B_YELLOW", int(yellow_sec * 1000)),
            ("ALL_RED", int(all_red_sec * 1000)),
        ]

        # Verify safety invariant
        for phase, _ in cycle_sequence:
            assert phase in VALID_PHASES, f"Invalid phase: {phase}"

        while t_ms < duration_ms:
            for phase, duration in cycle_sequence:
                if t_ms >= duration_ms:
                    break
                changes.append(
                    SignalChange(
                        at_video_ms=t_ms,
                        phase=phase,
                        source="simulation",
                        seq=seq,
                    )
                )
                seq += 1
                t_ms += duration

        return SignalTimeline(
            timeline_id=timeline_id,
            version=1,
            video_id=video_id,
            mode="simulation",
            changes=changes,
        )

    @staticmethod
    def create_manual_transition(
        current_phase: str,
        requested_group: str,  # "A" or "B" or "ALL_RED"
        at_video_ms: int,
        yellow_sec: float = 3.0,
        all_red_sec: float = 3.0,
        start_seq: int = 1,
    ) -> List[SignalChange]:
        """Generate safe transition sequence between groups.
        Never transitions directly from A_GREEN to B_GREEN; leaving ALL_YELLOW for a
        green also passes through ALL_RED first.
        """
        current_phase = current_phase or "UNKNOWN"
        steps: List[tuple] = []  # (phase, ms until the next step)
        own_group = current_phase[0] if current_phase[:2] in ("A_", "B_") else None
        if requested_group in ("A", "B"):
            target = f"{requested_group}_GREEN"
            if current_phase == target:
                return []
            # Other road's phase, or ALL_YELLOW/UNKNOWN: clear the box before the green.
            if own_group != requested_group and current_phase != "ALL_RED":
                if current_phase.endswith("_GREEN"):
                    steps.append((f"{own_group}_YELLOW", int(yellow_sec * 1000)))
                steps.append(("ALL_RED", int(all_red_sec * 1000)))
            steps.append((target, 0))
        elif requested_group in ("ALL_RED", "STOP"):
            if current_phase.endswith("_GREEN"):
                steps.append((f"{own_group}_YELLOW", int(yellow_sec * 1000)))
            steps.append(("ALL_RED", 0))

        changes: List[SignalChange] = []
        t = at_video_ms
        for seq, (phase, duration_ms) in enumerate(steps, start=start_seq):
            changes.append(SignalChange(at_video_ms=t, phase=phase, source="manual_annotation", seq=seq))
            t += duration_ms
        return changes
