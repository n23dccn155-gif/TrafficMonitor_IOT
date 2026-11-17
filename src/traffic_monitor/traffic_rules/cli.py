"""CLI runner for Traffic Rule Engine.
Run standalone:
python -m src.traffic_monitor.traffic_rules.cli --tracks <path> --scene <path> --timeline <path> --output <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import RuleEngine
from .schemas import SceneConfig, SignalTimeline


def main():
    parser = argparse.ArgumentParser(description="Standalone Traffic Rule Engine CLI")
    parser.add_argument("--tracks", required=True, help="Path to tracks.jsonl")
    parser.add_argument("--scene", required=True, help="Path to scene_config.json")
    parser.add_argument("--timeline", required=False, help="Path to signal_timeline.json (optional)")
    parser.add_argument("--output", required=True, help="Path to write events.jsonl")
    parser.add_argument("--rule-run-id", default="cli_run", help="Identifier for this rule execution")

    args = parser.parse_args()

    # Load scene config
    with open(args.scene, "r", encoding="utf-8") as f:
        scene_data = json.load(f)
    scene = SceneConfig.from_dict(scene_data)

    # Load timeline if provided
    timeline = None
    if args.timeline and Path(args.timeline).is_file():
        with open(args.timeline, "r", encoding="utf-8") as f:
            timeline_data = json.load(f)
        timeline = SignalTimeline.from_dict(timeline_data)

    engine = RuleEngine(scene=scene, timeline=timeline, rule_run_id=args.rule_run_id)
    events = engine.process_tracks_file(args.tracks)

    RuleEngine.save_events_jsonl(events, args.output)
    print(f"[OK] RuleEngine completed: generated {len(events)} events -> {args.output}")


if __name__ == "__main__":
    main()
