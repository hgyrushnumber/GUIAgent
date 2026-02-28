from typing import Optional, Dict, Any

from pcguiagent.memory.short_term import ShortTermMemory
from pcguiagent.memory.long_term import LongTermMemory
from pcguiagent.memory.episodic import EpisodicMemory
from pcguiagent.utils.logger import get_logger

logger = get_logger("MemoryStorage")

class MemoryStorage:
    """
    Agent 使用的统一 Memory 接口:
    - short_term: 当前任务上下文（随任务重置）
    - episodic: 执行事件记录
    - long_term: 用户偏好 / 通用知识（跨任务持久）

    controller/run.py → memory.add_event 即可
    ReasoningEngine → 可从 memory.short_term 获取上下文
    """

    def __init__(self, config):
        self.short_term = ShortTermMemory(limit=config.short_term_limit)
        self.long_term = LongTermMemory()
        self.episodic = EpisodicMemory(limit=config.episodic_limit)

        self.persistent_path = getattr(config, "persistent_path", None)

    # ============================================
    # 对外统一接口
    # ============================================
    def add_event(self, step: int, goal: str, action, result):
        self.episodic.add_event(step, goal, action, result)

    def set_context(self, key: str, value: Any):
        self.short_term.set(key, value)

    def get_context(self, key: str, default=None):
        return self.short_term.get(key, default)

    def set_preference(self, key: str, value: Any):
        self.long_term.set(key, value)

    # ============================================
    # 清理任务上下文
    # ============================================
    def reset_for_new_task(self):
        logger.info("[Memory] Resetting for new task")
        self.short_term.clear()
        self.episodic.clear()

    # ============================================
    # 持久化（可选）
    # ============================================
    def save(self):
        if not self.persistent_path:
            return

        import json
        with open(self.persistent_path, "w", encoding="utf-8") as f:
            json.dump({
                "long_term": self.long_term.to_dict()
            }, f, ensure_ascii=False, indent=2)

    def load(self):
        if not self.persistent_path:
            return

        import json, os

        if not os.path.exists(self.persistent_path):
            return

        with open(self.persistent_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "long_term" in data:
                self.long_term.update(data["long_term"])
