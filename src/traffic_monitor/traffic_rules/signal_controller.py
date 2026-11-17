"""Signal timeline generation and hardware controller interface.
Zero external dependency for logic and FakeSerialAdapter; optional pyserial for real hardware.
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from .schemas import SignalChange, SignalTimeline

VALID_PHASES = {"A_GREEN", "A_YELLOW", "ALL_RED", "B_GREEN", "B_YELLOW"}


class TimelineGenerator:
    """Generates strictly safe signal sequences with zero concurrent greens."""

    @staticmethod
    def generate_timed(
        duration_ms: int,
        a_green_sec: float = 10.0,
        b_green_sec: float = 10.0,
        yellow_sec: float = 3.0,
        all_red_sec: float = 2.0,
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
        all_red_sec: float = 2.0,
        start_seq: int = 1,
    ) -> List[SignalChange]:
        """Generate safe transition sequence between groups.
        Never transitions directly from A_GREEN to B_GREEN.
        """
        yellow_ms = int(yellow_sec * 1000)
        all_red_ms = int(all_red_sec * 1000)
        seq = start_seq
        t = at_video_ms
        changes: List[SignalChange] = []

        if requested_group == "A":
            if current_phase == "A_GREEN":
                return changes
            if current_phase in ("B_GREEN", "B_YELLOW"):
                if current_phase == "B_GREEN":
                    changes.append(SignalChange(at_video_ms=t, phase="B_YELLOW", source="manual_annotation", seq=seq))
                    seq += 1
                    t += yellow_ms
                changes.append(SignalChange(at_video_ms=t, phase="ALL_RED", source="manual_annotation", seq=seq))
                seq += 1
                t += all_red_ms
            changes.append(SignalChange(at_video_ms=t, phase="A_GREEN", source="manual_annotation", seq=seq))

        elif requested_group == "B":
            if current_phase == "B_GREEN":
                return changes
            if current_phase in ("A_GREEN", "A_YELLOW"):
                if current_phase == "A_GREEN":
                    changes.append(SignalChange(at_video_ms=t, phase="A_YELLOW", source="manual_annotation", seq=seq))
                    seq += 1
                    t += yellow_ms
                changes.append(SignalChange(at_video_ms=t, phase="ALL_RED", source="manual_annotation", seq=seq))
                seq += 1
                t += all_red_ms
            changes.append(SignalChange(at_video_ms=t, phase="B_GREEN", source="manual_annotation", seq=seq))

        elif requested_group in ("ALL_RED", "STOP"):
            if current_phase == "A_GREEN":
                changes.append(SignalChange(at_video_ms=t, phase="A_YELLOW", source="manual_annotation", seq=seq))
                seq += 1
                t += yellow_ms
            elif current_phase == "B_GREEN":
                changes.append(SignalChange(at_video_ms=t, phase="B_YELLOW", source="manual_annotation", seq=seq))
                seq += 1
                t += yellow_ms
            changes.append(SignalChange(at_video_ms=t, phase="ALL_RED", source="manual_annotation", seq=seq))

        return changes


class SignalController(ABC):
    @abstractmethod
    def send_phase(self, phase: str, command_id: int) -> dict:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass


class FakeSerialAdapter(SignalController):
    """Simulates Arduino Uno serial ACK communication for automated testing."""

    def __init__(self, simulate_disconnect: bool = False):
        self.connected = not simulate_disconnect
        self.last_phase = "ALL_RED"
        self.seq = 0

    def is_connected(self) -> bool:
        return self.connected

    def send_phase(self, phase: str, command_id: int) -> dict:
        if not self.connected:
            return {"command_id": command_id, "status": "ERROR", "error": "Serial disconnected"}
        if phase not in VALID_PHASES:
            return {"command_id": command_id, "status": "REJECTED", "error": f"Invalid phase: {phase}"}

        self.seq += 1
        self.last_phase = phase
        return {
            "command_id": command_id,
            "seq": self.seq,
            "phase": phase,
            "t_ms": int(time.time() * 1000) % 1000000,
            "status": "ACK",
        }


class PySerialAdapter(SignalController):
    """Hardware serial adapter for real Arduino Uno R3 via USB COM port."""

    def __init__(self, port: str = "COM3", baudrate: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self._try_connect()

    def _try_connect(self) -> bool:
        try:
            import serial  # type: ignore

            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(1.5)  # Allow Arduino bootloader reset
            return True
        except Exception:
            self.ser = None
            return False

    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def send_phase(self, phase: str, command_id: int) -> dict:
        if not self.is_connected():
            if not self._try_connect():
                return {"command_id": command_id, "status": "ERROR", "error": "Hardware serial not connected"}

        try:
            cmd = json.dumps({"command_id": command_id, "phase": phase}) + "\n"
            self.ser.write(cmd.encode("utf-8"))
            line = self.ser.readline().decode("utf-8").strip()
            if not line:
                return {"command_id": command_id, "status": "TIMEOUT", "error": "No ACK received"}
            return json.loads(line)
        except Exception as e:
            return {"command_id": command_id, "status": "ERROR", "error": str(e)}
