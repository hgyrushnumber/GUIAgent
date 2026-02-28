from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Action:
    """
    全局唯一 Action Schema
    被 ReasoningEngine / StepExecutor / Planner 一致使用
    """
    name: str
    args: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "name": self.name,
            "args": self.args
        }
