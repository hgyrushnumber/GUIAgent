from typing import Optional, Dict, Any, List
import time
import json

from pcguiagent.utils.logger import get_logger
from pcguiagent.utils.a11y_preprocessor import A11yTreePreprocessor
from pcguiagent.llms.prompt_templates import get_dsl
from pcguiagent.core.config import Config
from pcguiagent.core.osworld_actions import build_prompt_actions

logger = get_logger("RecursivePlanner")

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.
    Simple estimation: ~4 characters per token for English/Chinese mixed text.
    """
    return len(text) // 4


class RecursivePlanner:
    """
    Planning-style planner that generates a full plan in one shot.
    Input: goal + observation + action history.
    Output: a complete sequence of actions.
    """

    def __init__(
        self,
        llm,
        memory,
        tool_registry: Optional[Any] = None,
        task_id: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        self.llm = llm
        self.memory = memory
        self.registry = tool_registry
        self.task_id = task_id
        self.config = config
        
        # OSWorld mode detection: if tool_registry is None, we're in OSWorld pure strategy mode
        self._is_osworld_mode = tool_registry is None
        
        # Planning state
        self.plan: List[Dict[str, Any]] = []  # Stores the full plan
        self.plan_index = 0  # Current step index
        self.plan_generated = False  # Whether the plan has been generated
        
        # Dynamic tool list (OSWorld-MCP style)
        self._cached_tool_list: Optional[List[Dict[str, Any]]] = None
        self._cached_tools_description: Optional[str] = None
        self._embedding_cfg = config.tools_embedding if config else None
        
        # Initialize DSL (prompt template engine)
        self.dsl = get_dsl()
        
        # Initialize a11y tree preprocessor
        self._a11y_preprocessor = A11yTreePreprocessor()

    def update_tool_list(self, tool_list: List[Dict[str, Any]]):
        """
        Update the tool list (OSWorld-MCP style).
        
        Args:
            tool_list: Tools as [{"name": "...", "description": "...", "parameters": {...}}, ...]
        """
        # Refresh tool descriptions
        tools_description = self._format_tool_list_for_prompt(tool_list)
        self._cached_tools_description = tools_description
        self._cached_tool_list = tool_list
        
        logger.info(f"[Planner] Updated tool list: {len(tool_list)} tools")

    def _format_tool_list_for_prompt(self, tool_list: List[Dict[str, Any]]) -> str:
        """Format tool list for prompts (compact)."""
        descriptions = []
        for tool in tool_list:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            # Trim overly long descriptions to keep prompt short
            short_desc = desc[:160] + ("..." if len(desc) > 160 else "")
            descriptions.append(f"{name}: {short_desc}")
        return "\n".join(descriptions)

    def _select_relevant_tools(self, goal: str, observation_text: str) -> List[Dict[str, Any]]:
        """
        Use embedding-based retrieval (if available) to pick relevant tools.
        Falls back to all tools when embedding is unavailable.
        
        In OSWorld mode (tool_registry is None), returns OSWorld action descriptions.
        """
        # OSWorld mode: return OSWorld action descriptions
        if self._is_osworld_mode:
            return self._get_osworld_action_descriptions()
        
        # Traditional mode: use MCP tool registry
        if not self.registry:
            logger.warning("[Planner] No tool registry available, falling back to OSWorld actions")
            return self._get_osworld_action_descriptions()
        
        query = f"{goal}\n{observation_text}" if observation_text else goal
        top_k = self._embedding_cfg.top_k if self._embedding_cfg else None
        include_basic = True
        try:
            selected = self.registry.select_tools(query=query, top_k=top_k, include_basic=include_basic)
            if selected:
                logger.info(f"[Planner] Selected {len(selected)} tools for prompt (embedding).")
                return selected
        except Exception as e:
            logger.warning(f"[Planner] Tool selection failed, falling back to all tools: {e}")

        # Fallback to all tools
        return [
            {"name": name, "description": self.registry.get_tool_description(name)}
            for name in sorted(self.registry.keys())
        ]
    
    def _get_osworld_action_descriptions(self) -> List[Dict[str, Any]]:
        """
        Get OSWorld action descriptions for OSWorld mode from the shared adapter.
        
        Returns:
            List of action descriptions compatible with tool description format
        """
        prompt_items = build_prompt_actions()
        actions: List[Dict[str, Any]] = []
        for item in prompt_items:
            actions.append(
                {
                    "name": item["name"],
                    "description": f"{item['description']} (params: {item['parameters']})",
                    "action_type": item["name"],
                    "parameters": item.get("raw_parameters", {}),
                }
            )
        return actions

    async def generate_plan(self, goal: str, observation: Optional[Dict[str, Any]] = None, memory_context: Optional[str] = None):
        """
        Generate a full plan (planning style) and return the action list.
        """
        logger.info(f"[Planner.generate_plan] ===== Starting Plan Generation =====")
        logger.info(f"[Planner.generate_plan] Goal: {goal}")
        logger.info(f"[Planner.generate_plan] Observation provided: {observation is not None}")
        if observation:
            logger.info(f"[Planner.generate_plan] Observation keys: {list(observation.keys())}")
            if "accessibility_tree" in observation:
                a11y_len = len(observation["accessibility_tree"])
                logger.info(f"[Planner.generate_plan] Observation accessibility_tree length: {a11y_len} chars")
                logger.debug(f"[Planner.generate_plan] Observation accessibility_tree preview: {observation['accessibility_tree'][:1000]}...")
            if "screenshot" in observation:
                screenshot_size = len(observation["screenshot"]) if isinstance(observation["screenshot"], bytes) else "N/A"
                logger.info(f"[Planner.generate_plan] Observation screenshot size: {screenshot_size} bytes")
            if "terminal" in observation:
                terminal_len = len(observation["terminal"])
                logger.info(f"[Planner.generate_plan] Observation terminal length: {terminal_len} chars")
        
        # 1. Format observation (may be absent on first planning)
        obs_text = self._format_observation(observation) if observation else "None (initial planning)"
        logger.info(f"[Planner.generate_plan] Formatted observation length: {len(obs_text)} chars")
        logger.debug(f"[Planner.generate_plan] Formatted observation preview: {obs_text[:500]}...")

        # 2. Gather relevant tools via embedding search (or pyautogui actions in OSWorld mode)
        logger.info(f"[Planner.generate_plan] Selecting relevant tools/actions...")
        selected_tools = self._select_relevant_tools(goal, obs_text)
        tool_list = [tool.get("name", "") for tool in selected_tools]
        tools_description = self._format_tool_list_for_prompt(selected_tools)
        logger.info(f"[Planner.generate_plan] Selected {len(selected_tools)} tools/actions: {tool_list}")

        if not tool_list:
            logger.error("[Planner] No tools/actions available!")
            return json.dumps({
                "thought": "No tools/actions available",
                "is_done": True,
                "output": "Cannot proceed without tools/actions"
            })
        # 3. Get action history (if any)
        action_history = self._get_action_history()
        
        # 4. Pull working-memory context
        # Use provided memory_context if passed in, otherwise build internally.
        if memory_context is None:
            memory_context = self._get_working_memory_context_full()

        # 5. Build prompt with DSL and templates
        # Use OSWorld-specific template if in OSWorld mode
        if self._is_osworld_mode:
            prompt = self.dsl.plan_generation_osworld(
                goal=goal,
                observation=obs_text,
                tools_description=tools_description,
                action_history=action_history if action_history else None,
                memory_context=memory_context if memory_context else None
            )
        else:
            prompt = self.dsl.plan_generation(
                goal=goal,
                observation=obs_text,
                tools_description=tools_description,
                action_history=action_history if action_history else None,
                memory_context=memory_context if memory_context else None
            )

        # Save prompt for trace collector and logging
        self._last_prompt = prompt
        
        # Log prompt stats and full content
        prompt_chars = len(prompt)
        estimated_tokens = estimate_tokens(prompt)
        logger.info(f"[Planner] Generating complete plan...")
        logger.info(f"[Planner] Prompt stats: {prompt_chars} chars, ~{estimated_tokens} tokens")
        logger.debug(f"[Planner] ===== PLAN GENERATION PROMPT =====")
        logger.debug(f"[Planner] Full prompt:\n{prompt}")
        logger.debug(f"[Planner] ===== END PROMPT =====")
        
        raw = await self.llm.acomplete(prompt)
        
        # Log response
        response_chars = len(raw)
        logger.info(f"[Planner] Plan generation response: {response_chars} chars")
        logger.debug(f"[Planner] ===== PLAN GENERATION RESPONSE =====")
        logger.debug(f"[Planner] Full response:\n{raw}")
        logger.debug(f"[Planner] ===== END RESPONSE =====")
        
        return raw

    async def replan_current_step(self, goal: str, observation: Optional[Dict[str, Any]] = None, memory_context: Optional[str] = None):
        """
        Locally replan the current step without rebuilding the full plan.
        """
        # If no plan exists, fall back to the standard planning flow
        if not self.plan_generated or not self.plan or self.plan_index >= len(self.plan):
            logger.info("[Planner] No existing plan for local replan, falling back to next_action")
            return await self.next_action(goal, observation, memory_context=memory_context)

        # Build context
        obs_text = self._format_observation(observation) if observation else "Failure context missing"

        # Select relevant tools
        selected_tools = self._select_relevant_tools(goal, obs_text)
        tool_list = [tool.get("name", "") for tool in selected_tools]
        tools_description = self._format_tool_list_for_prompt(selected_tools)

        if not tool_list:
            logger.error("[Planner] No tools/actions available for local replan!")
            return json.dumps({
                "thought": "No tools/actions available",
                "is_done": True,
                "output": "Cannot proceed without tools/actions"
            })

        current_step = self.plan[self.plan_index]
        previous_steps = self.plan[:self.plan_index]
        remaining_steps = self.plan[self.plan_index + 1:] if self.plan_index + 1 < len(self.plan) else []

        # Working memory
        if memory_context is None:
            memory_context = self._get_working_memory_context_full()

        # Extract failure reasons (if any)
        error_info = ""
        if observation:
            error = observation.get("error")
            if error:
                error_info = f"\n# Error Details\n{error}\n"
            
            # Capture verification failures
            verification_failed = observation.get("verification_failed")
            if verification_failed:
                reason = verification_failed.get("reason", "")
                suggestions = verification_failed.get("suggestions", [])
                if reason:
                    error_info += f"\n# Verification Failure\nReason: {reason}\n"
                    if suggestions:
                        error_info += f"Suggestions: {', '.join(suggestions[:3])}\n"

        # Create the replan prompt via DSL and templates
        # Note: step_replan doesn't have OSWorld-specific version yet, use regular one
        # The tools_description already contains pyautogui actions if in OSWorld mode
        prompt = self.dsl.step_replan(
            goal=goal,
            observation=obs_text,
            current_step=current_step,
            previous_steps=previous_steps,
            remaining_steps=remaining_steps,
            tools_description=tools_description,
            tool_names=tool_list,
            error_info=error_info if error_info else None,
            memory_context=memory_context if memory_context else None
        )

        # Save prompt for trace
        self._last_local_replan_prompt = prompt
        
        # Log prompt stats and full content
        prompt_chars = len(prompt)
        estimated_tokens = estimate_tokens(prompt)
        logger.info(f"[Planner] Local replanning current step...")
        logger.info(f"[Planner] Replan prompt stats: {prompt_chars} chars, ~{estimated_tokens} tokens")
        logger.info(f"[Planner] ===== REPLAN PROMPT =====")
        logger.info(f"[Planner] Full replan prompt:\n{prompt}")
        logger.info(f"[Planner] ===== END REPLAN PROMPT =====")

        raw = await self.llm.acomplete(prompt)
        
        # Log response
        response_chars = len(raw)
        logger.info(f"[Planner] Replan response: {response_chars} chars")
        logger.info(f"[Planner] ===== REPLAN RESPONSE =====")
        logger.info(f"[Planner] Full replan response:\n{raw}")
        logger.info(f"[Planner] ===== END REPLAN RESPONSE =====")
        
        return raw

    async def next_action(self, goal: str, observation: Optional[Dict[str, Any]], memory_context: Optional[str] = None):
        """
        Return the next action using step-by-step decision making.
        Each call directly generates a single action based on current observation and history.
        """
        logger.info("[Planner.next_action] Step-by-step mode: Generating next action directly")
        
        # 1. Format observation
        obs_text = self._format_observation(observation) if observation else "None (first step)"
        logger.info(f"[Planner.next_action] Formatted observation length: {len(obs_text)} chars")
        
        # 2. Get action history
        action_history = self._get_action_history()
        logger.info(f"[Planner.next_action] Action history length: {len(action_history) if action_history else 0} chars")
        
        # 3. Select relevant tools/actions
        selected_tools = self._select_relevant_tools(goal, obs_text)
        tool_list = [tool.get("name", "") for tool in selected_tools]
        tools_description = self._format_tool_list_for_prompt(selected_tools)
        logger.info(f"[Planner.next_action] Selected {len(selected_tools)} tools/actions")
        
        if not tool_list:
            logger.error("[Planner.next_action] No tools/actions available!")
            return json.dumps({
                "thought": "No tools/actions available",
                "is_done": True,
                "output": "Cannot proceed without tools/actions"
            })
        
        # 4. Use provided memory_context or build internally
        if memory_context is None:
            memory_context = self._get_working_memory_context_full()
        
        # 5. Build step-by-step prompt
        if self._is_osworld_mode:
            prompt = self.dsl.next_action_osworld(
                goal=goal,
                observation=obs_text,
                tools_description=tools_description,
                action_history=action_history if action_history else None,
                memory_context=memory_context if memory_context else None
            )
        else:
            # For non-OSWorld mode, use regular planning (backward compatibility)
            prompt = self.dsl.plan_generation(
                goal=goal,
                observation=obs_text,
                tools_description=tools_description,
                action_history=action_history if action_history else None,
                memory_context=memory_context if memory_context else None
            )
        
        # Save prompt for logging
        self._last_prompt = prompt
        
        # Log prompt stats
        prompt_chars = len(prompt)
        estimated_tokens = estimate_tokens(prompt)
        logger.info(f"[Planner.next_action] Generating next action...")
        logger.info(f"[Planner.next_action] Prompt stats: {prompt_chars} chars, ~{estimated_tokens} tokens")
        logger.debug(f"[Planner.next_action] ===== NEXT ACTION PROMPT =====")
        logger.debug(f"[Planner.next_action] Full prompt:\n{prompt}")
        logger.debug(f"[Planner.next_action] ===== END PROMPT =====")
        
        # 6. Call LLM to generate single action
        raw = await self.llm.acomplete(prompt)
        
        # Log response
        response_chars = len(raw)
        logger.info(f"[Planner.next_action] Response: {response_chars} chars")
        logger.debug(f"[Planner.next_action] ===== NEXT ACTION RESPONSE =====")
        logger.debug(f"[Planner.next_action] Full response:\n{raw}")
        logger.debug(f"[Planner.next_action] ===== END RESPONSE =====")
        
        return raw
    
    def mark_step_completed(self):
        """
        Mark the current step as done.
        In step-by-step mode, this is a no-op (actions are tracked via memory).
        Kept for backward compatibility.
        """
        # In step-by-step mode, we don't use plan_index
        # Actions are tracked via memory system
        if self.plan_generated:
            # Legacy planning mode: advance plan index
            self.plan_index += 1
        # Step-by-step mode: do nothing (action already recorded in memory)
    
    def reset_plan(self):
        """Reset the plan to enable replanning."""
        self.plan = []
        self.plan_index = 0
        self.plan_generated = False
        logger.info("[Planner] Plan reset")

    def _has_coordinate_info(self, attrs: Dict[str, str]) -> bool:
        """
        检查节点是否包含坐标信息
        
        Ubuntu accessibility tree 使用命名空间前缀存储坐标：
        - {cp}screencoord: "(x, y)" - 左上角坐标
        - {cp}size: "(width, height)" - 尺寸
        
        Args:
            attrs: 节点的属性字典（可能包含命名空间前缀的键）
        
        Returns:
            如果包含坐标信息返回 True
        """
        # Ubuntu 命名空间前缀
        component_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/component"
        cp_prefix = f"{{{component_ns_ubuntu}}}"
        
        # 检查 Ubuntu 命名空间坐标字段（优先级最高）
        screencoord_key = f"{cp_prefix}screencoord"
        size_key = f"{cp_prefix}size"
        if screencoord_key in attrs and attrs[screencoord_key]:
            return True
        if size_key in attrs and attrs[size_key]:
            return True
        
        # 检查常见的坐标字段（向后兼容）
        coord_fields = ['bounds', 'position', 'x', 'y', 'left', 'top', 'right', 'bottom', 'width', 'height']
        for field in coord_fields:
            if field in attrs and attrs[field]:
                return True
        
        # 检查命名空间前缀的字段（支持其他可能的命名空间）
        for key in attrs.keys():
            if 'screencoord' in key.lower() or 'size' in key.lower():
                if attrs[key]:
                    return True
        
        return False
    
    def _filter_accessibility_tree(self, a11y_tree: str, max_length: int = 50000) -> str:
        """
        智能过滤 accessibility_tree，只保留关键节点（可交互元素）
        优先保留包含坐标信息的节点，确保坐标提取的准确性
        
        Args:
            a11y_tree: 原始 accessibility tree XML 字符串
            max_length: 最大保留长度（字符数）
        
        Returns:
            过滤后的 accessibility tree 字符串
        """
        if len(a11y_tree) <= max_length:
            return a11y_tree
        
        logger.info(f"[Planner._filter_accessibility_tree] Filtering accessibility tree: {len(a11y_tree)} chars -> max {max_length} chars")
        
        # 使用 XML 解析器提取关键节点
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(a11y_tree)
            
            # 定义关键属性
            key_attributes = ['clickable', 'editable', 'focusable', 'checkable', 'selectable']
            
            # 统计信息
            nodes_with_coords = 0
            nodes_without_coords = 0
            
            # 递归过滤节点
            def filter_node(node):
                nonlocal nodes_with_coords, nodes_without_coords
                
                attrs = node.attrib
                
                # 检查是否包含坐标信息（优先保留）
                has_coords = self._has_coordinate_info(attrs)
                if has_coords:
                    nodes_with_coords += 1
                
                # 检查节点是否有关键属性
                is_key_node = any(
                    attrs.get(attr, '').lower() == 'true' 
                    for attr in key_attributes
                )
                
                # 检查是否有文本内容且不是纯装饰性
                has_text = node.text and node.text.strip()
                is_decorative = attrs.get('role', '').lower() in ['presentation', 'none']
                
                # 保留条件：
                # 1. 包含坐标信息的节点（优先）
                # 2. 关键交互节点
                # 3. 包含重要文本的节点
                should_keep = has_coords or is_key_node or (has_text and not is_decorative)
                
                if should_keep:
                    # 保留此节点及其子节点
                    filtered_children = []
                    for child in node:
                        filtered_child = filter_node(child)
                        if filtered_child is not None:
                            filtered_children.append(filtered_child)
                    node.clear()
                    node.extend(filtered_children)
                    return node
                else:
                    nodes_without_coords += 1
                    # 检查子节点是否有关键节点
                    has_key_children = False
                    filtered_children = []
                    for child in node:
                        filtered_child = filter_node(child)
                        if filtered_child is not None:
                            filtered_children.append(filtered_child)
                            has_key_children = True
                    
                    if has_key_children:
                        node.clear()
                        node.extend(filtered_children)
                        return node
                    else:
                        return None
            
            filtered_root = filter_node(root)
            logger.info(f"[Planner._filter_accessibility_tree] Nodes with coordinates: {nodes_with_coords}, without: {nodes_without_coords}")
            
            if filtered_root is not None:
                filtered_xml = ET.tostring(filtered_root, encoding='unicode')
                if len(filtered_xml) <= max_length:
                    logger.info(f"[Planner._filter_accessibility_tree] Filtered to {len(filtered_xml)} chars (preserved {nodes_with_coords} nodes with coordinates)")
                    return filtered_xml
                else:
                    # 如果过滤后仍然太长，进行截断
                    logger.warning(f"[Planner._filter_accessibility_tree] Filtered tree still too long ({len(filtered_xml)} chars), truncating")
                    return self._truncate_accessibility_tree(filtered_xml, max_length)
            else:
                # 如果过滤后为空，使用截断方法
                logger.warning(f"[Planner._filter_accessibility_tree] Filtered tree is empty, using truncation")
                return self._truncate_accessibility_tree(a11y_tree, max_length)
        except Exception as e:
            logger.warning(f"[Planner._filter_accessibility_tree] Failed to filter accessibility tree: {e}, using truncation")
            return self._truncate_accessibility_tree(a11y_tree, max_length)
    
    def _truncate_accessibility_tree(self, a11y_tree: str, max_length: int) -> str:
        """
        截断 accessibility_tree，保留开头和结尾
        """
        if len(a11y_tree) <= max_length:
            return a11y_tree
        
        prefix_length = max_length // 2
        suffix_length = max_length // 2
        prefix = a11y_tree[:prefix_length]
        suffix = a11y_tree[-suffix_length:]
        truncated = f"{prefix}\n\n[... {len(a11y_tree) - max_length} characters truncated ...]\n\n{suffix}"
        logger.info(f"[Planner._truncate_accessibility_tree] Truncated from {len(a11y_tree)} to {len(truncated)} chars")
        return truncated

    def _get_ocr_result(self, screenshot: bytes) -> Optional[str]:
        """
        调用 OCR 识别 screenshot 中的文本和坐标
        
        Args:
            screenshot: 截图字节数据
        
        Returns:
            格式化的 OCR 结果文本，如果失败返回 None
        """
        # 检查 OCR 是否启用
        if not self.config or not self.config.ocr or not self.config.ocr.enabled:
            return None
        
        try:
            from pcguiagent.utils.ocr_client import create_ocr_client
            
            # 创建 OCR 客户端
            ocr_client = create_ocr_client(
                access_key_id=self.config.ocr.access_key_id,
                access_key_secret=self.config.ocr.access_key_secret,
                endpoint=self.config.ocr.endpoint
            )
            
            if not ocr_client:
                logger.warning("[Planner._get_ocr_result] OCR 客户端创建失败")
                return None
            
            # 调用 OCR
            logger.info(f"[Planner._get_ocr_result] 调用 OCR API，图片大小: {len(screenshot)} bytes")
            ocr_result = ocr_client.recognize(screenshot)
            
            if not ocr_result:
                logger.warning("[Planner._get_ocr_result] OCR 识别失败或返回空结果")
                return None
            
            # 格式化结果
            formatted = ocr_client.format_ocr_result(ocr_result)
            logger.info(f"[Planner._get_ocr_result] OCR 识别成功，结果长度: {len(formatted)} chars")
            return formatted
            
        except Exception as e:
            logger.warning(f"[Planner._get_ocr_result] OCR 调用出错: {e}", exc_info=True)
            return None
    
    def _format_observation(self, observation: Optional[Dict[str, Any]]) -> str:
        """
        Format observation results, including Working Memory data.
        
        OSWorld Mode (a11y_tree only, OCR disabled):
        - Uses accessibility_tree text only
        - Preprocesses a11y_tree into structured components
        - OCR is temporarily disabled
        
        Traditional Mode:
        - Uses execution results (success, data, error)
        """
        logger.debug(f"[Planner._format_observation] Formatting observation...")
        if observation is None:
            logger.debug(f"[Planner._format_observation] Observation is None, returning 'None (first step)'")
            return "None (first step)"
        
        logger.debug(f"[Planner._format_observation] Observation keys: {list(observation.keys())}")
        
        # OSWorld mode: check if this is a11y_tree observation
        if "accessibility_tree" in observation:
            # OSWorld mode: use a11y_tree only (OCR temporarily disabled)
            a11y_tree = observation.get("accessibility_tree", "")
            logger.info(f"[Planner._format_observation] OSWorld mode: accessibility_tree length: {len(a11y_tree)} chars")
            
            formatted_parts = []
            
            # 1. Accessibility Tree - Preprocess into structured components
            if a11y_tree:
                # Detect platform (default to ubuntu)
                platform = "ubuntu"  # Could be enhanced to detect from observation
                
                # Preprocess a11y_tree into structured components
                components = self._a11y_preprocessor.preprocess(a11y_tree, platform=platform)
                
                if components:
                    # Add component summary statistics
                    primary_count = sum(1 for c in components if c.get("actionable", False))
                    secondary_count = len(components) - primary_count
                    components_with_geometry = sum(1 for c in components if c.get("geometry") is not None)
                    
                    # Count by role
                    role_counts = {}
                    for c in components:
                        role = c.get("role", "unknown")
                        role_counts[role] = role_counts.get(role, 0) + 1
                    
                    # Build summary
                    summary_lines = [
                        f"# UI Components Summary",
                        f"- Total components: {len(components)}",
                        f"- Primary (actionable: true): {primary_count}",
                        f"- Secondary (has geometry, actionable: false): {secondary_count}",
                        f"- With coordinates: {components_with_geometry}",
                    ]
                    
                    # Add top roles
                    if role_counts:
                        top_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                        role_summary = ", ".join([f"{role}({count})" for role, count in top_roles])
                        summary_lines.append(f"- Top roles: {role_summary}")
                    
                    summary = "\n".join(summary_lines) + "\n\n"
                    
                    # Format components JSON
                    components_json = json.dumps(components, indent=2, ensure_ascii=False)
                    formatted_parts.append(f"{summary}# UI Components (Preprocessed from Accessibility Tree)\n{components_json}\n")
                    logger.info(f"[Planner._format_observation] Preprocessed {len(components)} actionable components ({primary_count} primary, {secondary_count} secondary)")
                else:
                    logger.warning(f"[Planner._format_observation] No actionable components found after preprocessing")
                    formatted_parts.append("# UI Components\n(no actionable components found)\n")
            else:
                logger.warning(f"[Planner._format_observation] Accessibility tree is EMPTY!")
                formatted_parts.append("# UI Components\n(empty)\n")
            
            # 2. OCR Results - Temporarily disabled (not using OCR)
            # screenshot = observation.get("screenshot") or observation.get("image")
            # if screenshot and isinstance(screenshot, bytes):
            #     logger.info(f"[Planner._format_observation] Screenshot available: {len(screenshot)} bytes")
            #     ocr_result = self._get_ocr_result(screenshot)
            #     if ocr_result:
            #         formatted_parts.append(f"\n{ocr_result}\n")
            #     else:
            #         logger.debug("[Planner._format_observation] OCR 未启用或识别失败，跳过 OCR 结果")
            # else:
            #     logger.debug("[Planner._format_observation] 无 screenshot 或 screenshot 格式不正确")
            logger.debug("[Planner._format_observation] OCR temporarily disabled - using only preprocessed a11y_tree components")
            
            # 3. Terminal Output (if available)
            terminal = observation.get("terminal")
            if terminal:
                logger.info(f"[Planner._format_observation] Adding terminal output: {len(terminal)} chars")
                formatted_parts.append(f"\n# Terminal Output\n{terminal}\n")
            
            formatted = "".join(formatted_parts)
            logger.info(f"[Planner._format_observation] Formatted observation length: {len(formatted)} chars")
            return formatted
        
        # Traditional mode: format execution results
        success = observation.get("success", False)
        data = observation.get("data", {})
        error = observation.get("error")
        
        formatted = f"Success: {success}\n"
        
        if error:
            formatted += f"Error: {error}\n"
        
        # Include recent failures to help LLM avoid repeating mistakes
        recent_failures = observation.get("recent_failures", [])
        if recent_failures:
            formatted += "\n⚠️ RECENT FAILURES (DO NOT REPEAT THESE ACTIONS):\n"
            for i, failure in enumerate(recent_failures, 1):
                action = failure.get("action", "unknown")
                error_msg = failure.get("error", "Unknown error")
                # Truncate long error messages
                if len(error_msg) > 150:
                    error_msg = error_msg[:150] + "..."
                formatted += f"  {i}. {action}\n"
                formatted += f"     Error: {error_msg}\n"
            formatted += "\n"
        
        # Prefer parsed structured data
        parsed = observation.get("parsed")
        if parsed:
            parsed_type = parsed.get("type", "unknown")
            summary = parsed.get("summary", "")
            key_fields = parsed.get("key_fields", {})
            
            formatted += f"\nParsed output type: {parsed_type}\n"
            formatted += f"Summary: {summary}\n"
            
            if key_fields:
                formatted += "Key fields extracted:\n"
                for key, value in list(key_fields.items())[:5]:  # Show first 5 fields
                    if isinstance(value, (str, int, float, bool)):
                        value_str = str(value)
                        if len(value_str) > 100:
                            value_str = value_str[:100] + "..."
                        formatted += f"  - {key}: {value_str}\n"
                    elif isinstance(value, list):
                        formatted += f"  - {key}: [{len(value)} items]\n"
                        # Display first 3 items
                        for i, item in enumerate(value[:3], 1):
                            item_str = str(item)[:50]
                            formatted += f"    {i}. {item_str}\n"
                        if len(value) > 3:
                            formatted += f"    ... and {len(value) - 3} more\n"
        
        # If no parsed data, fall back to raw data
        elif data and isinstance(data, dict):
            content = data.get("content", "")
            if content:
                content_str = str(content)
                # Summarize multi-line data (e.g., lists)
                if "\n" in content_str:
                    lines = [l.strip() for l in content_str.split("\n") if l.strip()]
                    if lines:
                        formatted += f"\nData retrieved: {len(lines)} items\n"
                        # Show first 3 as samples
                        for i, line in enumerate(lines[:3], 1):
                            formatted += f"  {i}. {line}\n"
                        if len(lines) > 3:
                            formatted += f"  ... and {len(lines) - 3} more\n"
                else:
                    # 单行数据，截取前200字符
                    formatted += f"\nData: {content_str[:200]}\n"
        
        # Add working-memory context when present
        working_memory_context = self._get_working_memory_context()
        if working_memory_context:
            formatted += "\n--- Working Memory (Previous Tool Results) ---\n"
            formatted += working_memory_context
            formatted += "\n--- End Working Memory ---\n"
        
        return formatted
    
    def _get_working_memory_context(self) -> str:
        """Fetch relevant context from Working Memory (simplified for formatting)."""
        try:
            # 获取short_term memory中的所有数据
            context_dict = self.memory.short_term.to_dict()
            if not context_dict:
                return ""
            
            context_lines = []
            for key, value in context_dict.items():
                # 只显示工具结果相关的上下文
                if key.startswith("tool_result_") and not key.endswith("_data"):
                    tool_name = key.replace("tool_result_", "")
                    if isinstance(value, dict) and "tool_name" in value:
                        summary = value.get("summary", "")
                        key_fields = value.get("key_fields", {})
                        context_lines.append(f"\nTool: {tool_name}")
                        if summary:
                            context_lines.append(f"  Summary: {summary}")
                        if key_fields:
                            # 显示关键字段
                            for k, v in list(key_fields.items())[:3]:
                                if isinstance(v, (str, int, float, bool)):
                                    v_str = str(v)
                                    if len(v_str) > 80:
                                        v_str = v_str[:80] + "..."
                                    context_lines.append(f"  {k}: {v_str}")
                                elif isinstance(v, list):
                                    context_lines.append(f"  {k}: [{len(v)} items]")
            
            return "\n".join(context_lines) if context_lines else ""
        except Exception as e:
            logger.warning(f"[Planner] Error getting working memory context: {e}")
            return ""
    
    def _get_working_memory_context_full(self) -> str:
        """从Working Memory中获取完整上下文（用于prompt）"""
        try:
            from pcguiagent.memory.context_builder import MemoryContextBuilder
            builder = MemoryContextBuilder(self.memory)
            return builder.build_context(include_raw=False)
        except Exception as e:
            logger.warning(f"[Planner] Error building full memory context: {e}")
            # Fallback to simple version
            simple_context = self._get_working_memory_context()
            if simple_context:
                return f"\n# Working Memory\n{simple_context}\n"
            return ""
    
    def _fill_action_args_from_memory(self, action: Dict[str, Any], memory_context: Optional[str]) -> Dict[str, Any]:
        """
        从 memory context 中动态填充 action args 中缺失的数据
        
        Args:
            action: 要执行的 action（包含 name 和 args）
            memory_context: Memory context 字符串（JSON 格式）
            
        Returns:
            填充后的 action
        """
        if not memory_context or not action:
            return action
        
        action_name = action.get("name", "")
        args_raw = action.get("args", {})
        # 确保 args 是字典类型
        if isinstance(args_raw, dict):
            args = args_raw.copy()
        elif isinstance(args_raw, str):
            logger.warning(f"[Planner] Args is string instead of dict: {args_raw[:100]}...")
            args = {}
        else:
            logger.warning(f"[Planner] Args has unexpected type {type(args_raw)}, using empty dict")
            args = {}
        
        # 解析 memory context JSON
        try:
            # 从 memory_context 字符串中提取 JSON
            import re
            json_match = re.search(r'```json\n(.*?)\n```', memory_context, re.DOTALL)
            if json_match:
                memory_json = json.loads(json_match.group(1))
                working_memory = memory_json.get("working_memory", {})
            else:
                # 如果没有代码块，尝试直接解析
                memory_json = json.loads(memory_context)
                working_memory = memory_json.get("working_memory", {})
        except Exception as e:
            logger.warning(f"[Planner] Failed to parse memory context: {e}")
            return action
        
        # 处理 excel.create_table：如果 data 为空，尝试从 memory 中获取数据
        if action_name == "excel.create_table":
            if not args.get("data") or args.get("data") == []:
                # 查找可能的数据源
                # 优先查找 code.list_extensions
                if "code.list_extensions" in working_memory:
                    extensions_data = working_memory["code.list_extensions"]
                    
                    # 处理不同的数据格式
                    if isinstance(extensions_data, list):
                        # 直接是列表格式
                        data_list = extensions_data
                    elif isinstance(extensions_data, dict) and "data" in extensions_data:
                        # 有 _metadata 的情况
                        data_list = extensions_data["data"]
                    else:
                        data_list = []
                    
                    # 转换为 Excel 表格格式
                    if data_list:
                        headers = args.get("headers", [])
                        excel_data = []
                        
                        for item in data_list:
                            if isinstance(item, str):
                                # 如果是字符串（插件ID，如 "alimozdemir.vscode-nuxt-dx-tools"）
                                # 提取插件名称部分（最后一个点之前的部分，或者整个字符串）
                                if "." in item:
                                    # 格式通常是 publisher.extension-name
                                    # 提取 extension-name 部分作为显示名称
                                    parts = item.split(".")
                                    if len(parts) >= 2:
                                        # 使用最后一个部分作为名称，或者使用整个ID
                                        name = parts[-1].replace("-", " ").title()
                                    else:
                                        name = item
                                else:
                                    name = item
                                excel_data.append([name])
                            elif isinstance(item, dict):
                                # 如果是字典（已解析的扩展信息）
                                if len(headers) == 1:
                                    # 单列：提取 name 字段
                                    name = item.get("name") or item.get("id") or str(item)
                                    excel_data.append([name])
                                else:
                                    # 多列：根据 headers 提取对应字段
                                    row = []
                                    for header in headers:
                                        # 匹配 header 到字典的 key（不区分大小写）
                                        header_lower = header.lower()
                                        value = None
                                        for k, v in item.items():
                                            if k.lower() == header_lower:
                                                value = v
                                                break
                                        if value is None:
                                            # 如果找不到，尝试常见的映射
                                            if "name" in header_lower:
                                                value = item.get("name") or item.get("id", "")
                                            elif "id" in header_lower:
                                                value = item.get("id") or item.get("name", "")
                                            elif "version" in header_lower:
                                                value = item.get("version", "")
                                            else:
                                                value = ""
                                        row.append(str(value) if value is not None else "")
                                    excel_data.append(row)
                            else:
                                excel_data.append([str(item)])
                        
                        if excel_data:
                            args["data"] = excel_data
                            logger.info(f"[Planner] ✅ Filled excel.create_table data from memory: {len(excel_data)} rows")
                        else:
                            logger.warning(f"[Planner] ⚠️ No data extracted from memory for excel.create_table")
                    else:
                        logger.warning(f"[Planner] ⚠️ code.list_extensions data is empty in memory")
        
        # 更新 action
        action["args"] = args
        return action
    
    def _get_action_history(self) -> str:
        """
        Get formatted action history with improved context.
        
        Returns:
            Formatted string with recent action history, including:
            - Step numbers
            - Action types and parameters
            - Success/failure status
            - Summary statistics
        """
        try:
            events = self.memory.episodic.get_events()
            if not events:
                return "No previous actions."
            
            # Get recent events (last 8 for better context)
            recent = events[-8:]
            total_events = len(events)
            
            history_lines = []
            history_lines.append(f"# Action History (showing last {len(recent)} of {total_events} total actions)\n")
            
            success_count = 0
            failure_count = 0
            
            for idx, event in enumerate(recent, start=1):
                step = event.get("step", 0)
                action = event.get("action", {})
                action_name = action.get("name", "unknown")
                action_args = action.get("args", {})
                result = event.get("result", {})
                success = result.get("success", False)
                
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                
                # Format action type (for OSWorld actions, extract action_type)
                action_type = "unknown"
                if isinstance(action_args, dict):
                    # Check for OSWorld action format
                    if "action_type" in action_args:
                        action_type = action_args.get("action_type", "unknown")
                        params = action_args.get("parameters", {})
                    else:
                        # Regular tool format
                        action_type = action_name
                        params = action_args
                else:
                    params = {}
                
                # Format parameters more clearly
                params_str = ""
                if params:
                    # For OSWorld actions, show key parameters
                    if action_type in ["CLICK", "MOVE_TO", "DRAG_TO"]:
                        x = params.get("x")
                        y = params.get("y")
                        if x is not None and y is not None:
                            params_str = f" at ({x}, {y})"
                    elif action_type in ["PRESS", "KEY_DOWN", "KEY_UP"]:
                        key = params.get("key")
                        if key:
                            params_str = f" key='{key}'"
                    elif action_type == "HOTKEY":
                        keys = params.get("keys", [])
                        if keys:
                            params_str = f" keys={keys}"
                    elif action_type == "TYPING":
                        text = params.get("text", "")
                        if text:
                            # Truncate long text
                            display_text = text[:50] + "..." if len(text) > 50 else text
                            params_str = f" text='{display_text}'"
                    elif action_type == "SCROLL":
                        dx = params.get("dx", 0)
                        dy = params.get("dy", 0)
                        params_str = f" dx={dx}, dy={dy}"
                    else:
                        # Generic parameter display
                        key_params = {}
                        for k, v in list(params.items())[:3]:  # Show first 3 params
                            if isinstance(v, (str, int, float, bool)):
                                key_params[k] = v
                            elif isinstance(v, list) and len(v) > 0:
                                key_params[k] = f"[{len(v)} items]"
                            else:
                                key_params[k] = str(v)[:30]
                        if key_params:
                            params_str = f" {key_params}"
                
                status = "✓" if success else "✗"
                # Use relative position (most recent first in display)
                relative_pos = len(recent) - idx + 1
                history_lines.append(f"{relative_pos}. {action_type}{params_str} → {status}")
            
            # Add summary
            if len(recent) > 0:
                history_lines.append(f"\nSummary: {success_count} succeeded, {failure_count} failed")
            
            return "\n".join(history_lines) if history_lines else "No previous actions."
        except Exception as e:
            logger.warning(f"[Planner] Error getting action history: {e}")
            return "Unable to retrieve action history."
