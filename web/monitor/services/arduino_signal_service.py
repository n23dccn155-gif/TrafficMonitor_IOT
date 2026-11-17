"""One USB Serial owner for the Uno traffic lights in the Django process."""
from __future__ import annotations

import re
import threading
import time


PHASES = {"A_GREEN", "A_YELLOW", "B_GREEN", "B_YELLOW", "ALL_RED"}
PORT_PATTERN = re.compile(r"COM[1-9][0-9]*\Z", re.IGNORECASE)


def parse_state(line: str) -> dict:
    parts = line.strip().split()
    if (len(parts) != 8 or parts[0] != "STATE" or parts[1] not in PHASES
            or parts[7] not in {"AUTO", "MANUAL"}):
        raise ValueError(f"Invalid Uno response: {line[:80]}")
    remaining_ms, a_green, a_yellow, b_green, b_yellow = map(int, parts[2:7])
    if min(remaining_ms, a_green, a_yellow, b_green, b_yellow) < 0:
        raise ValueError("Invalid negative Uno timing")
    return {
        "phase": parts[1], "remaining_ms": remaining_ms, "mode": parts[7].lower(),
        "a_green": a_green, "a_yellow": a_yellow,
        "b_green": b_green, "b_yellow": b_yellow,
    }


class ArduinoSignalService:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.RLock()
        self._serial = None
        self.port = None
        self.last_state = None

    @classmethod
    def get_instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _close(self):
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None
        self.last_state = None

    def disconnect(self):
        with self._lock:
            if self._serial is not None:
                try:
                    self._exchange("MANUAL ALL_RED")
                except Exception:
                    self.port = None
                    raise
            self._close()
            self.port = None
            return {"connected": False, "port": None}

    def connect(self, port: str):
        if not isinstance(port, str) or not PORT_PATTERN.fullmatch(port):
            raise ValueError("Port must be COM followed by a positive number, e.g. COM3")
        with self._lock:
            self._close()
            import serial
            self._serial = serial.Serial(port.upper(), 9600, timeout=0.8, write_timeout=0.8)
            self.port = port.upper()
            try:
                time.sleep(2)  # Uno resets when USB Serial is opened.
                self._serial.reset_input_buffer()
                return self._exchange("STATUS")
            except Exception:
                self._close()
                self.port = None
                raise

    def _exchange(self, command: str):
        if self._serial is None or not self._serial.is_open:
            self._close()
            raise ConnectionError("Arduino is not connected")
        try:
            self._serial.reset_input_buffer()
            self._serial.write((command + "\n").encode("ascii"))
            line = self._serial.readline().decode("ascii", errors="replace").strip()
            try:
                state = parse_state(line)
            except ValueError as exc:
                raise ConnectionError(str(exc)) from exc
            self.last_state = state
            return {"connected": True, "port": self.port, **state}
        except Exception:
            self._close()
            raise

    def status(self):
        with self._lock:
            if self._serial is None:
                return {"connected": False, "port": self.port}
            return self._exchange("STATUS")

    @staticmethod
    def available_ports():
        from serial.tools import list_ports
        return [{"port": item.device, "description": item.description}
                for item in list_ports.comports()]

    def command(self, command: str):
        with self._lock:
            return self._exchange(command)
