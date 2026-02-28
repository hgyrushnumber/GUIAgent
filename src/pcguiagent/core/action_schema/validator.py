import json
from typing import Optional, Tuple

from pcguiagent.core.action_schema.action import Action


class ActionValidator:
    """
    校验 LLM 输出的 JSON 是否是合法的 Action Schema
    """

    @staticmethod
    def validate(raw: str) -> Tuple[bool, Optional[Action], Optional[str]]:
        """
        返回:
        (is_valid, Action / None, error_msg)
        """

        try:
            data = json.loads(raw)
        except Exception:
            return False, None, "LLM output is not valid JSON"

        if "action" not in data:
            return False, None, "Missing 'action' field"

        action_block = data["action"]
        if "name" not in action_block:
            return False, None, "Action missing 'name'"

        args = action_block.get("args", {})
        if not isinstance(args, dict):
            return False, None, "Action 'args' must be a dict"

        action = Action(
            name=action_block["name"],
            args=args
        )

        return True, action, None
