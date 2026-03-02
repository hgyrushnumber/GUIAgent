"""Fixed subgoal stage manager for single-task MVP."""
from __future__ import annotations

from typing import Any, Dict

from .types import StageState


class StageManager:
    SUBGOALS = [
        "focus_address_bar",
        "open_baidu",
        "focus_search_box",
        "search_python",
    ]

    def init(self) -> StageState:
        return StageState(subgoals=self.SUBGOALS.copy())

    def update(
        self,
        state: StageState,
        obs: Dict[str, Any],
        last_action: Dict[str, Any] = None,
        info: Dict[str, Any] = None,
    ) -> StageState:
        if state.idx >= len(state.subgoals):
            return state

        url = str(obs.get("url", "")).lower()
        page_text = str(obs.get("page_text", "")).lower()
        current = state.current_subgoal

        completed = False
        if current == "focus_address_bar":
            completed = bool(last_action and last_action.get("action_type") == "CLICK")
        elif current == "open_baidu":
            completed = "baidu" in url or "baidu" in page_text
        elif current == "focus_search_box":
            completed = bool(last_action and last_action.get("action_type") == "CLICK")
        elif current == "search_python":
            completed = "python" in page_text

        if completed:
            state.idx += 1
            state.stall_count = 0
        else:
            state.stall_count += 1

        return state
