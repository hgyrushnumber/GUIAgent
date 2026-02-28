"""
Base Role Class

All roles in the Intra-Agent Multi-Role Reasoning system inherit from this base class.
Roles communicate through direct method calls instead of message passing.
"""
from abc import ABC
from typing import Optional, Dict, Any

from pcguiagent.utils.logger import get_logger

logger = get_logger("BaseRole")


class BaseRole(ABC):
    """
    所有角色的基类
    
    提供：
    - 统一的角色接口
    - 角色标识和能力定义
    - 共享状态访问（通过 agent 实例）
    """
    
    def __init__(self, role_id: str, role_type: str, agent: Optional[Any] = None):
        """
        初始化角色
        
        Args:
            role_id: 角色唯一标识
            role_type: 角色类型（planner, memory, reflector等）
            agent: 所属的 Agent 实例（用于访问共享状态）
        """
        self.role_id = role_id
        self.role_type = role_type
        self.agent = agent
        self._capabilities: list[str] = []
    
    @property
    def capabilities(self) -> list[str]:
        """角色能力列表"""
        return self._capabilities
    
    def set_agent(self, agent: Any) -> None:
        """
        设置所属的 Agent 实例
        
        Args:
            agent: Agent 实例
        """
        self.agent = agent
        logger.debug(f"[{self.role_id}] Agent reference set")
    
    def get_shared_state(self) -> Dict[str, Any]:
        """
        获取共享状态（从 agent 实例）
        
        Returns:
            共享状态字典
        """
        if self.agent and hasattr(self.agent, '_shared_state'):
            return self.agent._shared_state
        return {}
    
    def update_shared_state(self, key: str, value: Any) -> None:
        """
        更新共享状态
        
        Args:
            key: 状态键
            value: 状态值
        """
        if self.agent and hasattr(self.agent, '_shared_state'):
            self.agent._shared_state[key] = value
            logger.debug(f"[{self.role_id}] Updated shared state: {key}")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.role_id}, type={self.role_type})"

