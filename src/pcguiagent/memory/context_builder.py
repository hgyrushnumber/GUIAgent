"""
Memory Context Builder
为 Planner 构建包含 Memory 数据的上下文，确保 LLM 能够正确使用之前步骤的数据
"""
import json
from typing import Dict, Any, Optional, List
from pcguiagent.utils.logger import get_logger

logger = get_logger("MemoryContextBuilder")


class MemoryContextBuilder:
    """
    Memory 上下文构建器 - 简化版
    
    职责：
    1. 从 Working Memory 提取工具结果数据
    2. 以 JSON 格式展示完整数据结构，供 LLM 直接使用
    """
    
    def __init__(self, memory):
        self.memory = memory
    
    def build_context(self, include_raw: bool = False) -> str:
        """
        构建 Memory 上下文，以 JSON 格式返回，方便 LLM 直接解析和使用
        
        Args:
            include_raw: 是否包含原始数据（已废弃，保持兼容性）
            
        Returns:
            JSON 格式的上下文字符串
        """
        # 获取所有工具结果
        tool_results = self._get_all_tool_results()
        
        if not tool_results:
            return ""
        
        # 构建 JSON 结构
        memory_data = {}
        
        for tool_name, data in tool_results.items():
            structured_data = data.get("structured_data")
            
            if structured_data:
                # 限制数据大小，避免 token 过多
                if isinstance(structured_data, list):
                    if len(structured_data) > 100:
                        # 如果列表太长，只保留前100项，并添加元数据
                        memory_data[tool_name] = {
                            "_metadata": {
                                "total_items": len(structured_data),
                                "showing": 100,
                                "note": f"Showing first 100 of {len(structured_data)} items"
                            },
                            "data": structured_data[:100]
                        }
                    else:
                        # 直接使用完整数据
                        memory_data[tool_name] = structured_data
                elif isinstance(structured_data, dict):
                    memory_data[tool_name] = structured_data
                else:
                    # 其他类型，转换为字符串
                    memory_data[tool_name] = {
                        "_type": type(structured_data).__name__,
                        "data": str(structured_data)
                    }
            else:
                # 没有结构化数据，只保存摘要信息
                memory_data[tool_name] = {
                    "_summary": data.get("summary", "No structured data available"),
                    "_step": data.get("step", "N/A"),
                    "_type": data.get("output_type", "unknown")
                }
        
        # 构建最终的 JSON 格式上下文
        context_json = {
            "working_memory": memory_data,
            "_instruction": "Use the data in 'working_memory' directly in your action args. For lists, use them as data rows for Excel operations."
        }
        
        # 返回格式化的 JSON 字符串
        try:
            json_str = json.dumps(context_json, ensure_ascii=False, indent=2)
            return f"# Working Memory (JSON)\n\n```json\n{json_str}\n```"
        except Exception as e:
            logger.error(f"[ContextBuilder] Failed to serialize memory context: {e}")
            return ""
    
    
    def _get_all_tool_results(self) -> Dict[str, Dict[str, Any]]:
        """获取所有工具结果"""
        results = {}
        context_dict = self.memory.short_term.to_dict()
        
        for key, value in context_dict.items():
            if key.startswith("tool_result_") and isinstance(value, dict):
                # 排除 _data 和 _field 后缀的键
                if not key.endswith("_data") and not any(
                    key.endswith(f"_{field}") 
                    for field in value.get("key_fields", {}).keys()
                ):
                    tool_name = key.replace("tool_result_", "")
                    if "tool_name" in value:
                        results[tool_name] = value
        
        return results

