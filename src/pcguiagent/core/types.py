"""
Core Type Definitions

Shared types used across the Intra-Agent Multi-Role Reasoning system.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

JSONDict = Dict[str, Any]


@dataclass
class Plan:
    """
    执行计划
    
    Attributes:
        plan_id: 计划唯一标识
        goal: 任务目标
        steps: 步骤列表，每个步骤包含action和reasoning
        dependencies: 依赖关系映射 {step_index: [dependent_step_indices]}
        current_step: 当前执行步骤索引
    """
    plan_id: str
    goal: str
    steps: List[Dict[str, Any]]  # 步骤列表
    dependencies: Dict[int, List[int]] = field(default_factory=dict)  # 依赖关系
    current_step: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": self.steps,
            "dependencies": self.dependencies,
            "current_step": self.current_step,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        """从字典创建"""
        return cls(
            plan_id=data["plan_id"],
            goal=data["goal"],
            steps=data["steps"],
            dependencies=data.get("dependencies", {}),
            current_step=data.get("current_step", 0),
        )
    
    def get_next_step(self) -> Optional[Dict[str, Any]]:
        """获取下一个步骤"""
        if self.current_step >= len(self.steps):
            return None
        return self.steps[self.current_step]
    
    def advance_step(self) -> None:
        """推进到下一步"""
        self.current_step += 1
    
    def is_complete(self) -> bool:
        """检查计划是否完成"""
        return self.current_step >= len(self.steps)
