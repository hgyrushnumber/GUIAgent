from typing import Dict, Callable, Any

from pcguiagent.core.action_schema.action import Action


class ActionRegistry:
    """
    全局 Action -> Tool 映射表
    StepExecutor 会通过此处找到对应工具的执行函数
    """

    def __init__(self):
        self._registry: Dict[str, Callable[..., Any]] = {}

    def register(self, action_name: str, handler: Callable[..., Any]):
        self._registry[action_name] = handler

    def get(self, action_name: str) -> Callable[..., Any]:
        return self._registry.get(action_name)


# 全局单例
action_registry = ActionRegistry()


def register_action(name: str):
    """
    装饰器方式注册 Action
    @register_action("click")
    def click_handler(...):
    """
    def decorator(func):
        action_registry.register(name, func)
        return func
    return decorator
