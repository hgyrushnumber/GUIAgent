"""Build capped action candidates for MVP."""
from __future__ import annotations

from typing import List


class ActionComposer:
    def compose(self, ranked: List[dict], subgoal: str) -> List[dict]:
        candidates: List[dict] = []

        for item in ranked[:5]:
            if item.get("clickable"):
                candidates.append(
                    {
                        "action_type": "CLICK",
                        "element_id": item["element_id"],
                        "text": None,
                        "score": item["score"],
                    }
                )

        type_text = self._text_for_subgoal(subgoal)
        for item in ranked[:2]:
            if item.get("editable") and type_text:
                candidates.append(
                    {
                        "action_type": "TYPE",
                        "element_id": item["element_id"],
                        "text": type_text,
                        "score": item["score"] + 0.1,
                    }
                )

        candidates.append(
            {
                "action_type": "WAIT",
                "element_id": None,
                "text": None,
                "score": 0.01,
            }
        )

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:8]

    @staticmethod
    def _text_for_subgoal(subgoal: str) -> str:
        if subgoal == "open_baidu":
            return "https://www.baidu.com"
        if subgoal == "search_python":
            return "Python"
        return ""
