import json
from typing import Any, Dict

from pcguiagent.utils.logger import get_logger
from pcguiagent.llms.prompt_templates import get_dsl

logger = get_logger("PlanRepair") 

class PlanRepair:
    """
    负责在以下情况进行修复：
    - LLM 输出 JSON 不合法
    - Action 名称不存在 / 无效
    - 工具执行失败，需要调整参数或者换工具

    ReasoningEngine 和 ErrorHandler 会调用：
    - repair_plan(raw_text)
    - repair_action(error_context)
    """

    def __init__(self, llm, tool_registry):
        self.llm = llm
        self.tool_registry = tool_registry
        self.dsl = get_dsl()

    # =================================
    # 修复 LLM 输出（JSON 解析失败）
    # =================================
    async def repair_plan(self, raw_output: str) -> str:
        """
        给 LLM 看它自己错误的输出，让它包一层正确 JSON。
        """
        tool_list = sorted(self.tool_registry.keys())
        tools_description = self.tool_registry.get_tools_description_for_prompt()

        # 使用 DSL 和模板引擎生成 JSON 修复提示词
        prompt = self.dsl.json_repair(
            invalid_output=raw_output,
            tools_description=tools_description,
            tool_names=tool_list
        )

        # Save prompt for trace collector
        self._last_repair_prompt = prompt

        logger.info("[PlanRepair] Repairing invalid JSON plan...")
        logger.info(f"[PlanRepair] ===== JSON REPAIR PROMPT =====")
        logger.info(f"[PlanRepair] Full repair prompt:\n{prompt}")
        logger.info(f"[PlanRepair] ===== END PROMPT =====")
        
        fixed = await self.llm.acomplete(prompt)
        
        # Log response
        response_chars = len(fixed)
        logger.info(f"[PlanRepair] Repair response: {response_chars} chars")
        logger.info(f"[PlanRepair] ===== JSON REPAIR RESPONSE =====")
        logger.info(f"[PlanRepair] Full repair response:\n{fixed}")
        logger.info(f"[PlanRepair] ===== END RESPONSE =====")

        # 尝试快速验证，如果仍不是 JSON，就强制包装
        try:
            json.loads(fixed)
            return fixed
        except Exception:
            logger.warning("[PlanRepair] LLM still failed to produce JSON, wrapping fallback.")
            return json.dumps({
                "thought": "Fallback: LLM failed to repair JSON, mark task as failed.",
                "output": "PLAN_REPAIR_FAILED",
                "is_done": True,
            })

    # =================================
    # 修复执行失败的 Action
    # =================================
    async def repair_action(self, error_context: str) -> str:
        """
        当工具执行失败时，请 LLM 根据 error_context 修改 Action。
        返回值为新的 JSON plan 字符串。
        """
        tools_description = self.tool_registry.get_tools_description_for_prompt()

        # 使用 DSL 和模板引擎生成动作修复提示词
        prompt = self.dsl.action_repair(
            error_context=error_context,
            tools_description=tools_description
        )

        # Save prompt for trace collector
        self._last_repair_prompt = prompt

        logger.info("[PlanRepair] Repairing failed action...")
        logger.info(f"[PlanRepair] ===== ACTION REPAIR PROMPT =====")
        logger.info(f"[PlanRepair] Full repair prompt:\n{prompt}")
        logger.info(f"[PlanRepair] ===== END PROMPT =====")
        
        fixed = await self.llm.acomplete(prompt)
        
        # Log response
        response_chars = len(fixed)
        logger.info(f"[PlanRepair] Action repair response: {response_chars} chars")
        logger.info(f"[PlanRepair] ===== ACTION REPAIR RESPONSE =====")
        logger.info(f"[PlanRepair] Full repair response:\n{fixed}")
        logger.info(f"[PlanRepair] ===== END RESPONSE =====")
        
        return fixed
