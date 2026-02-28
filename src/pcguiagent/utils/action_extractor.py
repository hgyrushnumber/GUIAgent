"""
Action Extractor - 专门处理 action 提取的工具类

将复杂的 action 提取逻辑从 agent.py 中分离出来，提高代码可维护性。
"""
from typing import Dict, Optional, Any, List

from pcguiagent.utils.logger import get_logger
from pcguiagent.core.osworld_actions import validate_osworld_action, get_osworld_actions

logger = get_logger("ActionExtractor")


class ActionExtractor:
    """专门处理 action 提取的类"""
    
    def __init__(self, task_manager: Optional[Any] = None):
        """
        初始化 ActionExtractor
        
        Args:
            task_manager: 已废弃，保留仅为向后兼容（Intra-Agent 架构不再需要）
        """
        self.task_manager = task_manager  # Deprecated, kept for backward compatibility
        # 转换方法将在外部设置
        self._convert_action_to_pyautogui = None
        self._convert_mcp_action_to_pyautogui = None
        
        # 缓存 OSWorld 允许的键名列表
        try:
            osworld_actions = get_osworld_actions()
            self._allowed_keys = set(osworld_actions.get("KEYBOARD_KEYS", []))
        except Exception as e:
            logger.warning(f"[ActionExtractor] Failed to load KEYBOARD_KEYS: {e}, using empty set")
            self._allowed_keys = set()
    
    def extract_from_planner_output(self, action_data: Dict[str, Any]) -> Optional[str]:
        """
        直接从 RecursivePlanner 的输出中提取 action 并转换为 OSWorld pyautogui action 字符串
        
        Args:
            action_data: RecursivePlanner.next_action() 返回的 JSON 解析后的字典，包含：
                - action: Dict[str, Any] - action 信息
                - is_done: bool - 是否完成
                - thought: str - 思考过程（可选）
        
        Returns:
            pyautogui action 字符串，如果无法提取则返回 WAIT（可恢复）或 FAIL（致命错误）
        """
        logger.info(f"[ActionExtractor.extract_from_planner_output] ===== Starting Action Extraction from Planner Output =====")
        logger.info(f"[ActionExtractor.extract_from_planner_output] Action data keys: {list(action_data.keys())}")
        logger.debug(f"[ActionExtractor.extract_from_planner_output] Full action data: {action_data}")
        
        # 检查是否完成
        if action_data.get("is_done"):
            logger.info("[ActionExtractor.extract_from_planner_output] Task is done")
            return "DONE"
        
        # 提取 action
        action = action_data.get("action", {})
        if not action:
            logger.warning(f"[ActionExtractor.extract_from_planner_output] No action in action_data, returning WAIT")
            return "WAIT"
        
        if not isinstance(action, dict):
            logger.warning(f"[ActionExtractor.extract_from_planner_output] Action is not a dict: {type(action)}, returning WAIT")
            return "WAIT"
        
        logger.info(f"[ActionExtractor.extract_from_planner_output] Action type: {type(action)}")
        logger.info(f"[ActionExtractor.extract_from_planner_output] Action: {action}")
        
        # 尝试提取 Generic 格式 (OSWorld mode)
        action_type = action.get("action_type")
        parameters = action.get("parameters")
        
        logger.info(f"[ActionExtractor.extract_from_planner_output] Checking for generic format: action_type={action_type}, parameters={parameters is not None}")
        if action_type and parameters is not None:
            logger.info(f"[ActionExtractor.extract_from_planner_output] Found generic format, extracting...")
            return self._extract_generic_format(action_type, parameters, action)
        
        # 尝试提取 MCP 格式 (traditional mode)
        action_name = action.get("name")
        action_args = action.get("args", {})
        
        logger.info(f"[ActionExtractor.extract_from_planner_output] Checking for MCP format: action_name={action_name}")
        if action_name:
            logger.info(f"[ActionExtractor.extract_from_planner_output] Found MCP format, extracting...")
            return self._extract_mcp_format(action_name, action_args, action)
        
        # 格式无法识别
        logger.warning(f"[ActionExtractor.extract_from_planner_output] Action format not recognized: {action}")
        logger.warning(f"[ActionExtractor.extract_from_planner_output] Returning WAIT (recoverable error)")
        return "WAIT"
    
    def extract(self, result: Dict[str, Any], current_task_id: Optional[str] = None) -> Optional[str]:
        """
        从 TaskManager 的 task 中提取当前步骤的 action 并转换为 OSWorld pyautogui action 字符串
        
        DEPRECATED: This method is deprecated. Use extract_from_planner_output() instead.
        
        Args:
            result: TaskManager.execute_next_step() 返回的字典
            current_task_id: 当前任务 ID
        
        Returns:
            pyautogui action 字符串，如果无法提取则返回 WAIT（可恢复）或 FAIL（致命错误）
        """
        logger.info(f"[ActionExtractor.extract] ===== Starting Action Extraction =====")
        logger.info(f"[ActionExtractor.extract] Task ID: {current_task_id}")
        logger.info(f"[ActionExtractor.extract] Result status: {result.get('status', 'unknown')}")
        logger.info(f"[ActionExtractor.extract] Result keys: {list(result.keys())}")
        logger.debug(f"[ActionExtractor.extract] Full result: {result}")
        
        status = result.get("status", "waiting")
        
        # 任务完成
        if status == "completed":
            logger.info("[ActionExtractor.extract] Task completed")
            return "DONE"
        
        # 任务失败
        if status == "failed":
            error = result.get("error", "Unknown error")
            logger.error(f"[ActionExtractor.extract] Task failed: {error}")
            return "FAIL"  # 任务失败是致命错误，返回 FAIL
        
        # 从 task 中获取最后执行的 action
        if not current_task_id:
            logger.warning("[ActionExtractor.extract] No task ID provided, returning WAIT")
            return "WAIT"  # 可恢复错误，返回 WAIT
        
        task = self.task_manager._tasks.get(current_task_id)
        if not task:
            logger.warning(f"[ActionExtractor.extract] Task {current_task_id} not found, returning WAIT")
            return "WAIT"  # 可恢复错误，返回 WAIT
        
        logger.info(f"[ActionExtractor.extract] Task found: {current_task_id}")
        logger.info(f"[ActionExtractor.extract] Task status: {task.status}")
        logger.info(f"[ActionExtractor.extract] Task results count: {len(task.results)}")
        
        # 获取最后一步的 action（刚执行的步骤）
        if not task.results:
            logger.warning(f"[ActionExtractor.extract] No results in task (may be first step, plan not generated yet), returning WAIT")
            return "WAIT"  # 可能是第一步，plan 还没生成，返回 WAIT 而不是 FAIL
        
        last_result = task.results[-1]
        action_info = last_result.get("action", {})
        
        logger.info(f"[ActionExtractor.extract] ===== Extracting Action from Task Result =====")
        logger.info(f"[ActionExtractor.extract] Last result keys: {list(last_result.keys())}")
        logger.info(f"[ActionExtractor.extract] Action info type: {type(action_info)}")
        logger.info(f"[ActionExtractor.extract] Action info: {action_info}")
        logger.debug(f"[ActionExtractor.extract] Full last_result: {last_result}")
        
        if not action_info or not isinstance(action_info, dict):
            logger.warning(f"[ActionExtractor.extract] Action info is not a dict or is empty: {action_info}")
            logger.warning(f"[ActionExtractor.extract] Returning WAIT (recoverable error)")
            return "WAIT"  # 可恢复错误，返回 WAIT
        
        # 尝试提取 Generic 格式 (OSWorld mode)
        action_type = action_info.get("action_type")
        parameters = action_info.get("parameters")
        
        logger.info(f"[ActionExtractor.extract] Checking for generic format: action_type={action_type}, parameters={parameters is not None}")
        if action_type and parameters is not None:
            logger.info(f"[ActionExtractor.extract] Found generic format, extracting...")
            return self._extract_generic_format(action_type, parameters, action_info)
        
        # 尝试提取 MCP 格式 (traditional mode)
        action_name = action_info.get("name")
        action_args = action_info.get("args", {})
        
        logger.info(f"[ActionExtractor.extract] Checking for MCP format: action_name={action_name}")
        if action_name:
            logger.info(f"[ActionExtractor.extract] Found MCP format, extracting...")
            return self._extract_mcp_format(action_name, action_args, action_info)
        
        # 格式无法识别
        logger.warning(f"[ActionExtractor.extract] Action info format not recognized: {action_info}")
        logger.warning(f"[ActionExtractor.extract] Returning WAIT (recoverable error)")
        return "WAIT"  # 可恢复错误，返回 WAIT
    
    def _validate_and_correct_coordinates(
        self, 
        action_type: str, 
        parameters: Dict[str, Any],
        screen_width: int = 1920,
        screen_height: int = 1080
    ) -> Dict[str, Any]:
        """
        验证并修正坐标参数
        
        Args:
            action_type: Action 类型
            parameters: Action 参数
            screen_width: 屏幕宽度（默认 1920）
            screen_height: 屏幕高度（默认 1080）
        
        Returns:
            修正后的参数字典
        """
        corrected_params = parameters.copy()
        
        # 需要坐标的 action 类型
        coord_actions = ['CLICK', 'MOVE_TO', 'DRAG_TO', 'RIGHT_CLICK', 'DOUBLE_CLICK']
        
        if action_type.upper() in coord_actions:
            x = parameters.get('x')
            y = parameters.get('y')
            
            # 验证和修正 x 坐标
            if x is not None:
                try:
                    x = float(x)
                    if x < 0:
                        logger.warning(f"[ActionExtractor._validate_and_correct_coordinates] x={x} < 0, clamping to 0")
                        x = 0
                    elif x > screen_width:
                        logger.warning(f"[ActionExtractor._validate_and_correct_coordinates] x={x} > {screen_width}, clamping to {screen_width}")
                        x = screen_width
                    corrected_params['x'] = int(x)
                except (ValueError, TypeError):
                    logger.warning(f"[ActionExtractor._validate_and_correct_coordinates] Invalid x coordinate: {x}, removing")
                    corrected_params.pop('x', None)
            
            # 验证和修正 y 坐标
            if y is not None:
                try:
                    y = float(y)
                    if y < 0:
                        logger.warning(f"[ActionExtractor._validate_and_correct_coordinates] y={y} < 0, clamping to 0")
                        y = 0
                    elif y > screen_height:
                        logger.warning(f"[ActionExtractor._validate_and_correct_coordinates] y={y} > {screen_height}, clamping to {screen_height}")
                        y = screen_height
                    corrected_params['y'] = int(y)
                except (ValueError, TypeError):
                    logger.warning(f"[ActionExtractor._validate_and_correct_coordinates] Invalid y coordinate: {y}, removing")
                    corrected_params.pop('y', None)
            
            # 如果坐标被移除，记录警告
            if 'x' not in corrected_params or 'y' not in corrected_params:
                logger.warning(f"[ActionExtractor._validate_and_correct_coordinates] Missing coordinates after validation for {action_type}")
        
        return corrected_params
    
    def _normalize_key_name(self, key: str) -> str:
        """
        规范化键盘键名，将常见变体转换为 OSWorld 标准格式。
        
        Args:
            key: 原始键名（可能包含变体如 "Super", "Ctrl", "Alt" 等）
        
        Returns:
            规范化后的键名（OSWorld 标准格式）
        """
        if not isinstance(key, str):
            return key
        
        key_lower = key.lower()
        
        # 键名映射表：常见变体 → OSWorld 标准格式
        key_mapping = {
            # Super/Win 键
            "super": "win",
            "super_l": "winleft",
            "super_r": "winright",
            "superleft": "winleft",
            "superright": "winright",
            "windows": "win",
            "windowsleft": "winleft",
            "windowsright": "winright",
            
            # Ctrl 键
            "ctrl": "ctrl",
            "ctrl_l": "ctrlleft",
            "ctrl_r": "ctrlright",
            "ctrlleft": "ctrlleft",
            "ctrlright": "ctrlright",
            "control": "ctrl",
            "controlleft": "ctrlleft",
            "controlright": "ctrlright",
            
            # Alt 键
            "alt": "alt",
            "alt_l": "altleft",
            "alt_r": "altright",
            "altleft": "altleft",
            "altright": "altright",
            "option": "option",
            "optionleft": "optionleft",
            "optionright": "optionright",
            
            # Shift 键
            "shift": "shift",
            "shift_l": "shiftleft",
            "shift_r": "shiftright",
            "shiftleft": "shiftleft",
            "shiftright": "shiftright",
            
            # 特殊键
            "enter": "enter",
            "return": "return",
            "tab": "tab",
            "space": " ",
            "escape": "esc",
            "esc": "esc",
            "backspace": "backspace",
            "delete": "delete",
            "del": "del",
        }
        
        # 检查映射表
        if key_lower in key_mapping:
            normalized = key_mapping[key_lower]
            if normalized != key:
                logger.debug(f"[ActionExtractor._normalize_key_name] Normalized '{key}' → '{normalized}'")
            return normalized
        
        # 单字符键：转换为小写
        if len(key) == 1:
            normalized = key.lower()
            if normalized != key:
                logger.debug(f"[ActionExtractor._normalize_key_name] Normalized single char '{key}' → '{normalized}'")
            return normalized
        
        # 如果键名已经在允许列表中，直接返回
        if key in self._allowed_keys:
            return key
        
        # 尝试小写版本
        if key_lower in self._allowed_keys:
            logger.debug(f"[ActionExtractor._normalize_key_name] Normalized '{key}' → '{key_lower}' (lowercase)")
            return key_lower
        
        # 无法规范化，返回原值（让验证器处理）
        logger.warning(f"[ActionExtractor._normalize_key_name] Could not normalize key '{key}', keeping original")
        return key
    
    def _normalize_keyboard_parameters(self, action_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化键盘相关的参数（key 或 keys）。
        
        Args:
            action_type: Action 类型
            parameters: Action 参数
        
        Returns:
            规范化后的参数字典
        """
        normalized_params = parameters.copy()
        
        # 需要键盘参数的 action 类型
        keyboard_actions = ['PRESS', 'KEY_DOWN', 'KEY_UP', 'HOTKEY']
        
        if action_type.upper() in keyboard_actions:
            # PRESS, KEY_DOWN, KEY_UP: 规范化 'key' 参数
            if 'key' in normalized_params:
                original_key = normalized_params['key']
                normalized_key = self._normalize_key_name(original_key)
                normalized_params['key'] = normalized_key
                if normalized_key != original_key:
                    logger.info(f"[ActionExtractor._normalize_keyboard_parameters] Normalized key: '{original_key}' → '{normalized_key}'")
            
            # HOTKEY: 规范化 'keys' 列表中的每个键
            if 'keys' in normalized_params:
                original_keys = normalized_params['keys']
                if isinstance(original_keys, list):
                    normalized_keys = [self._normalize_key_name(k) for k in original_keys]
                    normalized_params['keys'] = normalized_keys
                    if normalized_keys != original_keys:
                        logger.info(f"[ActionExtractor._normalize_keyboard_parameters] Normalized keys: {original_keys} → {normalized_keys}")
        
        return normalized_params
    
    def _extract_generic_format(
        self, 
        action_type: str, 
        parameters: Dict[str, Any], 
        action_info: Dict[str, Any]
    ) -> Optional[str]:
        """处理 Generic 格式 (OSWorld mode)"""
        logger.info(f"[ActionExtractor._extract_generic_format] ===== Extracting Generic Format =====")
        logger.info(f"[ActionExtractor._extract_generic_format] Action type: {action_type}")
        logger.info(f"[ActionExtractor._extract_generic_format] Parameters: {parameters}")
        
        # 规范化键盘参数（在验证之前）
        parameters = self._normalize_keyboard_parameters(action_type, parameters)
        logger.info(f"[ActionExtractor._extract_generic_format] Parameters after keyboard normalization: {parameters}")
        
        # 验证并修正坐标
        parameters = self._validate_and_correct_coordinates(action_type, parameters)
        logger.info(f"[ActionExtractor._extract_generic_format] Parameters after coordinate validation: {parameters}")
        
        # Enforce OSWorld action constraints before conversion
        is_valid, err = validate_osworld_action(action_type, parameters)
        if not is_valid:
            logger.error(f"[ActionExtractor._extract_generic_format] Invalid OSWorld action: {err}")
            logger.error(f"[ActionExtractor._extract_generic_format] Action info: {action_info}")
            return "WAIT"  # 验证失败，返回 WAIT 而不是 FAIL
        
        logger.info(f"[ActionExtractor._extract_generic_format] Action validation passed")
        
        # 使用绑定的转换方法
        if self._convert_action_to_pyautogui:
            logger.info(f"[ActionExtractor._extract_generic_format] Converting action to pyautogui format...")
            pyautogui_action = self._convert_action_to_pyautogui(action_type, parameters)
        else:
            logger.error("[ActionExtractor._extract_generic_format] _convert_action_to_pyautogui not set, cannot convert action")
            pyautogui_action = None
        
        if pyautogui_action:
            logger.info(f"[ActionExtractor._extract_generic_format] ✓ Successfully converted to pyautogui action: {pyautogui_action}")
            return pyautogui_action
        else:
            logger.warning(f"[ActionExtractor._extract_generic_format] Failed to convert action {action_type} to pyautogui format")
            logger.warning(f"[ActionExtractor._extract_generic_format] Returning WAIT (recoverable error)")
            return "WAIT"  # 转换失败，返回 WAIT 而不是 FAIL
    
    def _extract_mcp_format(
        self, 
        action_name: str, 
        action_args: Dict[str, Any], 
        action_info: Dict[str, Any]
    ) -> Optional[str]:
        """处理 MCP 格式 (traditional mode)"""
        logger.info(f"[ActionExtractor._extract_mcp_format] ===== Extracting MCP Format =====")
        logger.info(f"[ActionExtractor._extract_mcp_format] Action name: {action_name}")
        logger.info(f"[ActionExtractor._extract_mcp_format] Action args: {action_args}")
        
        # 使用绑定的转换方法
        if self._convert_mcp_action_to_pyautogui:
            logger.info(f"[ActionExtractor._extract_mcp_format] Converting MCP action to pyautogui format...")
            pyautogui_action = self._convert_mcp_action_to_pyautogui(action_name, action_args)
        else:
            logger.error("[ActionExtractor._extract_mcp_format] _convert_mcp_action_to_pyautogui not set, cannot convert action")
            pyautogui_action = None
        
        if pyautogui_action:
            logger.info(f"[ActionExtractor._extract_mcp_format] ✓ Successfully converted to pyautogui action: {pyautogui_action}")
            return pyautogui_action
        else:
            logger.warning(f"[ActionExtractor._extract_mcp_format] Failed to convert MCP action {action_name} to pyautogui format")
            logger.warning(f"[ActionExtractor._extract_mcp_format] Returning WAIT (recoverable error)")
            return "WAIT"  # 转换失败，返回 WAIT 而不是 FAIL

