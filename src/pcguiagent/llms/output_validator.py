import json
from typing import Tuple, Optional

from pcguiagent.core.action_schema.action import Action


class OutputValidator:
    """
    LLM 输出校验器（OSWorld 必备）
    """

    @staticmethod
    def validate(raw: str) -> Tuple[bool, Optional[dict], Optional[str]]:
        """
        返回：
        (is_valid, json_object 或 None, error_msg)
        """
        try:
            obj = json.loads(raw)
        except Exception:
            return False, None, "Output is not valid JSON"

        # 必须有 is_done 字段
        if "is_done" not in obj:
            return False, None, "Missing is_done"

        # is_done = false 时必须有 action
        if not obj["is_done"]:
            if "action" not in obj:
                return False, None, "Missing action field"
            if "name" not in obj["action"]:
                return False, None, "Missing action.name"

        return True, obj, None
