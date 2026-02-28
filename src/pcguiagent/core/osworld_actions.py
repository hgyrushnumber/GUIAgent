"""
OSWorld action space adapter.

Loads `OSWorld/desktop_env/actions.py` and exposes:
- ACTION_SPACE, KEYBOARD_KEYS, X_MAX, Y_MAX
- Prompt-friendly descriptions for LLM templates
- Runtime validator for action_type + parameters

Environment override:
- OSWORLD_ACTIONS_PATH: path to OSWorld actions.py
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Cache to avoid reloading the external module repeatedly
_cached_actions: Optional[Dict[str, Any]] = None


def _default_actions_path() -> Path:
    """Resolve the default path to OSWorld actions.py (sibling repo)."""
    env_path = os.getenv("OSWORLD_ACTIONS_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    # pc-gui-agent/src/pcguiagent/core → ../.. = project root
    # OSWorld repo is expected at ../OSWorld/desktop_env/actions.py
    root = Path(__file__).resolve().parents[4]
    return root / "OSWorld" / "desktop_env" / "actions.py"


def _load_actions_module(path: Optional[Path] = None):
    """Dynamically import the OSWorld actions.py module."""
    actions_path = Path(path) if path else _default_actions_path()
    if not actions_path.exists():
        raise FileNotFoundError(f"OSWorld actions.py not found at {actions_path}")

    spec = importlib.util.spec_from_file_location("osworld_actions_module", actions_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec from {actions_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def get_osworld_actions(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Return cached OSWorld action definitions.

    Returns dict with keys: ACTION_SPACE, KEYBOARD_KEYS, X_MAX, Y_MAX
    """
    global _cached_actions
    if _cached_actions is not None:
        return _cached_actions

    module = _load_actions_module(path)
    required = ["ACTION_SPACE", "KEYBOARD_KEYS", "X_MAX", "Y_MAX"]
    missing = [k for k in required if not hasattr(module, k)]
    if missing:
        raise AttributeError(f"Missing fields in OSWorld actions.py: {missing}")

    _cached_actions = {
        "ACTION_SPACE": module.ACTION_SPACE,
        "KEYBOARD_KEYS": module.KEYBOARD_KEYS,
        "X_MAX": module.X_MAX,
        "Y_MAX": module.Y_MAX,
    }
    return _cached_actions


def build_prompt_actions() -> List[Dict[str, Any]]:
    """
    Build prompt-ready action descriptions from OSWorld ACTION_SPACE.

    Format: [{name, description, parameters}]
    """
    data = get_osworld_actions()
    actions = data["ACTION_SPACE"]
    prompt_items: List[Dict[str, Any]] = []

    for action in actions:
        name = action.get("action_type", "")
        note = action.get("note", "")
        params = action.get("parameters", {}) or {}
        param_lines = []
        for pname, pinfo in params.items():
            ptype = pinfo.get("type")
            optional = pinfo.get("optional", False)
            prange = pinfo.get("range")
            ptype_name = getattr(ptype, "__name__", str(ptype))
            desc = f"{pname} ({ptype_name})"
            if optional:
                desc += ", optional"
            if prange is not None:
                desc += f", range={prange}"
            param_lines.append(desc)
        parameters_desc = "; ".join(param_lines) if param_lines else "None"
        prompt_items.append(
            {
                "name": name,
                "description": note,
                "parameters": parameters_desc,
                "raw_parameters": params,
            }
        )

    return prompt_items


def format_actions_for_prompt() -> str:
    """Return a compact string description suitable for LLM prompts."""
    items = build_prompt_actions()
    lines = []
    for item in items:
        params = item.get("parameters", "None")
        lines.append(f"{item['name']}: {item['description']} (params: {params})")
    return "\n".join(lines)


def _is_numeric_range(value: Any, prange: Any) -> bool:
    if not isinstance(prange, (list, tuple)) or len(prange) != 2:
        return False
    return all(isinstance(x, (int, float)) for x in prange)


def _validate_enum(value: Any, allowed: List[Any]) -> bool:
    return value in allowed


def _validate_range(value: Any, prange: Any) -> bool:
    if _is_numeric_range(value, prange):
        return prange[0] <= value <= prange[1]
    if isinstance(prange, list):
        return value in prange
    return True


def validate_osworld_action(action_type: str, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate action_type + parameters against OSWorld ACTION_SPACE.

    Returns (is_valid, error_message_if_any)
    """
    data = get_osworld_actions()
    actions = data["ACTION_SPACE"]
    key_map = {a["action_type"]: a for a in actions}
    if action_type not in key_map:
        return False, f"Unknown action_type: {action_type}"

    action_def = key_map[action_type]
    param_defs: Dict[str, Dict[str, Any]] = action_def.get("parameters", {}) or {}

    # Required check + type/range validation
    for pname, pinfo in param_defs.items():
        expected_type = pinfo.get("type")
        optional = pinfo.get("optional", False)
        prange = pinfo.get("range")
        present = pname in parameters and parameters[pname] is not None

        if not present and not optional:
            return False, f"Missing required parameter: {pname}"
        if not present:
            continue

        value = parameters[pname]
        # Type check with tolerant float/int conversion
        if expected_type is float:
            if not isinstance(value, (int, float)):
                return False, f"Parameter '{pname}' must be float"
        elif expected_type is int:
            if not isinstance(value, int):
                return False, f"Parameter '{pname}' must be int"
        elif expected_type is str:
            if not isinstance(value, str):
                return False, f"Parameter '{pname}' must be str"
        elif expected_type is list:
            if not isinstance(value, list):
                return False, f"Parameter '{pname}' must be list"
            # For list, if range provided, treat as enum for each element
            if prange:
                allowed = prange[0] if isinstance(prange, list) and len(prange) == 1 else prange
                if isinstance(allowed, list):
                    for idx, item in enumerate(value):
                        if not _validate_enum(item, allowed):
                            return False, f"Parameter '{pname}[{idx}]' not in allowed set"
        else:
            # Unknown type, skip strict check
            pass

        if prange is not None:
            if isinstance(value, list):
                # For list parameters, validate each element if enum provided
                if isinstance(prange, list) and len(prange) == 1 and isinstance(prange[0], list):
                    allowed = prange[0]
                    for idx, item in enumerate(value):
                        if not _validate_enum(item, allowed):
                            return False, f"Parameter '{pname}[{idx}]' not in allowed set"
            else:
                if not _validate_range(value, prange):
                    return False, f"Parameter '{pname}' out of range {prange}"

    # Reject unexpected parameters
    for pname in parameters:
        if pname not in param_defs:
            return False, f"Unexpected parameter: {pname}"

    return True, None


__all__ = [
    "get_osworld_actions",
    "build_prompt_actions",
    "format_actions_for_prompt",
    "validate_osworld_action",
]

