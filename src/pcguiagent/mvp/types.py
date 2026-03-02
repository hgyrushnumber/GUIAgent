"""Types for single-task OSWorld MVP pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UIElement:
    element_id: str
    role: str
    text: str = ""
    clickable: bool = False
    editable: bool = False
    enabled: bool = True


@dataclass
class StageState:
    subgoals: List[str]
    idx: int = 0
    stall_count: int = 0

    @property
    def current_subgoal(self) -> str:
        if self.idx >= len(self.subgoals):
            return "done"
        return self.subgoals[self.idx]


@dataclass
class ActionCandidate:
    action_type: str
    element_id: Optional[str] = None
    text: Optional[str] = None
    score: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    step: int
    subgoal: str
    topk_elements: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    chosen_action: Dict[str, Any]
    done: bool
    success_signal: bool
    latency_ms: float
