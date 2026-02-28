from typing import Any, Dict, Optional


class ShortTermMemory:
    """
    负责存储任务的短期上下文，包括：
    - 上一次 observation
    - 重要变量（如“目标位置”、“上一次点击的控件”）
    - planner 状态（某子任务进行到哪一步）

    当任务结束，该 memory 会自动清空。
    """

    def __init__(self, limit: int = 10):
        self.limit = limit
        self._context: Dict[str, Any] = {}

    # ================================
    # 基础操作
    # ================================
    def set(self, key: str, value: Any):
        self._context[key] = value
        self._trim()

    def get(self, key: str, default=None):
        return self._context.get(key, default)

    def clear(self):
        self._context.clear()

    def to_dict(self):
        return dict(self._context)

    # ================================
    # 限制大小
    # ================================
    def _trim(self):
        """当过长时，丢弃最早的 key"""
        if len(self._context) > self.limit:
            first_key = next(iter(self._context))
            del self._context[first_key]
