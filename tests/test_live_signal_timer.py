import pytest

from monitor.services.live_signal_timer import LiveSignalTimer, parse_signal_config
from src.traffic_monitor.traffic_rules.schemas import SignalTimeline

TIMED = {"mode": "timed", "a_green": 5, "a_yellow": 2, "b_green": 4, "b_yellow": 1}


def make_timer(config=TIMED, now_ms=0):
    timeline = SignalTimeline(timeline_id="t", version=1, video_id="live", mode="live", changes=[])
    return LiveSignalTimer(timeline, config, now_ms), timeline


def test_timed_cycle_records_changes_at_scheduled_ms_not_call_time():
    timer, timeline = make_timer()
    assert timer.advance(4999) == []
    # Called late (after 12.3s): every boundary is still recorded at its exact time.
    assert timer.advance(12300) == ["A_YELLOW", "B_GREEN", "B_YELLOW", "A_GREEN"]
    assert [(c.at_video_ms, c.phase) for c in timeline.changes] == [
        (0, "A_GREEN"), (5000, "A_YELLOW"), (7000, "B_GREEN"), (11000, "B_YELLOW"), (12000, "A_GREEN"),
    ]
    assert timeline.get_phase_at(6999) == "A_YELLOW"
    assert timeline.get_phase_at(7000) == "B_GREEN"
    assert timer.state(12300) == {
        "mode": "timed", "phase": "A_GREEN", "remaining_ms": 4700, "paused": False, "warming_up": False,
        "durations": {"a_green": 5, "a_yellow": 2, "b_green": 4, "b_yellow": 1},
    }


def test_manual_phase_holds_and_reconfigure_restarts_cycle():
    timer, timeline = make_timer()
    timer.configure({"mode": "manual", "phase": "B_GREEN"}, 3000)
    assert timer.advance(60000) == []
    assert timer.state(60000)["phase"] == "B_GREEN"
    timer.configure(TIMED, 61000)
    timer.advance(66000)
    assert [(c.at_video_ms, c.phase) for c in timeline.changes][-3:] == [
        (3000, "B_GREEN"), (61000, "A_GREEN"), (66000, "A_YELLOW"),
    ]


def test_both_yellow_pauses_and_resume_keeps_yellow_two_seconds_for_warm_up():
    timer, timeline = make_timer({"mode": "manual", "phase": "A_GREEN"})
    timer.configure({"mode": "manual", "phase": "ALL_YELLOW"}, 1000)
    assert timer.paused and timer.state(1500)["paused"] is True
    timer.configure({"mode": "manual", "phase": "B_GREEN"}, 5000)
    # Still yellow while YOLO warms up; detection runs again (not paused).
    assert timer.phase == "ALL_YELLOW" and not timer.paused
    assert timer.state(5500) == {"mode": "manual", "phase": "ALL_YELLOW", "remaining_ms": 1500,
                                 "paused": False, "warming_up": True}
    timer.configure({"mode": "manual", "phase": "A_GREEN"}, 6000)  # changed mind: due time kept
    assert timer.advance(6999) == []
    assert timer.advance(7000) == ["A_GREEN"]
    assert [(c.at_video_ms, c.phase) for c in timeline.changes] == [
        (0, "A_GREEN"), (1000, "ALL_YELLOW"), (7000, "A_GREEN"),
    ]
    assert timer.state(7000)["warming_up"] is False


def test_pause_again_during_warm_up_cancels_resume():
    timer, timeline = make_timer({"mode": "manual", "phase": "ALL_YELLOW"})
    assert timer.paused
    timer.configure(TIMED, 1000)
    timer.configure({"mode": "manual", "phase": "ALL_YELLOW"}, 1500)
    assert timer.advance(10000) == [] and timer.paused


@pytest.mark.parametrize("config", [
    None, [], {"mode": "auto"}, {"mode": "manual", "phase": "UNKNOWN"}, {"mode": "manual", "phase": "ALL_RED"},
    {**TIMED, "a_green": 2}, {**TIMED, "b_yellow": 11}, {**TIMED, "a_yellow": "3"}, {**TIMED, "b_green": True},
])
def test_invalid_signal_config_is_rejected(config):
    with pytest.raises(ValueError):
        parse_signal_config(config)
