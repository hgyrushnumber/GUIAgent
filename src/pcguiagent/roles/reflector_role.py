"""
Reflector Role - Task Verification and Reflection

Encapsulates TaskVerifier to provide verification and reflection services via direct method calls.
"""
from typing import Dict, Optional, Any, List

from pcguiagent.utils.logger import get_logger
from pcguiagent.roles.base_role import BaseRole

logger = get_logger("ReflectorRole")


class ReflectorRole(BaseRole):
    """
    反思角色 - 负责任务验证和反思
    
    封装 TaskVerifier，提供验证和修复服务
    """
    
    def __init__(self, task_verifier: Any, plan_repair: Optional[Any] = None, agent: Optional[Any] = None):
        """
        初始化 ReflectorRole
        
        Args:
            task_verifier: TaskVerifier 实例
            plan_repair: PlanRepair 实例（可选）
            agent: 所属的 Agent 实例（可选）
        """
        super().__init__("reflector_role", "reflector", agent)
        self.task_verifier = task_verifier
        self.plan_repair = plan_repair
        self._capabilities = ["verify_completion", "analyze_error", "suggest_fix", "repair_plan"]
    
    async def verify_completion(
        self,
        goal: str,
        results: List[Dict[str, Any]],
        observation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        验证任务完成
        
        Args:
            goal: 任务目标
            results: 执行结果列表
            observation: 观察数据
        
        Returns:
            验证结果字典
        """
        logger.info(f"[ReflectorRole] Verifying task completion: {goal[:100]}...")
        
        # 构建 action_history（从 results 提取）
        action_history = []
        for result in results:
            action_history.append({
                "action": result.get("action", {}),
                "result": result.get("result", {}),
            })
        
        # 调用 TaskVerifier 验证
        try:
            verification = await self.task_verifier.verify_completion(
                goal=goal,
                final_output=None,  # 从 observation 或 results 中提取
                action_history=action_history,
                observation=observation
            )
            
            logger.info(
                f"[ReflectorRole] Verification result: "
                f"is_complete={verification.get('is_complete')}, "
                f"confidence={verification.get('confidence', 0.0):.2f}"
            )
            
            return {
                "success": True,
                "verification": verification,
            }
        except Exception as e:
            logger.error(f"[ReflectorRole] Verification failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def analyze_error(self, error: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        分析错误
        
        Args:
            error: 错误信息
            context: 上下文
        
        Returns:
            错误分析结果
        """
        logger.info(f"[ReflectorRole] Analyzing error: {error[:100] if error else 'Unknown'}...")
        
        # 简单的错误分析（可以扩展为更复杂的分析）
        error_type = "unknown"
        if error:
            error_lower = error.lower()
            if "timeout" in error_lower:
                error_type = "timeout"
            elif "not found" in error_lower or "不存在" in error_lower:
                error_type = "not_found"
            elif "permission" in error_lower or "权限" in error_lower:
                error_type = "permission"
            elif "invalid" in error_lower or "无效" in error_lower:
                error_type = "invalid"
        
        analysis = {
            "error_type": error_type,
            "error_message": error,
            "context": context or {},
            "severity": "medium",  # low, medium, high
        }
        
        logger.debug(f"[ReflectorRole] Error analysis: {error_type}")
        return {
            "success": True,
            "analysis": analysis,
        }
    
    def suggest_fix(self, error_analysis: Dict[str, Any]) -> List[str]:
        """
        建议修复
        
        Args:
            error_analysis: 错误分析结果
        
        Returns:
            修复建议列表
        """
        error_type = error_analysis.get("analysis", {}).get("error_type", "unknown")
        suggestions = []
        
        if error_type == "timeout":
            suggestions = [
                "Wait longer before retrying",
                "Check if the target element is loading",
                "Try a different approach to access the element"
            ]
        elif error_type == "not_found":
            suggestions = [
                "Verify the element exists in the current view",
                "Check if the element identifier is correct",
                "Try using a different selector or method"
            ]
        elif error_type == "permission":
            suggestions = [
                "Check if you have the necessary permissions",
                "Try running with elevated privileges",
                "Verify the file or resource is accessible"
            ]
        else:
            suggestions = [
                "Review the error message for details",
                "Check the logs for more information",
                "Try a different approach"
            ]
        
        logger.debug(f"[ReflectorRole] Suggested {len(suggestions)} fixes")
        return suggestions
    
    async def repair_plan(self, plan_output: str) -> str:
        """
        修复计划
        
        Args:
            plan_output: 计划输出字符串
        
        Returns:
            修复后的计划输出
        """
        if not self.plan_repair:
            logger.warning("[ReflectorRole] PlanRepair not available, returning original output")
            return plan_output
        
        logger.info("[ReflectorRole] Repairing plan...")
        try:
            repaired = await self.plan_repair.repair_plan(plan_output)
            logger.info(f"[ReflectorRole] Plan repaired: {len(repaired)} chars")
            return repaired
        except Exception as e:
            logger.error(f"[ReflectorRole] Plan repair failed: {e}")
            return plan_output

