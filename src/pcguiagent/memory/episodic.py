from typing import List, Dict, Any


class EpisodicMemory:
    """
    事件记忆：
    每一步工具执行，都会记录一条 Event：
    {
      "step": 1,
      "action": "...",
      "args": {...},
      "result": {...}
    }

    OSWorld 长任务中非常重要：可用于错误恢复、避免重复操作。
    """

    def __init__(self, limit: int = 200):
        self.limit = limit
        self._events: List[Dict[str, Any]] = []

    def add_event(self, step: int, goal: str, action, result):
        item = {
            "step": step,
            "goal": goal,
            "action": {
                "name": action.name,
                "args": action.args,
            },
            "result": {
                "success": result.success,
                "data": result.data,
                "error": result.error,
            },
        }
        self._events.append(item)
        self._trim()

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def clear(self):
        self._events.clear()

    def _trim(self):
        if len(self._events) > self.limit:
            overflow = len(self._events) - self.limit
            self._events = self._events[overflow:]
