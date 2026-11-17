"""Base class for all traffic violation rules.
Implements the golden rule: strictly ONE event per vehicle track passage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Optional, Tuple

from ..schemas import SceneConfig, SignalTimeline, TrackFrame, TrackObservation, ViolationEvent


class RuleState(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    LOCKED = "LOCKED"


class BaseRule(ABC):
    def __init__(self, rule_name: str, rule_run_id: str):
        self.rule_name = rule_name
        self.rule_run_id = rule_run_id
        # State key: (segment_id, track_id) -> RuleState
        self._states: Dict[Tuple[str, int], RuleState] = {}
        # Track history cache: (segment_id, track_id) -> Dict[str, Any]
        self._track_history: Dict[Tuple[str, int], dict] = {}

    def get_state(self, segment_id: str, track_id: int) -> RuleState:
        return self._states.get((segment_id, track_id), RuleState.PENDING)

    def set_state(self, segment_id: str, track_id: int, state: RuleState) -> None:
        self._states[(segment_id, track_id)] = state

    def is_locked(self, segment_id: str, track_id: int) -> bool:
        return self.get_state(segment_id, track_id) == RuleState.LOCKED

    def lock_track(self, segment_id: str, track_id: int) -> None:
        self.set_state(segment_id, track_id, RuleState.LOCKED)

    def reset(self) -> None:
        self._states.clear()
        self._track_history.clear()

    @abstractmethod
    def evaluate(
        self,
        observation: TrackObservation,
        frame: TrackFrame,
        scene: SceneConfig,
        timeline: Optional[SignalTimeline],
    ) -> Optional[ViolationEvent]:
        """Evaluate single vehicle observation in frame.
        Must return ViolationEvent at most ONCE per track passage, then LOCK.
        """
        pass
