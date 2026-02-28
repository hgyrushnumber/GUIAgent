"""
PC GUI Agent - Intra-Agent Multi-Role Reasoning

Intra-Agent Multi-Role Reasoning 架构：
1. 接收 OSWorld 的 observation
2. 通过角色协作（PlannerRole, MemoryRole, ReflectorRole）生成 action
3. 将 action 转换为 OSWorld pyautogui 字符串
4. 角色之间通过直接方法调用协作，无消息传递开销
"""

import asyncio
import json
import uuid
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

from pcguiagent.utils.logger import get_logger
from pcguiagent.bootstrap import Bootstrap
from pcguiagent.core.osworld_actions import validate_osworld_action
from pcguiagent.utils.config_loader import find_config_file
from pcguiagent.utils.action_extractor import ActionExtractor
from pcguiagent.roles import PlannerRole, MemoryRole, ReflectorRole

logger = get_logger("PCGuiAgent")


class PCGuiAgent:
    """
    OSWorld → Intra-Agent Multi-Role Reasoning 系统的 Adapter
    
    职责：
    - 接收 OSWorld observation
    - 通过角色协作（PlannerRole, MemoryRole, ReflectorRole）生成 action
    - 将 action 转换为 OSWorld pyautogui 字符串
    - 角色之间通过直接方法调用协作，无消息传递开销
    """

    def __init__(
        self,
        action_space: str = "osworld",
        observation_type: Optional[str] = "a11y_tree",
        config_path: Optional[str] = None,
        **_: Any,
    ):
        # OSWorld 需要的属性
        # 仅支持 OSWorld 动作空间，强制对齐以避免提示词/执行端不一致
        self.action_space = action_space or "osworld"
        if self.action_space != "osworld":
            logger.warning(
                "[PCGuiAgent] action_space=%s 与 OSWorld 动作空间不符，强制切换为 osworld",
                self.action_space,
            )
            self.action_space = "osworld"
        self.observation_type = observation_type
        
        # Intra-Agent Multi-Role Reasoning 系统组件
        self._planner_role: Optional[PlannerRole] = None
        self._memory_role: Optional[MemoryRole] = None
        self._reflector_role: Optional[ReflectorRole] = None
        
        # 底层组件（用于角色初始化）
        self._planner: Optional[Any] = None  # RecursivePlanner
        self._memory: Optional[Any] = None  # MemoryStorage
        self._llm: Optional[Any] = None  # LLM Client
        self._task_verifier: Optional[Any] = None  # TaskVerifier
        
        self._config_path = config_path or self._find_default_config()
        
        # 状态管理
        self._initialized = False
        self._step_counter = 0
        self._action_extractor: Optional[ActionExtractor] = None
        
        # 共享状态（供角色访问）
        self._shared_state: Dict[str, Any] = {
            "current_task": None,
            "current_plan": None,
            "step_index": 0,
            "results": [],
        }
        
        # Event loop 管理：使用当前运行的 loop 或获取默认 loop
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的 loop，获取或创建默认 loop
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果也没有默认 loop，创建新的
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

    @staticmethod
    def _find_default_config() -> str:
        """查找默认配置文件"""
        try:
            config_path = find_config_file("config.yaml", module_dir=Path(__file__).parent)
            return str(config_path)
        except FileNotFoundError:
            # 如果都找不到，返回相对路径（Bootstrap 会处理）
            return "config.yaml"

    # ---------- Lifecycle ----------
    def reset(self, runtime_logger: Any = None, vm_ip: Optional[str] = None):
        """
        OSWorld 兼容的 reset：重置任务状态
        """
        self._step_counter = 0
        if self._planner:
            self._planner.reset_plan()
        
        # 重置共享状态
        self._shared_state = {
            "current_task": None,
            "current_plan": None,
            "step_index": 0,
            "results": [],
        }
        
        logger.info("[PCGuiAgent] Reset for new task/episode")

    async def _ensure_initialized(self):
        """确保 Intra-Agent Multi-Role Reasoning 系统已初始化"""
        if not self._initialized:
            logger.info("[PCGuiAgent] Initializing Intra-Agent Multi-Role Reasoning system...")
            try:
                bootstrap = Bootstrap(self._config_path)
                components = await bootstrap.build_intra_agent()
                
                # 获取底层组件
                self._llm = components["llm"]
                self._memory = components["memory"]
                self._planner = components["planner"]
                self._task_verifier = components.get("task_verifier")
                
                # 初始化角色
                self._planner_role = PlannerRole(self._planner, agent=self)
                self._memory_role = MemoryRole(self._memory, agent=self)
                if self._task_verifier:
                    self._reflector_role = ReflectorRole(self._task_verifier, plan_repair=None, agent=self)
                
                logger.info("[PCGuiAgent] Roles initialized:")
                logger.info(f"  - PlannerRole: {self._planner_role is not None}")
                logger.info(f"  - MemoryRole: {self._memory_role is not None}")
                logger.info(f"  - ReflectorRole: {self._reflector_role is not None}")
                
                # 初始化 ActionExtractor（不需要 task_manager）
                self._action_extractor = ActionExtractor(None)
                # 将转换方法绑定到 ActionExtractor
                self._action_extractor._convert_action_to_pyautogui = self._convert_action_to_pyautogui
                self._action_extractor._convert_mcp_action_to_pyautogui = self._convert_mcp_action_to_pyautogui
                
                self._initialized = True
                logger.info("[PCGuiAgent] Intra-Agent Multi-Role Reasoning system initialized")
            except Exception as e:
                logger.error(f"[PCGuiAgent] Failed to initialize Intra-Agent system: {e}", exc_info=True)
                raise

    async def initialize(self):
        await self._ensure_initialized()

    async def close(self):
        """关闭 Single Agent 系统"""
        if self._planner:
            self._planner.reset_plan()
        if self._loop and not self._loop.is_closed():
            self._loop.close()
        self._initialized = False
        logger.info("[PCGuiAgent] Closed")

    # ---------- Core Interface ----------
    def act(self, observation: Dict[str, Any]) -> str:
        """同步接口，便于在 OSWorld 的同步调用环境中使用"""
        # 如果已有运行中的 loop，使用 run_coroutine_threadsafe
        if self._loop.is_running():
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(self.step(observation), self._loop)
            return future.result()
        else:
            return self._loop.run_until_complete(self.step(observation))

    async def step(self, observation: Dict[str, Any]) -> str:
        """
        OSWorld 期望的核心接口
        
        Args:
            observation: OSWorld observation dict，包含：
                - instruction: str (任务指令)
                - a11y_tree / accessibility_tree: str
                - screenshot: bytes (可选)
                - step: int (可选)
                - terminal: str (可选)
        
        Returns:
            pyautogui action 字符串，如 "CLICK 100 200", "WAIT", "SCROLL 0 -100" 等
        """
        await self._ensure_initialized()
        
        # 提取 instruction 和 step
        instruction = observation.get("instruction", "")
        step_num = observation.get("step")
        if step_num is None:
            step_num = self._step_counter
        self._step_counter = step_num + 1
        
        logger.info(f"[PCGuiAgent.step] Step {step_num}: Processing observation")
        logger.info(f"[PCGuiAgent.step] Instruction: {instruction}")
        
        # 记录 OSWorld observation 的详细内容
        a11y_tree = observation.get("a11y_tree") or observation.get("accessibility_tree") or ""
        a11y_tree_length = len(a11y_tree) if a11y_tree else 0
        a11y_tree_preview = a11y_tree[:1000] if a11y_tree else "(empty)"  # 增加到 1000 字符用于调试
        
        logger.info(f"[PCGuiAgent.step] ===== OSWorld Observation Details =====")
        logger.info(f"[PCGuiAgent.step] Step number: {step_num}")
        logger.info(f"[PCGuiAgent.step] Instruction: {instruction}")
        logger.info(f"[PCGuiAgent.step] Instruction length: {len(instruction)} chars")
        logger.info(f"[PCGuiAgent.step] Accessibility tree length: {a11y_tree_length} chars")
        logger.info(f"[PCGuiAgent.step] Accessibility tree preview (first 1000 chars):\n{a11y_tree_preview}")
        
        # 记录其他 observation 字段
        has_screenshot = bool(observation.get("screenshot") or observation.get("image"))
        has_terminal = bool(observation.get("terminal"))
        logger.info(f"[PCGuiAgent.step] Has screenshot: {has_screenshot}")
        if has_screenshot:
            screenshot = observation.get("screenshot") or observation.get("image")
            screenshot_size = len(screenshot) if isinstance(screenshot, bytes) else "N/A"
            logger.info(f"[PCGuiAgent.step] Screenshot size: {screenshot_size} bytes")
        logger.info(f"[PCGuiAgent.step] Has terminal: {has_terminal}")
        if has_terminal:
            terminal = observation.get("terminal", "")
            logger.info(f"[PCGuiAgent.step] Terminal output length: {len(terminal)} chars")
            logger.debug(f"[PCGuiAgent.step] Terminal output preview: {terminal[:200]}...")
        logger.info(f"[PCGuiAgent.step] Observation keys: {list(observation.keys())}")
        logger.debug(f"[PCGuiAgent.step] Full accessibility_tree:\n{a11y_tree}")
        logger.info(f"[PCGuiAgent.step] ===== End Observation Details =====")
        
        # 检查 instruction
        if not instruction:
            logger.warning("[PCGuiAgent.step] No instruction provided, returning WAIT")
            return "WAIT"
        
        # 转换 observation 格式
        logger.info(f"[PCGuiAgent.step] Converting OSWorld observation to internal format...")
        internal_observation = self._convert_osworld_observation(observation)
        logger.info(f"[PCGuiAgent.step] Converted observation keys: {list(internal_observation.keys())}")
        if "accessibility_tree" in internal_observation:
            a11y_len = len(internal_observation["accessibility_tree"])
            logger.info(f"[PCGuiAgent.step] Converted accessibility_tree length: {a11y_len} chars")
        if "screenshot" in internal_observation:
            screenshot_size = len(internal_observation["screenshot"]) if isinstance(internal_observation["screenshot"], bytes) else "N/A"
            logger.info(f"[PCGuiAgent.step] Converted screenshot size: {screenshot_size} bytes")
        
        # 通过 MemoryRole 构建 memory context
        memory_context = None
        if self._memory_role:
            try:
                memory_context = self._memory_role.build_context()
                logger.info(f"[PCGuiAgent.step] Memory context length: {len(memory_context) if memory_context else 0} chars")
            except Exception as e:
                logger.warning(f"[PCGuiAgent.step] Failed to get memory context: {e}")
        
        # 通过 PlannerRole 获取下一步 action
        logger.info(f"[PCGuiAgent.step] Calling PlannerRole.get_next_step()...")
        try:
            action_output = await self._planner_role.get_next_step(
                goal=instruction,
                observation=internal_observation,
                memory_context=memory_context
            )
            
            logger.info(f"[PCGuiAgent.step] ===== Planner Result =====")
            logger.info(f"[PCGuiAgent.step] Action output length: {len(action_output)} chars")
            logger.debug(f"[PCGuiAgent.step] Action output: {action_output}")
            logger.info(f"[PCGuiAgent.step] ===== End Planner Result =====")
            
            # 解析 action
            try:
                action_data = json.loads(action_output)
                logger.info(f"[PCGuiAgent.step] Action data parsed successfully")
                logger.info(f"[PCGuiAgent.step] Action data keys: {list(action_data.keys())}")
                
                # 检查是否完成
                if action_data.get("is_done"):
                    logger.info(f"[PCGuiAgent.step] Task is done")
                    # 标记计划完成
                    self._planner.mark_step_completed()
                    return "DONE"
                
                # 提取 action
                action = action_data.get("action", {})
                if not action:
                    logger.warning(f"[PCGuiAgent.step] No action in response, returning WAIT")
                    return "WAIT"
                
                logger.info(f"[PCGuiAgent.step] ===== Extracting Action =====")
                logger.info(f"[PCGuiAgent.step] Action type: {type(action)}")
                logger.info(f"[PCGuiAgent.step] Action: {action}")
                
                # 使用 ActionExtractor 提取并转换 action
                if self._action_extractor:
                    pyautogui_action = self._action_extractor.extract_from_planner_output(action_data)
                else:
                    # 回退方法：直接转换
                    action_type = action.get("action_type") if isinstance(action, dict) else None
                    parameters = action.get("parameters") if isinstance(action, dict) else {}
                    if action_type:
                        pyautogui_action = self._convert_action_to_pyautogui(action_type, parameters)
                    else:
                        logger.warning(f"[PCGuiAgent.step] Cannot extract action, returning WAIT")
                        return "WAIT"
                
                # 标记步骤完成
                if self._planner:
                    self._planner.mark_step_completed()
                
                # 更新共享状态
                self._shared_state["step_index"] = self._step_counter
                if action:
                    self._shared_state["results"].append({
                        "step": self._step_counter,
                        "action": action,
                    })
                
                logger.info(f"[PCGuiAgent.step] ===== Final Action =====")
                logger.info(f"[PCGuiAgent.step] Extracted action: {pyautogui_action}")
                logger.info(f"[PCGuiAgent.step] ===== End Final Action =====")
                return pyautogui_action if pyautogui_action else "WAIT"
                
            except json.JSONDecodeError as e:
                logger.error(f"[PCGuiAgent.step] Failed to parse action output JSON: {e}")
                logger.error(f"[PCGuiAgent.step] Action output that failed to parse: {action_output[:1000]}...")
                return "WAIT"  # 可恢复错误
            
        except Exception as e:
            # 其他错误 - 根据错误类型判断是否可恢复
            error_type = type(e).__name__
            logger.critical(f"[PCGuiAgent.step] Exception occurred: {error_type}: {e}", exc_info=True)
            
            # 判断是否为可恢复错误
            recoverable_errors = (ConnectionError, TimeoutError, asyncio.TimeoutError)
            if isinstance(e, recoverable_errors):
                logger.warning(f"[PCGuiAgent.step] Recoverable error ({error_type}), returning WAIT")
                return "WAIT"
            
            # 致命错误
            logger.error(f"[PCGuiAgent.step] Fatal error ({error_type}), returning FAIL")
            return "FAIL"

    # ---------- OSWorld Adapter Helpers ----------
    def predict(self, instruction: str, obs: Dict[str, Any]) -> Tuple[str, list[str]]:
        """
        OSWorld run.py 兼容接口
        
        Returns:
            (response_message, [pyautogui_action])
        """
        try:
            # 合并 instruction 到 observation
            observation = obs.copy()
            observation["instruction"] = instruction
            
            action = self.act(observation)
            return "ok", [action]
        except Exception as exc:
            logger.error(f"[PCGuiAgent.predict] Failed: {exc}", exc_info=True)
            return "fail", ["WAIT"]

    # ---------- Conversion Methods (Adapter Logic) ----------
    def _convert_osworld_observation(self, osworld_obs: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 OSWorld observation 转换为多 Agent 系统能理解的格式
        
        Args:
            osworld_obs: OSWorld observation dict
        
        Returns:
            多 Agent 系统格式的 observation
        """
        internal_obs = {}
        
        # 记录转换过程
        logger.info(f"[_convert_osworld_observation] ===== Converting OSWorld Observation =====")
        logger.info(f"[_convert_osworld_observation] Original observation keys: {list(osworld_obs.keys())}")
        
        # 提取 accessibility_tree (支持多种字段名)
        a11y_tree = (
            osworld_obs.get("a11y_tree") or 
            osworld_obs.get("accessibility_tree") or 
            ""
        )
        if a11y_tree:
            logger.info(f"[_convert_osworld_observation] ✓ accessibility_tree extracted: {len(a11y_tree)} chars")
            logger.debug(f"[_convert_osworld_observation] accessibility_tree preview: {a11y_tree[:500]}...")
            internal_obs["accessibility_tree"] = a11y_tree
        else:
            logger.warning(f"[_convert_osworld_observation] ✗ accessibility_tree NOT found in observation!")
        
        # 提取 screenshot (如果存在)
        screenshot = osworld_obs.get("screenshot") or osworld_obs.get("image")
        if screenshot:
            screenshot_size = len(screenshot) if isinstance(screenshot, bytes) else "N/A"
            logger.info(f"[_convert_osworld_observation] ✓ screenshot extracted: {screenshot_size} bytes")
            internal_obs["screenshot"] = screenshot
        else:
            logger.info(f"[_convert_osworld_observation] - screenshot not present (optional)")
        
        # 提取 terminal (如果存在)
        terminal = osworld_obs.get("terminal")
        if terminal:
            logger.info(f"[_convert_osworld_observation] ✓ terminal extracted: {len(terminal)} chars")
            logger.debug(f"[_convert_osworld_observation] terminal preview: {terminal[:200]}...")
            internal_obs["terminal"] = terminal
        else:
            logger.info(f"[_convert_osworld_observation] - terminal not present (optional)")
        
        # 提取 instruction (如果存在)
        instruction = osworld_obs.get("instruction")
        if instruction:
            logger.info(f"[_convert_osworld_observation] ✓ instruction extracted: {len(instruction)} chars")
            internal_obs["instruction"] = instruction
        else:
            logger.info(f"[_convert_osworld_observation] - instruction not present (optional)")
        
        logger.info(f"[_convert_osworld_observation] Converted observation keys: {list(internal_obs.keys())}")
        logger.info(f"[_convert_osworld_observation] ===== End Conversion =====")
        
        return internal_obs

    def _reject_action(self, reason: str, action_payload: Optional[Dict[str, Any]] = None) -> str:
        """
        统一的动作拒绝处理：根据错误类型返回 WAIT（可恢复）或 FAIL（致命）。
        """
        logger.error(f"[PCGuiAgent._reject_action] Action rejected: {reason}")
        if action_payload is not None:
            logger.error(f"[PCGuiAgent._reject_action] Rejected action payload: {action_payload}")
        
        # 判断是否为致命错误（任务明确失败）
        fatal_keywords = ["Task failed", "Fatal", "Critical"]
        is_fatal = any(keyword.lower() in reason.lower() for keyword in fatal_keywords)
        
        if is_fatal:
            logger.error(f"[PCGuiAgent._reject_action] Fatal error, returning FAIL")
            return "FAIL"
        else:
            logger.warning(f"[PCGuiAgent._reject_action] Recoverable error, returning WAIT")
            return "WAIT"

    def _convert_action_to_pyautogui(self, action_type: str, parameters: Dict[str, Any]) -> Optional[str]:
        """
        将通用 action 格式转换为 pyautogui Python 代码字符串（OSWorld 模式）
        
        Args:
            action_type: Action 类型，如 "CLICK", "TYPE", "KEY" 等
            parameters: Action 参数
        
        Returns:
            pyautogui Python 代码字符串，如 "pyautogui.click(100, 200)", "pyautogui.press('enter')" 等
        """
        if not action_type:
            return None
        
        action_type_upper = action_type.upper()
        logger.debug(f"[_convert_action_to_pyautogui] Converting {action_type_upper} with parameters: {parameters}")
        logger.info(f"[_convert_action_to_pyautogui] Action conversion: {action_type_upper} -> pyautogui Python code")
        
        try:
            if action_type_upper == "CLICK":
                x = parameters.get("x")
                y = parameters.get("y")
                button = parameters.get("button", "left")
                num_clicks = parameters.get("num_clicks")
                
                if x is not None and y is not None:
                    if button and button != "left":
                        return f"pyautogui.click({int(x)}, {int(y)}, button='{button}', clicks={int(num_clicks) if num_clicks else 1})"
                    return f"pyautogui.click({int(x)}, {int(y)}, clicks={int(num_clicks) if num_clicks else 1})"
                else:
                    # Click at current position
                    if button and button != "left":
                        return f"pyautogui.click(button='{button}', clicks={int(num_clicks) if num_clicks else 1})"
                    return f"pyautogui.click(clicks={int(num_clicks) if num_clicks else 1})"
            
            elif action_type_upper == "TYPE" or action_type_upper == "TYPING":
                text = parameters.get("text", "")
                if text is not None:
                    # Use repr() to properly escape the string
                    return f"pyautogui.typewrite({repr(text)})"
                return None
            
            elif action_type_upper == "KEY" or action_type_upper == "PRESS":
                key = parameters.get("key")
                if key:
                    # Handle special key combinations like "ctrl+c"
                    # If it contains "+", split and use hotkey, otherwise use press
                    if "+" in str(key) or "," in str(key):
                        # Split by + or ,
                        if "+" in str(key):
                            keys_list = [k.strip() for k in str(key).split("+")]
                        else:
                            keys_list = [k.strip() for k in str(key).split(",")]
                        keys_str = ", ".join([repr(k) for k in keys_list])
                        return f"pyautogui.hotkey({keys_str})"
                    else:
                        return f"pyautogui.press({repr(str(key))})"
                return None
            
            elif action_type_upper == "SCROLL":
                dx = parameters.get("dx", 0)
                dy = parameters.get("dy", parameters.get("clicks", 0))
                parts = []
                if dx:
                    parts.append(f"pyautogui.hscroll({int(dx)})")
                parts.append(f"pyautogui.scroll({int(dy)})")
                return "; ".join(parts)
            
            elif action_type_upper in ("MOVE", "MOVE_TO"):
                x = parameters.get("x")
                y = parameters.get("y")
                if x is not None and y is not None:
                    return f"pyautogui.moveTo({int(x)}, {int(y)})"
                return None

            elif action_type_upper == "DRAG_TO":
                x = parameters.get("x")
                y = parameters.get("y")
                if x is not None and y is not None:
                    return f"pyautogui.dragTo({int(x)}, {int(y)})"
                return None
            
            elif action_type_upper == "DOUBLECLICK" or action_type_upper == "DOUBLE_CLICK":
                x = parameters.get("x")
                y = parameters.get("y")
                if x is not None and y is not None:
                    return f"pyautogui.doubleClick({int(x)}, {int(y)})"
                else:
                    return "pyautogui.doubleClick()"
            
            elif action_type_upper == "RIGHTCLICK" or action_type_upper == "RIGHT_CLICK":
                x = parameters.get("x")
                y = parameters.get("y")
                if x is not None and y is not None:
                    return f"pyautogui.rightClick({int(x)}, {int(y)})"
                else:
                    return "pyautogui.rightClick()"

            elif action_type_upper == "MOUSE_DOWN":
                button = parameters.get("button", "left")
                return f"pyautogui.mouseDown(button='{button}')" if button else "pyautogui.mouseDown()"

            elif action_type_upper == "MOUSE_UP":
                button = parameters.get("button", "left")
                return f"pyautogui.mouseUp(button='{button}')" if button else "pyautogui.mouseUp()"
            
            elif action_type_upper == "HOTKEY":
                keys = parameters.get("keys")
                if isinstance(keys, list) and keys:
                    keys_str = ", ".join([repr(str(k)) for k in keys])
                    return f"pyautogui.hotkey({keys_str})"
                return None

            elif action_type_upper in ("KEY_DOWN", "KEYDOWN"):
                key = parameters.get("key")
                if key:
                    return f"pyautogui.keyDown({repr(str(key))})"
                return None

            elif action_type_upper in ("KEY_UP", "KEYUP"):
                key = parameters.get("key")
                if key:
                    return f"pyautogui.keyUp({repr(str(key))})"
                return None
            
            elif action_type_upper == "WAIT":
                return "WAIT"
            
            elif action_type_upper == "DONE":
                return "DONE"
            
            elif action_type_upper == "FAIL":
                return "FAIL"
            
            logger.debug(f"[_convert_action_to_pyautogui] Unknown action type: {action_type_upper}")
            return None
            
        except Exception as e:
            logger.warning(f"[_convert_action_to_pyautogui] Error converting action: {e}")
            return None
    
    def _convert_mcp_action_to_pyautogui(self, action_name: str, action_args: Dict[str, Any]) -> Optional[str]:
        """
        将 MCP 工具调用转换为 pyautogui action 字符串
        
        Args:
            action_name: MCP 工具名称，如 "os.click", "os.type", "os.key" 等
            action_args: 工具参数
        
        Returns:
            pyautogui action 字符串，如 "CLICK 100 200", "TYPE hello", "KEY enter" 等
        """
        if not action_name:
            return None
        
        # 提取工具类型（os.click -> click）
        tool_type = action_name.split(".")[-1] if "." in action_name else action_name
        
        logger.debug(f"[_convert_mcp_action_to_pyautogui] Converting {action_name} with args: {action_args}")
        logger.info(f"[_convert_mcp_action_to_pyautogui] MCP action conversion: {action_name} (type: {tool_type}) -> pyautogui")
        
        try:
            if tool_type == "click":
                x = action_args.get("x")
                y = action_args.get("y")
                if x is not None and y is not None:
                    return f"CLICK {int(x)} {int(y)}"
            
            elif tool_type == "type" or tool_type == "typewrite":
                text = action_args.get("text") or action_args.get("content", "")
                if text:
                    # 转义特殊字符
                    text_escaped = text.replace('"', '\\"').replace('\n', '\\n')
                    return f'TYPE "{text_escaped}"'
            
            elif tool_type == "key" or tool_type == "press":
                key = action_args.get("key") or action_args.get("keys", [])
                if isinstance(key, list) and len(key) > 0:
                    key = key[0]
                if key:
                    return f"KEY {key}"
            
            elif tool_type == "scroll":
                x = action_args.get("x", 0)
                y = action_args.get("y", 0)
                clicks = action_args.get("clicks") or action_args.get("scroll_y", 0)
                if clicks != 0:
                    return f"SCROLL {int(clicks)} {int(x)} {int(y)}"
            
            elif tool_type == "move" or tool_type == "moveto":
                x = action_args.get("x")
                y = action_args.get("y")
                if x is not None and y is not None:
                    return f"MOVE {int(x)} {int(y)}"
            
            else:
                logger.debug(f"[_convert_mcp_action_to_pyautogui] Unknown tool type: {tool_type}")
                return None
                
        except Exception as e:
            logger.warning(f"[_convert_mcp_action_to_pyautogui] Error converting action: {e}")
            return None
        
        return None

    # ---------- CLI fallback ----------
    async def run(self, goal: str) -> Dict[str, Any]:
        """
        CLI 兼容的降级实现
        """
        await self.initialize()
        return {
            "success": False,
            "step_count": 0,
            "actions": [],
            "message": "OSWorld adapter runs only with act/step",
        }
