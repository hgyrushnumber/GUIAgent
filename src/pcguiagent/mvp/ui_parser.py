"""A11y parser for MVP."""
from __future__ import annotations

from typing import Any, Dict, List

from .types import UIElement


class UIParser:
    """Parse OSWorld-like observation to normalized elements."""

    def parse(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        raw_nodes = observation.get("a11y_nodes") or observation.get("elements") or []
        elements: List[UIElement] = []

        for idx, node in enumerate(raw_nodes):
            role = str(node.get("role", "")).lower()
            text = str(node.get("text", "") or node.get("name", "")).strip()
            clickable = bool(node.get("clickable", role in {"button", "link", "menuitem"}))
            editable = bool(node.get("editable", role in {"textbox", "input", "searchbox"}))
            enabled = bool(node.get("enabled", True))

            if not (clickable or editable or text):
                continue

            element_id = str(node.get("element_id") or f"node_{idx}")
            elements.append(
                UIElement(
                    element_id=element_id,
                    role=role,
                    text=text,
                    clickable=clickable,
                    editable=editable,
                    enabled=enabled,
                )
            )

        return {
            "elements": elements,
            "window_meta": observation.get("window_meta", {}),
            "raw_a11y": observation.get("a11y_tree", ""),
            "url": observation.get("url", ""),
            "page_text": observation.get("page_text", ""),
        }
