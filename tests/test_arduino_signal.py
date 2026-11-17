"""Protocol and API checks without an attached board."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import Client

from monitor.services.arduino_signal_service import ArduinoSignalService, parse_state


def test_parse_uno_state():
    assert parse_state("STATE B_GREEN 4210 5 2 7 2 AUTO\r\n") == {
        "phase": "B_GREEN", "remaining_ms": 4210, "mode": "auto",
        "a_green": 5, "a_yellow": 2, "b_green": 7, "b_yellow": 2,
    }
    with pytest.raises(ValueError):
        parse_state("STATE A_GREEN 5000 5 2 5 2")


def test_arduino_api_validates_before_sending():
    client = Client()
    with patch("monitor.views.ArduinoSignalService.get_instance") as get_service:
        service = get_service.return_value
        service.command.return_value = {
            "connected": True, "port": "COM3", "phase": "A_GREEN",
            "remaining_ms": 5000, "mode": "auto", "a_green": 5,
            "a_yellow": 2, "b_green": 5, "b_yellow": 2,
        }
        response = client.post("/api/arduino/signal/", data=json.dumps({
            "action": "auto", "a_green": 5, "a_yellow": 2,
            "b_green": 5, "b_yellow": 2,
        }), content_type="application/json")
        assert response.status_code == 200
        service.command.assert_called_once_with("AUTO 5 2 5 2")
        service.command.reset_mock()
        bad = client.post("/api/arduino/signal/", data=json.dumps({
            "action": "manual", "phase": "A_GREEN;B_GREEN",
        }), content_type="application/json")
        assert bad.status_code == 400
        service.command.assert_not_called()


def test_arduino_api_blocks_nonlocal_client():
    response = Client(REMOTE_ADDR="192.168.1.5").get("/api/arduino/signal/")
    assert response.status_code == 403


def test_serial_service_uses_uno_state_and_stops_on_disconnect(monkeypatch):
    class FakeSerial:
        is_open = True

        def __init__(self, port, baudrate, timeout, write_timeout):
            assert (port, baudrate) == ("COM3", 9600)
            self.commands = []

        def reset_input_buffer(self):
            pass

        def write(self, data):
            self.commands.append(data.decode("ascii").strip())

        def readline(self):
            phase = "ALL_RED" if self.commands[-1] == "MANUAL ALL_RED" else "A_GREEN"
            return f"STATE {phase} 5000 5 2 5 2 AUTO\n".encode("ascii")

        def close(self):
            self.is_open = False

    fake = FakeSerial
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=lambda *args, **kwargs: fake(*args, **kwargs)))
    monkeypatch.setattr("monitor.services.arduino_signal_service.time.sleep", lambda _: None)
    service = ArduinoSignalService()
    assert service.connect("com3")["phase"] == "A_GREEN"
    port = service._serial
    assert service.command("AUTO 5 2 5 2")["phase"] == "A_GREEN"
    assert service.disconnect()["connected"] is False
    assert port.commands == ["STATUS", "AUTO 5 2 5 2", "MANUAL ALL_RED"]
    assert port.is_open is False
