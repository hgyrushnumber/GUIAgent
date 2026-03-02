"""Action selection policy for MVP."""
from __future__ import annotations

import json
from typing import List

from .local_model import LocalModelClient


class LocalModelPolicy:
    def __init__(self, client: LocalModelClient):
        self.client = client

    def select_one(self, candidates: List[dict], subgoal: str, obs_summary: str) -> dict:
        if not candidates:
            return {"action_type": "WAIT", "element_id": None, "text": None}

        prompt = self._build_prompt(candidates, subgoal, obs_summary)
        try:
            raw = self.client.generate(prompt)
            parsed = json.loads(raw)
            pick = str(parsed.get("pick", "")).upper()
            for c in candidates:
                if c["action_type"] == pick:
                    return c
        except Exception:
            pass

        # Fallback: highest score, prefer CLICK if close.
        ordered = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
        best = ordered[0]
        for c in ordered[1:]:
            if (
                c["action_type"] == "CLICK"
                and best["score"] - c.get("score", 0.0) <= 0.1
            ):
                return c
        return best

    @staticmethod
    def _build_prompt(candidates: List[dict], subgoal: str, obs_summary: str) -> str:
        compact = [
            {
                "action_type": c.get("action_type"),
                "element_id": c.get("element_id"),
                "text": c.get("text"),
                "score": round(float(c.get("score", 0.0)), 3),
            }
            for c in candidates
        ]
        return (
            "You are selecting ONE GUI action. Return JSON only: {\"pick\": \"CLICK|TYPE|WAIT\"}.\n"
            f"Subgoal: {subgoal}\n"
            f"Observation: {obs_summary[:400]}\n"
            f"Candidates: {json.dumps(compact, ensure_ascii=False)}"
        )
