"""
Memory Role - Memory Management

Encapsulates MemoryStorage to provide memory services via direct method calls.
"""
from typing import Dict, Optional, Any, List

from pcguiagent.utils.logger import get_logger
from pcguiagent.roles.base_role import BaseRole

logger = get_logger("MemoryRole")


class MemoryRole(BaseRole):
    """
    记忆角色 - 负责记忆管理
    
    封装 MemoryStorage，提供记忆存储、检索、上下文构建接口
    """
    
    def __init__(self, memory: Any, agent: Optional[Any] = None):
        """
        初始化 MemoryRole
        
        Args:
            memory: MemoryStorage 实例
            agent: 所属的 Agent 实例（可选）
        """
        super().__init__("memory_role", "memory", agent)
        self.memory = memory
        self._capabilities = [
            "store_context",
            "retrieve_context",
            "build_context",
            "search_memory",
            "add_event",
        ]
    
    def store_context(self, key: str, value: Any) -> bool:
        """
        存储上下文
        
        Args:
            key: 上下文键
            value: 上下文值
        
        Returns:
            是否成功
        """
        try:
            self.memory.set_context(key, value)
            logger.debug(f"[MemoryRole] Stored context: {key}")
            return True
        except Exception as e:
            logger.error(f"[MemoryRole] Failed to store context: {e}")
            return False
    
    def retrieve_context(self, key: str, default: Any = None) -> Any:
        """
        检索上下文
        
        Args:
            key: 上下文键
            default: 默认值
        
        Returns:
            上下文值
        """
        try:
            value = self.memory.get_context(key, default)
            logger.debug(f"[MemoryRole] Retrieved context: {key}")
            return value
        except Exception as e:
            logger.error(f"[MemoryRole] Failed to retrieve context: {e}")
            return default
    
    def build_context(self, include_types: Optional[List[str]] = None) -> str:
        """
        构建完整上下文
        
        Args:
            include_types: 包含的类型列表（可选）
        
        Returns:
            上下文字符串
        """
        try:
            # 使用 ContextBuilder 构建上下文
            from pcguiagent.memory.context_builder import MemoryContextBuilder
            builder = MemoryContextBuilder(self.memory)
            context = builder.build_context(include_raw=False)
            
            logger.debug(f"[MemoryRole] Built context ({len(context)} chars)")
            return context
        except Exception as e:
            logger.error(f"[MemoryRole] Failed to build context: {e}")
            return ""
    
    def search_memory(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
        
        Returns:
            搜索结果列表
        """
        try:
            # 简单的搜索实现（可以扩展为更复杂的搜索）
            results = []
            # 从 episodic memory 中搜索
            if hasattr(self.memory, 'episodic') and hasattr(self.memory.episodic, '_events'):
                for event in self.memory.episodic._events[-limit:]:
                    if query.lower() in str(event).lower():
                        results.append(event)
            
            logger.debug(f"[MemoryRole] Search results: {len(results)} items")
            return results
        except Exception as e:
            logger.error(f"[MemoryRole] Failed to search memory: {e}")
            return []
    
    def add_event(self, step: int, goal: str, action: Any, result: Any) -> bool:
        """
        添加事件
        
        Args:
            step: 步骤号
            goal: 任务目标
            action: 动作
            result: 结果
        
        Returns:
            是否成功
        """
        try:
            self.memory.add_event(step, goal, action, result)
            logger.debug(f"[MemoryRole] Added event: step {step}")
            return True
        except Exception as e:
            logger.error(f"[MemoryRole] Failed to add event: {e}")
            return False

