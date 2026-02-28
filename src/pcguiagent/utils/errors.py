

class AgentError(Exception):
    """Agent 运行中发生的通用错误"""
    pass


class ToolExecutionError(AgentError):
    """MCP 工具执行失败"""
    pass


class LLMOutputError(AgentError):
    """LLM 输出格式错误"""
    pass


class PlanningError(AgentError):
    """Planner 生成计划失败"""
    pass
