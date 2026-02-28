"""
Task completion verifier.
Ensures the task is truly finished and prevents premature termination.
"""
from typing import Dict, Any, Optional
from pcguiagent.utils.logger import get_logger

logger = get_logger("TaskVerifier")


class TaskVerifier:
    """
    Task completion verifier.
    
    Responsibilities:
    1. Verify the task is genuinely completed.
    2. Check whether key steps were executed.
    3. Ensure the output meets the task requirements.
    """
    
    def __init__(self, memory=None, app_detector=None):
        self.memory = memory
        self.app_detector = app_detector
    
    async def verify_completion(
        self,
        goal: str,
        final_output: Any,
        action_history: list,
        observation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        使用 MCP 工具的响应作为唯一验证标准。
        """
        # 1) 提取最近的 MCP 响应（优先 observation，其次 action_history 最后一条）
        latest_response = None
        if isinstance(observation, dict) and ("success" in observation or "error" in observation):
            latest_response = observation
        elif action_history:
            latest = action_history[-1] or {}
            latest_response = latest.get("result") or latest.get("observation")
        
        if latest_response is None:
            return {
                "is_complete": False,
                "confidence": 0.0,
                "reason": "没有可用的 MCP 响应，无法验证完成状态",
                "missing_steps": [],
                "suggestions": ["获取一次 MCP 工具响应后再判断是否完成"]
            }
        
        # 2) 提取工具的实际返回结果（支持嵌套结构）
        # 工具返回可能嵌套在 data.structured_content 或 data.content 中
        success = None
        error = None
        data = None
        
        # 首先尝试直接从 latest_response 获取
        if isinstance(latest_response, dict):
            success = latest_response.get("success")
            error = latest_response.get("error")
            data = latest_response.get("data")
            
            # 无条件检查 data.structured_content，因为工具的实际返回结果可能在这里
            # 无论外层 success 是什么，都要检查工具的实际返回结果
            if isinstance(data, dict):
                structured_content = data.get("structured_content")
                if isinstance(structured_content, dict):
                    # 优先使用工具的实际返回结果（覆盖外层的 success）
                    tool_success = structured_content.get("success")
                    tool_error = structured_content.get("error")
                    if tool_success is not None:
                        success = tool_success  # 使用工具的实际返回结果
                    if tool_error:
                        error = tool_error
                    # 如果 structured_content 有 data，使用它
                    if "data" in structured_content:
                        data = structured_content.get("data")
            
            # 如果 data 是字符串（JSON），尝试解析
            if isinstance(data, str):
                try:
                    import json
                    parsed_data = json.loads(data)
                    if isinstance(parsed_data, dict):
                        if "success" in parsed_data:
                            success = parsed_data.get("success")
                        if "error" in parsed_data:
                            error = parsed_data.get("error")
                        if "data" in parsed_data:
                            data = parsed_data.get("data")
                except (json.JSONDecodeError, ValueError):
                    pass
        
        # 确保 success 是布尔值
        success = bool(success) if success is not None else False
        
        if success:
            # 对于应用启动类任务，需要验证实际应用是否启动
            app_launch_verified = await self._verify_app_launch(goal, action_history)
            if app_launch_verified is not None:
                if not app_launch_verified:
                    # MCP 返回成功，但实际应用未启动
                    confidence = 0.3  # 低置信度
                    reason = "MCP 响应成功，但目标应用未检测到运行"
                    return {
                        "is_complete": False,
                        "confidence": confidence,
                        "reason": reason,
                        "missing_steps": ["目标应用可能未成功启动，需要重试"],
                        "suggestions": ["检查应用是否已安装并在 PATH 中", "重试启动应用"]
                    }
                else:
                    # 应用确实启动了
                    confidence = 1.0 if data else 0.9
                    reason = "MCP 响应成功，且目标应用已检测到运行"
            else:
                # 不是应用启动任务，或无法验证
                confidence = 1.0 if data else 0.85
                reason = "MCP 响应成功，认为任务已完成"
            
            return {
                "is_complete": True,
                "confidence": confidence,
                "reason": reason,
                "missing_steps": [],
                "suggestions": []
            }
        
        # 未成功时返回失败原因
        reason = f"MCP 响应失败：{error}" if error else "MCP 响应未成功"
        suggestions = []
        if error:
            suggestions.append(f"根据错误信息重试：{error}")
        else:
            suggestions.append("重试工具或重新规划后再次执行")
        
        return {
            "is_complete": False,
            "confidence": 0.0,
            "reason": reason,
            "missing_steps": [],
            "suggestions": suggestions[:2]
        }
    
    def _extract_requirements(self, goal: str) -> Dict[str, Any]:
        """Extract key requirements from the task goal."""
        goal_lower = goal.lower()
        requirements = {
            "actions": [],
            "outputs": [],
            "keywords": [],
            "tools_needed": []  # 需要的工具
        }
        
        # Extract action keywords
        action_keywords = ["open", "create", "write", "save", "install", "search", "find", "get", "extract", "query", "查询"]
        for keyword in action_keywords:
            if keyword in goal_lower:
                requirements["actions"].append(keyword)
        
        # Extract output requirements
        output_keywords = ["file", "document", "list", "report", "result", "data", "markdown", "json", "excel"]
        for keyword in output_keywords:
            if keyword in goal_lower:
                requirements["outputs"].append(keyword)
        
        # Derive tool needs based on task content
        if "vscode" in goal_lower or "插件" in goal_lower or "extension" in goal_lower:
            requirements["tools_needed"].append("code.list_extensions")
            if "打开" in goal_lower or "open" in goal_lower:
                requirements["tools_needed"].append("code.launch_vscode")
        
        if "excel" in goal_lower or "表格" in goal_lower:
            requirements["tools_needed"].extend(["excel.create_excel"])
            # If the task requires entering data, we may need to create a table and set column values.
            # Note: excel.create_table with a data argument can satisfy both creation and data entry.
            if any(kw in goal_lower for kw in ["填入", "填写", "fill", "set", "每行"]):
                # Prefer create_table (more efficient). If create_table has data, consider it satisfied.
                requirements["tools_needed"].append("excel.create_table")
                # set_column_values is a fallback when create_table lacks data.
                # _check_missing_steps treats create_table with data as satisfying set_column_values.
                requirements["tools_needed"].append("excel.set_column_values")
            else:
                requirements["tools_needed"].append("excel.create_table")
        
        # Extract other keywords
        requirements["keywords"] = [word for word in goal.split() if len(word) > 2]
        
        return requirements
    
    def _check_missing_steps(
        self,
        requirements: Dict[str, Any],
        action_history: list
    ) -> list:
        """Check for potentially missing steps."""
        missing = []
        
        # Check if key actions were executed
        executed_actions = [a.get("action", {}).get("name", "") for a in action_history]
        executed_actions_lower = [a.lower() for a in executed_actions]
        
        # Map action keywords to tool capabilities (semantic mapping)
        action_tool_mapping = {
            "查询": ["list", "get", "query", "search", "find", "extract"],
            "query": ["list", "get", "query", "search", "find", "extract"],
            "open": ["launch", "open", "start"],
            "create": ["create", "make", "new"],
            "write": ["write", "set", "update", "save"],
            "save": ["save", "write", "set"],
            "install": ["install"],
            "search": ["search", "find", "list", "get"],
            "find": ["find", "search", "list", "get"],
            "get": ["get", "list", "fetch", "retrieve"],
            "extract": ["extract", "get", "list"]
        }
        
        # Check whether corresponding actions exist
        for action_keyword in requirements.get("actions", []):
            found = False
            # 1. Directly check action names for the keyword
            if any(action_keyword in action for action in executed_actions_lower):
                found = True
            # 2. Check if semantically related tools were executed
            elif action_keyword in action_tool_mapping:
                related_tools = action_tool_mapping[action_keyword]
                if any(any(tool in action for tool in related_tools) for action in executed_actions_lower):
                    found = True
            # 3. Special case: if required tools ran, treat the action as covered
            #    e.g., "query" maps to code.list_extensions
            if not found:
                tools_needed = requirements.get("tools_needed", [])
                if any("list" in tool or "get" in tool or "query" in tool for tool in tools_needed):
                    if any(tool in " ".join(executed_actions_lower) for tool in tools_needed):
                        found = True
            
            if not found:
                missing.append(f"Action related to '{action_keyword}' may be missing")
        
        # Ensure save/write actions happened when files are expected
        if any(kw in " ".join(requirements.get("outputs", [])).lower() for kw in ["file", "document"]):
            has_save = any("save" in a or "write" in a or "create" in a for a in executed_actions_lower)
            if not has_save:
                missing.append("File save/write operation may be missing")
        
        # Verify all required tools were executed
        tools_needed = requirements.get("tools_needed", [])
        for tool in tools_needed:
            tool_found = any(tool in a for a in executed_actions_lower)
            
            # Special case 1: excel.create_table can replace excel.set_column_values
            # If excel.create_table ran with data, treat set_column_values as satisfied.
            if not tool_found and tool == "excel.set_column_values":
                if any("excel.create_table" in a for a in executed_actions_lower):
                    # 检查 excel.create_table 是否有数据参数
                    for action_item in action_history:
                        action_name = action_item.get("action", {}).get("name", "").lower()
                        if "excel.create_table" in action_name:
                            action_args = action_item.get("action", {}).get("args", {})
                            # 如果 create_table 有 data 参数且不为空，认为满足要求
                            if action_args.get("data") or action_args.get("headers"):
                                tool_found = True
                                logger.debug(f"[Verifier] excel.create_table with data satisfies excel.set_column_values requirement")
                                break
            
            # Special case 2: excel.set_cell_value + excel.set_column_values can replace excel.create_table.
            # If both ran (headers + data), treat create_table as satisfied.
            if not tool_found and tool == "excel.create_table":
                has_set_cell = any("excel.set_cell_value" in a for a in executed_actions_lower)
                has_set_column = any("excel.set_column_values" in a for a in executed_actions_lower)
                
                if has_set_cell and has_set_column:
                    # 检查 set_column_values 是否有数据（非空数组或成功执行）
                    for action_item in action_history:
                        action_name = action_item.get("action", {}).get("name", "").lower()
                        if "excel.set_column_values" in action_name:
                            action_args = action_item.get("action", {}).get("args", {})
                            result_data = action_item.get("result", {}).get("data", "")
                            result_success = action_item.get("result", {}).get("success", False)
                            
                            # Check 1: values parameter in args
                            values = action_args.get("values", [])
                            if isinstance(values, list) and len(values) > 0:
                                tool_found = True
                                logger.debug(f"[Verifier] excel.set_cell_value + excel.set_column_values (with {len(values)} values) satisfies excel.create_table requirement")
                                break
                            
                            # Check 2: success result string that includes value counts (e.g., "51 values")
                            if result_success and isinstance(result_data, str):
                                # Look for counts like "51 values" or "with X values"
                                import re
                                value_match = re.search(r'(\d+)\s*values?', result_data.lower())
                                if value_match and int(value_match.group(1)) > 0:
                                    tool_found = True
                                    logger.debug(f"[Verifier] excel.set_cell_value + excel.set_column_values (result shows {value_match.group(1)} values) satisfies excel.create_table requirement")
                                    break
                    
                    # Check 3: if both set_cell_value and set_column_values ran, assume the table structure exists.
                    if not tool_found and has_set_cell and has_set_column:
                        tool_found = True
                        logger.debug(f"[Verifier] excel.set_cell_value + excel.set_column_values combination satisfies excel.create_table requirement (structure created)")
            
            # Special case 3: if a query-style tool ran (e.g., code.list_extensions),
            # consider list/get/query requirements satisfied.
            if not tool_found and ("list" in tool.lower() or "get" in tool.lower() or "query" in tool.lower()):
                # 检查是否有任何 list/get/query 相关的工具已执行
                query_related_actions = [a for a in executed_actions_lower if any(kw in a for kw in ["list", "get", "query"])]
                if query_related_actions:
                    tool_found = True
                    logger.debug(f"[Verifier] Query-related action found: {query_related_actions}, satisfies tool requirement: {tool}")
            
            if not tool_found:
                missing.append(f"Required tool '{tool}' may not have been executed")
        
        return missing
    
    def _check_output_relevance(self, goal: str, output: Any) -> float:
        """Check how relevant the output is to the task goal."""
        if not output:
            return 0.0
        
        output_str = str(output).lower()
        goal_lower = goal.lower()
        
        # Extract keywords from the goal
        goal_words = set(word for word in goal_lower.split() if len(word) > 3)
        
        # Check whether the output contains goal keywords
        output_words = set(word for word in output_str.split() if len(word) > 3)
        
        # Calculate overlap
        if len(goal_words) == 0:
            return 0.5  # 无法判断
        
        overlap = len(goal_words & output_words) / len(goal_words)
        
        # Penalize very short outputs (likely incomplete)
        if len(output_str) < 10:
            overlap *= 0.5
        
        return min(overlap, 1.0)
    
    def _calculate_confidence(
        self,
        missing_steps: list,
        output_relevance: float,
        action_count: int
    ) -> float:
        """Compute completion confidence."""
        # If no critical steps are missing, we can consider the task complete even with lower relevance.
        if len(missing_steps) == 0:
            # No missing steps means critical actions were executed.
            # Reduce dependence on output_relevance; lift baseline confidence.
            confidence = 0.75 + (output_relevance * 0.25)  # Base 0.75 plus relevance adjustment (max 1.0)
        else:
            # Missing steps require a blended calculation
            confidence = 1.0
            confidence -= len(missing_steps) * 0.2  # 缺失步骤扣分
            confidence = confidence * 0.4 + output_relevance * 0.6
        
        # Action-count check (more actions suggest progress)
        if action_count >= 4:  # At least four actions for multi-step tasks
            confidence += 0.05  # Small bonus
        elif action_count >= 3:
            pass  # 正常
        elif action_count < 2:
            confidence *= 0.85  # 动作太少扣分
        
        return max(0.0, min(1.0, confidence))
    
    def _generate_reason(
        self,
        missing_steps: list,
        output_relevance: float,
        confidence: float
    ) -> str:
        """生成验证原因"""
        if confidence >= 0.7:
            return "Task appears to be completed successfully"
        elif missing_steps:
            return f"Task may be incomplete: {', '.join(missing_steps[:2])}"
        elif output_relevance < 0.5:
            return "Output does not seem relevant to the task goal"
        else:
            return "Task completion uncertain, more verification needed"
    
    def _generate_suggestions(
        self,
        missing_steps: list,
        output_relevance: float
    ) -> list:
        """生成建议"""
        suggestions = []
        
        if missing_steps:
            suggestions.extend(missing_steps[:3])
        
        if output_relevance < 0.5:
            suggestions.append("Verify that the output matches the task requirements")
        
        if not suggestions:
            suggestions.append("Task appears complete, but double-check the results")
        
        return suggestions
    
    async def _verify_app_launch(self, goal: str, action_history: list) -> Optional[bool]:
        """
        验证应用启动类任务是否真正完成。
        
        Returns:
            True: 应用已启动
            False: 应用未启动
            None: 不是应用启动任务或无法验证
        """
        if not self.app_detector:
            return None
        
        goal_lower = goal.lower()
        
        # 检查是否是应用启动任务
        app_launch_keywords = {
            "vscode": ["打开vscode", "open vscode", "启动vscode", "launch vscode", "打开code", "open code"],
            "chrome": ["打开chrome", "open chrome", "打开浏览器", "open browser"],
            "excel": ["打开excel", "open excel"],
        }
        
        target_app = None
        for app, keywords in app_launch_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                target_app = app
                break
        
        if not target_app:
            return None  # 不是应用启动任务
        
        # 检查是否执行了启动工具
        launch_tools = {
            "vscode": "code.launch_vscode",
            "chrome": "google_chrome.chrome_open_tabs_setup",
            "excel": "excel.create_excel",  # Excel 通常通过创建文件启动
        }
        
        expected_tool = launch_tools.get(target_app)
        if not expected_tool:
            return None
        
        # 检查 action_history 中是否有启动工具
        has_launch_action = False
        for action_item in action_history:
            action_name = action_item.get("action", {}).get("name", "")
            if expected_tool in action_name:
                has_launch_action = True
                break
        
        if not has_launch_action:
            return None  # 没有执行启动动作，无法验证
        
        # 启动后的耐心等待 + 多次重试检测，减少误判
        retry_intervals = [0.5, 1.0, 1.5]  # seconds, total wait 3s
        for attempt, delay in enumerate(retry_intervals, start=1):
            # 先尝试基于进程名的快速检查（更宽松，只要进程存在就认为启动）
            process_running = self._is_process_running(target_app)
            
            # 再尝试前台/窗口检测，保证体验更准确
            detected_app = None
            try:
                app_info = self.app_detector.get_current_app()
                if app_info:
                    detected_app = app_info.get("app_name", "").lower()
            except Exception as e:
                logger.debug(f"[TaskVerifier] App detection failed on attempt {attempt}: {e}")
            
            # 映射检测到的应用名到目标应用
            app_mapping = {
                "code": "vscode",
                "chrome": "chrome",
                "excel": "excel",
            }
            detected_mapped = app_mapping.get(detected_app, detected_app) if detected_app else None
            
            # 成功条件：前台/窗口匹配 或 进程存在
            if detected_mapped == target_app:
                logger.info(f"[TaskVerifier] ✅ 目标应用 {target_app} 已检测到运行 (attempt {attempt})")
                return True
            if process_running:
                logger.info(f"[TaskVerifier] ✅ 目标应用 {target_app} 进程已检测到 (attempt {attempt})")
                return True
            
            # 最后一次尝试后仍未检测到，判定失败
            if attempt == len(retry_intervals):
                logger.warning(
                    f"[TaskVerifier] ⚠️ 目标应用 {target_app} 未检测到运行，"
                    f"前台: {detected_app or 'none'}, process: {process_running}"
                )
                return False
            
            # 等待下一次检测
            try:
                import asyncio
                await asyncio.sleep(delay)
            except Exception:
                # 如果 asyncio 不可用，直接使用同步等待作为兜底
                import time
                time.sleep(delay)
        
        return None  # 理论上不会到这里

    def _is_process_running(self, target_app: str) -> bool:
        """
        粗略检测目标应用进程是否存在，用于补偿前台窗口检测不可靠的情况。
        """
        try:
            import psutil  # type: ignore
        except ImportError:
            return False
        except Exception:
            return False
        
        process_names = {
            "vscode": ["code", "code.exe"],
            "chrome": ["chrome", "chrome.exe", "msedge", "msedge.exe"],
            "excel": ["excel", "excel.exe"],
        }
        candidates = process_names.get(target_app, [])
        if not candidates:
            return False
        
        try:
            for p in psutil.process_iter(attrs=["name"]):
                name = (p.info.get("name") or "").lower()
                if name.endswith(".exe"):
                    name = name[:-4]
                if name in candidates:
                    return True
        except Exception:
            return False
        
        return False

