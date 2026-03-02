"""Simple grounding ranker for MVP."""
from __future__ import annotations

from typing import List

from .types import UIElement


class GroundingRanker:
    KEYWORDS = {
        "focus_address_bar": ["address", "url", "搜索", "地址"],
        "open_baidu": ["address", "url", "百度", "baidu"],
        "focus_search_box": ["搜索", "search", "query"],
        "search_python": ["搜索", "search", "python"],
    }

    def rank(self, elements: List[UIElement], subgoal: str, top_k: int = 5) -> List[dict]:
        keywords = [kw.lower() for kw in self.KEYWORDS.get(subgoal, [])]
        scored = []
        for e in elements:
            score = 0.0
            t = e.text.lower()
            if e.enabled:
                score += 0.2
            if e.clickable:
                score += 0.2
            if e.editable:
                score += 0.4
            for kw in keywords:
                if kw in t:
                    score += 1.0
            scored.append({"element": e, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return [
            {
                "element_id": x["element"].element_id,
                "role": x["element"].role,
                "text": x["element"].text,
                "clickable": x["element"].clickable,
                "editable": x["element"].editable,
                "score": round(x["score"], 4),
            }
            for x in scored[:top_k]
        ]
