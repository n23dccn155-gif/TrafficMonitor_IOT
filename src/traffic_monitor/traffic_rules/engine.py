"""Traffic Rule Engine.
Evaluates tracks against scene configuration and signal timeline to produce violation events.
Zero Django dependency.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, List, Optional

from .rules.lane_crossing import LaneEncroachmentRule
from .rules.red_light import RedLightRule
from .rules.wrong_way import WrongWayRule
from .schemas import SceneConfig, SignalTimeline, TrackFrame, ViolationEvent


class RuleEngine:
    def __init__(
        self,
        scene: SceneConfig,
        timeline: Optional[SignalTimeline] = None,
        rule_run_id: str = "run_default",
    ):
        self.scene = scene
        self.timeline = timeline
        self.rule_run_id = rule_run_id

        # Instantiate 3 rules
        self.rules = [
            WrongWayRule(rule_run_id=rule_run_id),
            LaneEncroachmentRule(rule_run_id=rule_run_id),
            RedLightRule(rule_run_id=rule_run_id),
        ]
        self._emitted_event_ids = set()

    def reset(self) -> None:
        self._emitted_event_ids.clear()
        for r in self.rules:
            r.reset()

    def process_frame(self, frame: TrackFrame) -> List[ViolationEvent]:
        events: List[ViolationEvent] = []
        for track in frame.tracks:
            for rule in self.rules:
                ev = rule.evaluate(track, frame, self.scene, self.timeline)
                if ev is not None:
                    # Enforce global idempotency
                    if ev.event_id not in self._emitted_event_ids:
                        self._emitted_event_ids.add(ev.event_id)
                        events.append(ev)
        return events

    def process_tracks_stream(self, frame_stream: Iterator[TrackFrame]) -> List[ViolationEvent]:
        all_events: List[ViolationEvent] = []
        for frame in frame_stream:
            evs = self.process_frame(frame)
            all_events.extend(evs)
        return all_events

    def process_tracks_file(self, tracks_jsonl_path: str | Path) -> List[ViolationEvent]:
        path = Path(tracks_jsonl_path)
        if not path.is_file():
            raise FileNotFoundError(f"tracks file not found: {path}")

        def _stream() -> Iterator[TrackFrame]:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        yield TrackFrame.from_dict(data)
                    except Exception:
                        continue

        return self.process_tracks_stream(_stream())

    @staticmethod
    def save_events_jsonl(events: List[ViolationEvent], output_path: str | Path) -> None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
