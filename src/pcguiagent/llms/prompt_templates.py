"""
Prompt Template Management System
Uses the Jinja2 template engine to manage and render prompts.
Supports a DSL (Domain Specific Language) interface.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from pcguiagent.utils.logger import get_logger

logger = get_logger("PromptTemplates")


class PromptTemplateManager:
    """
    Prompt template manager.
    Uses the Jinja2 engine to load and render templates.
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the template manager.
        
        Args:
            template_dir: Template directory path, defaults to llms/templates
        """
        if template_dir is None:
            # Default template directory: templates directory next to this file
            current_file = Path(__file__).parent
            template_dir = str(current_file / "templates")
        
        self.template_dir = Path(template_dir)
        
        if not self.template_dir.exists():
            logger.warning(f"Template directory not found: {template_dir}, creating...")
            self.template_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Cache for loaded templates
        self._template_cache: Dict[str, Any] = {}
        
        logger.info(f"[PromptTemplateManager] Initialized with template dir: {template_dir}")
    
    def get_template(self, template_name: str):
        """
        Get a template with caching.
        
        Args:
            template_name: Template file name (without .jinja)
            
        Returns:
            Jinja2 Template object
        """
        if template_name not in self._template_cache:
            try:
                template_file = f"{template_name}.jinja"
                self._template_cache[template_name] = self.env.get_template(template_file)
                logger.debug(f"[PromptTemplateManager] Loaded template: {template_file}")
            except Exception as e:
                logger.error(f"[PromptTemplateManager] Failed to load template {template_name}: {e}")
                raise
        
        return self._template_cache[template_name]
    
    def render(self, template_name: str, **kwargs) -> str:
        """
        Render a template.
        
        Args:
            template_name: Template name
            **kwargs: Template variables
            
        Returns:
            Rendered string
        """
        template = self.get_template(template_name)
        return template.render(**kwargs)
    
    def render_system_prompt(self) -> str:
        """Get the system prompt"""
        return self.render("system_prompt")
    
    def render_plan_generate(
        self,
        goal: str,
        observation: str,
        tools_description: str,
        action_history: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        Render the plan-generation prompt.
        
        Args:
            goal: Task goal
            observation: Current observation
            tools_description: Tool descriptions
            action_history: Action history (optional)
            memory_context: Working-memory context (optional)
            
        Returns:
            Rendered prompt
        """
        return self.render(
            "plan_generate",
            system_prompt=self.render_system_prompt(),
            goal=goal,
            observation=observation,
            action_history=action_history or "",
            memory_context=memory_context or "",
            tools_description=tools_description
        )
    
    def render_plan_generate_osworld(
        self,
        goal: str,
        observation: str,
        tools_description: str,
        action_history: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        Render the OSWorld-specific plan-generation prompt.
        
        Args:
            goal: Task goal
            observation: Current observation (accessibility tree)
            tools_description: PyAutoGUI action descriptions
            action_history: Action history (optional)
            memory_context: Working-memory context (optional)
            
        Returns:
            Rendered prompt
        """
        return self.render(
            "plan_generate_osworld",
            system_prompt=self.render_system_prompt(),
            goal=goal,
            observation=observation,
            action_history=action_history or "",
            memory_context=memory_context or "",
            tools_description=tools_description
        )
    
    def render_next_action_osworld(
        self,
        goal: str,
        observation: str,
        tools_description: str,
        action_history: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        Render the OSWorld-specific step-by-step next-action prompt.
        
        Args:
            goal: Task goal
            observation: Current observation (preprocessed UI components)
            tools_description: PyAutoGUI action descriptions
            action_history: Action history (optional)
            memory_context: Working-memory context (optional)
            
        Returns:
            Rendered prompt
        """
        return self.render(
            "next_action_osworld",
            system_prompt=self.render_system_prompt(),
            goal=goal,
            observation=observation,
            action_history=action_history or "",
            memory_context=memory_context or "",
            tools_description=tools_description
        )
    
    def render_plan_replan(
        self,
        goal: str,
        observation: str,
        current_step: str,
        previous_steps: str,
        remaining_steps: str,
        tools_description: str,
        tool_names: str,
        error_info: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        Render the local replan prompt for the current step.
        
        Args:
            goal: Task goal
            observation: Current observation
            current_step: The current failed step (JSON string)
            previous_steps: Completed steps (JSON string)
            remaining_steps: Remaining steps (JSON string)
            tools_description: Tool descriptions
            tool_names: List of tool names (comma separated)
            error_info: Error details (optional)
            memory_context: Working-memory context (optional)
            
        Returns:
            Rendered prompt
        """
        return self.render(
            "plan_replan",
            system_prompt=self.render_system_prompt(),
            goal=goal,
            observation=observation,
            error_info=error_info or "",
            current_step=current_step,
            previous_steps=previous_steps or "None",
            remaining_steps=remaining_steps or "None",
            memory_context=memory_context or "",
            tools_description=tools_description,
            tool_names=tool_names
        )
    
    def render_task_breakdown(self, goal: str) -> str:
        """
        Render the task-decomposition prompt.
        
        Args:
            goal: Task goal
            
        Returns:
            Rendered prompt
        """
        return self.render(
            "task_breakdown",
            system_prompt=self.render_system_prompt(),
            goal=goal
        )
    
    def render_plan_repair(
        self,
        invalid_output: str,
        tools_description: str,
        tool_names: str
    ) -> str:
        """
        Render the plan-repair prompt (for JSON parsing failures).
        
        Args:
            invalid_output: Invalid output string
            tools_description: Tool descriptions
            tool_names: List of tool names (comma separated)
            
        Returns:
            Rendered prompt
        """
        return self.render(
            "plan_repair",
            system_prompt=self.render_system_prompt(),
            invalid_output=invalid_output,
            tools_description=tools_description,
            tool_names=tool_names
        )
    
    def render_action_repair(
        self,
        error_context: str,
        tools_description: str
    ) -> str:
        """
        Render the action-repair prompt (execution failed).
        
        Args:
            error_context: Error context
            tools_description: Tool descriptions
            
        Returns:
            Rendered prompt
        """
        return self.render(
            "action_repair",
            system_prompt=self.render_system_prompt(),
            error_context=error_context,
            tools_description=tools_description
        )


# Global template manager instance (singleton)
_template_manager: Optional[PromptTemplateManager] = None


def get_template_manager() -> PromptTemplateManager:
    """
    Get the global template manager instance (singleton).
    
    Returns:
        PromptTemplateManager instance
    """
    global _template_manager
    if _template_manager is None:
        _template_manager = PromptTemplateManager()
    return _template_manager


# ============================================================================
# DSL (Domain Specific Language) interface
# ============================================================================

class PromptDSL:
    """
    Prompt DSL (domain-specific language) interface.
    Provides a concise API to generate different kinds of prompts.
    """
    
    def __init__(self, template_manager: Optional[PromptTemplateManager] = None):
        """
        Initialize the DSL.
        
        Args:
            template_manager: Template manager, defaults to the global instance
        """
        self.tm = template_manager or get_template_manager()
    
    def plan_generation(
        self,
        goal: str,
        observation: str = "None (initial planning)",
        tools_description: str = "",
        action_history: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        DSL: Generate a planning prompt.
        
        Example:
            prompt = dsl.plan_generation(
                goal="open vscode",
                observation="...",
                tools_description="..."
            )
        """
        return self.tm.render_plan_generate(
            goal=goal,
            observation=observation,
            tools_description=tools_description,
            action_history=action_history,
            memory_context=memory_context
        )
    
    def plan_generation_osworld(
        self,
        goal: str,
        observation: str = "None (initial planning)",
        tools_description: str = "",
        action_history: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        DSL: Generate an OSWorld-specific planning prompt.
        
        Example:
            prompt = dsl.plan_generation_osworld(
                goal="open vscode",
                observation="...",
                tools_description="..."
            )
        """
        return self.tm.render_plan_generate_osworld(
            goal=goal,
            observation=observation,
            tools_description=tools_description,
            action_history=action_history,
            memory_context=memory_context
        )
    
    def next_action_osworld(
        self,
        goal: str,
        observation: str,
        tools_description: str,
        action_history: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        DSL: Generate an OSWorld-specific step-by-step next-action prompt.
        
        Example:
            prompt = dsl.next_action_osworld(
                goal="open vscode",
                observation="...",
                tools_description="...",
                action_history="..."
            )
        """
        return self.tm.render_next_action_osworld(
            goal=goal,
            observation=observation,
            tools_description=tools_description,
            action_history=action_history,
            memory_context=memory_context
        )
    
    def step_replan(
        self,
        goal: str,
        observation: str,
        current_step: dict,
        previous_steps: list,
        remaining_steps: list,
        tools_description: str,
        tool_names: list,
        error_info: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> str:
        """
        DSL: Local replan prompt for the current step.
        
        Example:
            prompt = dsl.step_replan(
                goal="...",
                observation="...",
                current_step={"step": 1, "action": {...}},
                previous_steps=[],
                remaining_steps=[...],
                tools_description="...",
                tool_names=["code.launch_vscode", ...],
                error_info="..."
            )
        """
        import json
        return self.tm.render_plan_replan(
            goal=goal,
            observation=observation,
            current_step=json.dumps(current_step, ensure_ascii=False, indent=2),
            previous_steps=json.dumps(previous_steps, ensure_ascii=False, indent=2) if previous_steps else "None",
            remaining_steps=json.dumps(remaining_steps, ensure_ascii=False, indent=2) if remaining_steps else "None",
            tools_description=tools_description,
            tool_names=", ".join(tool_names),
            error_info=error_info,
            memory_context=memory_context
        )
    
    def task_decomposition(self, goal: str) -> str:
        """
        DSL: Task decomposition prompt.
        
        Example:
            prompt = dsl.task_decomposition(goal="open vscode and create excel")
        """
        return self.tm.render_task_breakdown(goal=goal)
    
    def json_repair(self, invalid_output: str, tools_description: str, tool_names: list) -> str:
        """
        DSL: JSON repair prompt.
        
        Example:
            prompt = dsl.json_repair(
                invalid_output="...",
                tools_description="...",
                tool_names=["code.*", "excel.*"]
            )
        """
        return self.tm.render_plan_repair(
            invalid_output=invalid_output,
            tools_description=tools_description,
            tool_names=", ".join(tool_names)
        )
    
    def action_repair(self, error_context: str, tools_description: str) -> str:
        """
        DSL: Action repair prompt.
        
        Example:
            prompt = dsl.action_repair(
                error_context="Tool execution failed: ...",
                tools_description="..."
            )
        """
        return self.tm.render_action_repair(
            error_context=error_context,
            tools_description=tools_description
        )


# Global DSL instance for convenience
_dsl_instance: Optional[PromptDSL] = None


def get_dsl() -> PromptDSL:
    """
    Get the global DSL instance.
    
    Returns:
        PromptDSL instance
    """
    global _dsl_instance
    if _dsl_instance is None:
        _dsl_instance = PromptDSL()
    return _dsl_instance


# ============================================================================
# Backward compatibility: keep legacy constants (deprecated)
# ============================================================================

SYSTEM_PROMPT = """
You are an OSWorld GUI agent specializing in tool-based reasoning.
You must ALWAYS output pure JSON in one of the mandatory formats.
Do NOT output natural language outside JSON.
"""

TASK_DECOMPOSE_PROMPT = """
Decompose the high-level goal into 3-7 clear subtasks. Use numbered list:
1. ...
2. ...
"""

ACTION_PLAN_PROMPT = """
Generate next action according to OSWorld schema.

Schema for actions:
{
  "thought": "reasoning",
  "action": {
    "name": "<tool>",
    "args": { ... }
  },
  "is_done": false
}

Schema for final answer:
{
  "thought": "reasoning",
  "output": "<text>",
  "is_done": true
}

Return ONLY JSON.
"""
