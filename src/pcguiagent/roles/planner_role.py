"""
Planner Role - Task Planning and Decomposition

Encapsulates RecursivePlanner to provide planning services via direct method calls.
"""
import json
import uuid
from typing import Dict, Optional, Any

from pcguiagent.utils.logger import get_logger
from pcguiagent.roles.base_role import BaseRole
from pcguiagent.core.types import Plan

logger = get_logger("PlannerRole")


class PlannerRole(BaseRole):
    """
    规划角色 - 负责任务规划和分解
    
    封装 RecursivePlanner，通过直接方法调用提供规划服务
    """
    
    def __init__(self, planner: Any, agent: Optional[Any] = None):
        """
        初始化 PlannerRole
        
        Args:
            planner: RecursivePlanner 实例
            agent: 所属的 Agent 实例（可选）
        """
        super().__init__("planner_role", "planner", agent)
        self.planner = planner
        self._capabilities = ["plan", "replan", "get_next_step"]
    
    async def plan(
        self,
        goal: str,
        observation: Optional[Dict[str, Any]] = None,
        memory_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成计划
        
        Args:
            goal: 任务目标
            observation: 观察数据
            memory_context: 记忆上下文
        
        Returns:
            包含 plan 或 is_done 的字典
        """
        logger.info(f"[PlannerRole] Planning for goal: {goal[:100]}...")
        logger.info(f"[PlannerRole] Observation provided: {observation is not None}")
        if observation:
            logger.info(f"[PlannerRole] Observation keys: {list(observation.keys())}")
            if "accessibility_tree" in observation:
                a11y_len = len(observation["accessibility_tree"])
                logger.info(f"[PlannerRole] Observation accessibility_tree length: {a11y_len} chars")
            if "screenshot" in observation:
                screenshot_size = len(observation["screenshot"]) if isinstance(observation["screenshot"], bytes) else "N/A"
                logger.info(f"[PlannerRole] Observation screenshot size: {screenshot_size} bytes")
        
        plan_output = await self.planner.generate_plan(
            goal=goal,
            observation=observation,
            memory_context=memory_context
        )
        
        # 解析计划输出
        logger.info(f"[PlannerRole] Parsing plan output...")
        logger.info(f"[PlannerRole] Plan output length: {len(plan_output)} chars")
        logger.debug(f"[PlannerRole] Plan output preview: {plan_output[:500]}...")
        
        try:
            plan_data = json.loads(plan_output)
            logger.info(f"[PlannerRole] Plan data parsed successfully")
            logger.info(f"[PlannerRole] Plan data keys: {list(plan_data.keys())}")
            
            if plan_data.get("is_done"):
                logger.info(f"[PlannerRole] Plan indicates task is done")
                return {
                    "success": True,
                    "is_done": True,
                    "output": plan_data.get("output"),
                }
            
            # 提取计划步骤
            steps = plan_data.get("plan", [])
            logger.info(f"[PlannerRole] Extracted {len(steps)} steps from plan")
            if not steps:
                logger.error(f"[PlannerRole] Generated plan is EMPTY!")
                logger.error(f"[PlannerRole] Plan data: {plan_data}")
                return {
                    "success": False,
                    "error": "Generated plan is empty"
                }
            
            # Log each step
            logger.info(f"[PlannerRole] ===== Plan Steps Details =====")
            for i, step in enumerate(steps):
                action = step.get("action", {})
                action_type = action.get("action_type") if isinstance(action, dict) else str(action)
                action_name = action.get("name") if isinstance(action, dict) else None
                logger.info(f"[PlannerRole] Step {i+1}: action_type={action_type}, name={action_name}")
                logger.debug(f"[PlannerRole] Step {i+1} full content: {step}")
            logger.info(f"[PlannerRole] ===== End Plan Steps =====")
            
            # 创建 Plan 对象
            plan = Plan(
                plan_id=str(uuid.uuid4()),
                goal=goal,
                steps=steps,
            )
            
            logger.info(f"[PlannerRole] Plan object created with {len(steps)} steps")
            
            return {
                "success": True,
                "plan": plan.to_dict(),
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"[PlannerRole] Failed to parse plan output JSON: {e}")
            logger.error(f"[PlannerRole] Plan output that failed to parse: {plan_output[:1000]}...")
            return {
                "success": False,
                "error": f"Failed to parse plan output: {e}"
            }
    
    async def replan(
        self,
        goal: str,
        observation: Optional[Dict[str, Any]] = None,
        memory_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        重新规划当前步骤
        
        Args:
            goal: 任务目标
            observation: 观察数据
            memory_context: 记忆上下文
        
        Returns:
            包含 plan 的字典
        """
        logger.info(f"[PlannerRole] Replanning for goal: {goal[:100]}...")
        
        plan_output = await self.planner.replan_current_step(
            goal=goal,
            observation=observation,
            memory_context=memory_context
        )
        
        try:
            plan_data = json.loads(plan_output)
            steps = plan_data.get("plan", [])
            
            if steps:
                plan = Plan(
                    plan_id=str(uuid.uuid4()),
                    goal=goal,
                    steps=steps,
                )
                return {
                    "success": True,
                    "plan": plan.to_dict(),
                }
            else:
                return {
                    "success": False,
                    "error": "Replan failed: no steps generated"
                }
        
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse replan output: {e}"
            }
    
    async def get_next_step(
        self,
        goal: str,
        observation: Optional[Dict[str, Any]] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        获取下一步 action（JSON 字符串）
        
        Args:
            goal: 任务目标
            observation: 观察数据
            memory_context: 记忆上下文
        
        Returns:
            JSON 格式的 action 字符串
        """
        logger.info(f"[PlannerRole] Getting next step for goal: {goal[:100]}...")
        
        action_output = await self.planner.next_action(
            goal=goal,
            observation=observation,
            memory_context=memory_context
        )
        
        logger.info(f"[PlannerRole] Next step output length: {len(action_output)} chars")
        return action_output

