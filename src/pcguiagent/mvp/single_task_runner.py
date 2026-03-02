"""Single-task MVP runner pipeline."""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .action_composer import ActionComposer
from .grounding_ranker import GroundingRanker
from .policy import LocalModelPolicy
from .stage_manager import StageManager
from .trajectory_logger import TrajectoryLogger
from .ui_parser import UIParser


class SingleTaskMVPRunner:
    """Minimal pipeline for one OSWorld-style task."""

    def __init__(self, policy: LocalModelPolicy, log_path: str):
        self.parser = UIParser()
        self.stage_manager = StageManager()
        self.ranker = GroundingRanker()
        self.composer = ActionComposer()
        self.policy = policy
        self.logger = TrajectoryLogger(log_path)

    def run_episode(self, env: Any, max_steps: int = 20) -> Dict[str, Any]:
        observation = env.reset()
        stage = self.stage_manager.init()
        last_action: Optional[Dict[str, Any]] = None
        no_change_count = 0
        success = False

        for step in range(max_steps):
            t0 = time.perf_counter()

            parsed = self.parser.parse(observation)
            stage = self.stage_manager.update(stage, parsed, last_action, {})
            subgoal = stage.current_subgoal

            ranked = self.ranker.rank(parsed["elements"], subgoal=subgoal, top_k=5)
            candidates = self.composer.compose(ranked=ranked, subgoal=subgoal)
            chosen = self.policy.select_one(candidates, subgoal, obs_summary=parsed.get("raw_a11y", ""))

            next_obs, _, done, info = env.step(chosen)
            success_signal = self._is_success(next_obs)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            self.logger.append(
                {
                    "step": step,
                    "subgoal": subgoal,
                    "topk_elements": ranked,
                    "candidates": candidates,
                    "chosen_action": chosen,
                    "done": bool(done),
                    "success_signal": bool(success_signal),
                    "latency_ms": round(latency_ms, 2),
                }
            )

            if self._is_same_ui(observation, next_obs):
                no_change_count += 1
            else:
                no_change_count = 0

            if success_signal:
                success = True
                return {"success": True, "steps": step + 1, "reason": "success_signal"}
            if done:
                return {"success": success, "steps": step + 1, "reason": "env_done"}
            if no_change_count >= 3:
                return {"success": False, "steps": step + 1, "reason": "no_ui_change"}

            observation = next_obs
            last_action = chosen

        return {"success": success, "steps": max_steps, "reason": "max_steps"}

    @staticmethod
    def _is_same_ui(obs1: Dict[str, Any], obs2: Dict[str, Any]) -> bool:
        return (
            str(obs1.get("url", "")) == str(obs2.get("url", ""))
            and str(obs1.get("page_text", ""))[:120] == str(obs2.get("page_text", ""))[:120]
        )

    @staticmethod
    def _is_success(observation: Dict[str, Any]) -> bool:
        url = str(observation.get("url", "")).lower()
        txt = str(observation.get("page_text", "")).lower()
        app = str(observation.get("window_meta", {}).get("app", "")).lower()
        return ("browser" in app or "chrome" in app or "edge" in app) and (
            "baidu" in url or "baidu" in txt
        ) and ("python" in txt)
