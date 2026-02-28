from typing import Dict, Any


class LongTermMemory:
    """
    长期记忆
    - 用户偏好
    - 应用常用路径
    - 历史任务的总结信息
    - 可被持久化到磁盘

    这是“智能办公”与“自动流程”关键组件。
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self._store[key] = value

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    def update(self, data: Dict[str, Any]):
        self._store.update(data)

    def to_dict(self):
        return dict(self._store)

    def clear(self):
        self._store.clear()
