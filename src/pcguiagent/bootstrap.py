import yaml
import os
from pathlib import Path
from typing import Optional, Dict, Any

from pcguiagent.core.config import Config
from pcguiagent.utils.config_loader import find_config_file
from pcguiagent.llms.base_client import BaseLLMClient
from pcguiagent.llms.factory import build_llm_client

from pcguiagent.memory.storage import MemoryStorage

from pcguiagent.planners.recursive_planner import RecursivePlanner

from pcguiagent.agents.task_verifier import TaskVerifier

# Note: Multi-Agent imports removed - using Intra-Agent Multi-Role Reasoning architecture

from pcguiagent.utils.logger import get_logger
from pcguiagent.utils.app_detector import AppDetector

# Note: Observability imports removed - not used in Intra-Agent Multi-Role Reasoning architecture

# MetricsTracker - try to import from evaluation, fallback to simple version
try:
    import sys
    from pathlib import Path
    # Add parent directory to path to import from evaluation
    parent_dir = Path(__file__).parent.parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from evaluation.metrics_tracker import MetricsTracker
except ImportError:
    # Create a simple MetricsTracker if evaluation module not available
    from typing import Dict, Any, List, Optional
    from datetime import datetime
    
    class MetricsTracker:
        """Simple metrics tracker for OSWorld evaluation"""
        def __init__(self):
            self.tool_invocations: List[Dict[str, Any]] = []
            self.decisions: List[Dict[str, Any]] = []
            self.total_steps = 0
            self.task_start_time: Optional[datetime] = None
            self.task_end_time: Optional[datetime] = None
        
        def start_task(self):
            self.tool_invocations.clear()
            self.decisions.clear()
            self.total_steps = 0
            self.task_start_time = datetime.now()
        
        def record_invocation(self, tool_name: str, is_mcp: bool, success: bool, execution_time: float, error: Optional[str] = None):
            self.tool_invocations.append({
                "tool_name": tool_name,
                "is_mcp": is_mcp,
                "success": success,
                "execution_time": execution_time,
                "error": error,
            })
            self.total_steps += 1
        
        def record_decision(self, step: int, tool_name: str, is_mcp: bool, decision_correct: bool, reasoning: Optional[str] = None):
            self.decisions.append({
                "step": step,
                "tool_name": tool_name,
                "is_mcp": is_mcp,
                "decision_correct": decision_correct,
                "reasoning": reasoning,
            })
        
        def end_task(self):
            self.task_end_time = datetime.now()
        
        def get_metrics(self) -> Dict[str, Any]:
            correct = sum(1 for d in self.decisions if d.get("decision_correct"))
            total = len(self.decisions)
            tir = (correct / total * 100) if total > 0 else 0.0
            
            mcp_calls = sum(1 for inv in self.tool_invocations if inv.get("is_mcp"))
            mcp_successful = sum(1 for inv in self.tool_invocations if inv.get("is_mcp") and inv.get("success"))
            
            return {
                "total_steps": self.total_steps,
                "tool_invocation_rate": tir,
                "total_invocations": len(self.tool_invocations),
                "total_decisions": len(self.decisions),
                "correct_decisions": correct,
                "mcp_tool_calls": mcp_calls,
                "gui_actions": len(self.tool_invocations) - mcp_calls,
                "mcp_success_rate": (mcp_successful / mcp_calls * 100) if mcp_calls > 0 else 0.0,
                "mcp_call_rate": (mcp_calls / self.total_steps * 100) if self.total_steps > 0 else 0.0,
            }
        
        def reset(self):
            self.tool_invocations.clear()
            self.decisions.clear()
            self.total_steps = 0
            self.task_start_time = None
            self.task_end_time = None

logger = get_logger("Bootstrap")


class Bootstrap:
    """
    Build the OSWorld-Optimized Agent instance.
    """

    def __init__(self, config_path: str):
        # Resolve config path using unified config loader
        config_file = find_config_file(config_path, module_dir=Path(__file__).parent)
        
        with open(config_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        
        if not raw:
            raise ValueError(f"Config file is empty or invalid: {config_file}")
        
        self.config = Config.from_dict(raw)

    async def build_agent(self) -> Dict[str, Any]:
        """
        Build Intra-Agent Multi-Role Reasoning system.
        
        Returns:
            Dict with components (llm, memory, planner, task_verifier)
        """
        return await self.build_intra_agent()
    
    async def build_intra_agent(self) -> Dict[str, Any]:
        """
        Build Intra-Agent Multi-Role Reasoning system.
        Returns a dict with all components needed for roles.
        """
        logger.info("=" * 80)
        logger.info("Building Intra-Agent Multi-Role Reasoning System")
        logger.info("=" * 80)
        
        # -------------------------------
        # 1. LLM
        # -------------------------------
        logger.info("Step 1/4: Initializing LLM...")
        llm = self._build_llm()
        logger.info(f"✅ LLM initialized: {self.config.llm.provider}/{self.config.llm.model}")
        
        # -------------------------------
        # 2. Memory
        # -------------------------------
        logger.info("Step 2/4: Initializing Memory...")
        memory = MemoryStorage(self.config.memory)
        logger.info("✅ Memory initialized")
        
        # -------------------------------
        # 3. Planner
        # -------------------------------
        logger.info("Step 3/4: Initializing Planner...")
        tool_registry = None  # OSWorld mode: no MCP, no tool registry
        planner = RecursivePlanner(llm, memory, tool_registry, config=self.config)
        logger.info("✅ Planner initialized")
        logger.info("  → OSWorld mode: Planner will use pyautogui actions (no MCP tools)")
        
        # -------------------------------
        # 4. Task Verifier
        # -------------------------------
        logger.info("Step 4/4: Initializing Task Verifier...")
        from pcguiagent.utils.app_detector import AppDetector
        from pcguiagent.agents.task_verifier import TaskVerifier
        app_detector = AppDetector()
        task_verifier = TaskVerifier(memory=memory, app_detector=app_detector)
        logger.info("✅ Task Verifier initialized")
        
        logger.info("=" * 80)
        logger.info("Intra-Agent Multi-Role Reasoning System build complete!")
        logger.info("=" * 80)
        
        return {
            "llm": llm,
            "memory": memory,
            "planner": planner,
            "task_verifier": task_verifier,
        }
    
    # ---------------------------------
    # Private helpers
    # ---------------------------------
    def _build_llm(self) -> BaseLLMClient:
        return build_llm_client(self.config.llm)
