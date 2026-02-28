"""
工具输出结构化解析器
自动识别和解析工具输出，特别是长列表、JSON等复杂结构
"""
import json
import re
from typing import Any, Dict, List, Optional, Union
from pcguiagent.utils.logger import get_logger

logger = get_logger("ToolOutputParser")


class ToolOutputParser:
    """
    工具输出结构化解析器
    
    功能：
    1. 自动识别输出类型（列表、JSON、文本等）
    2. 结构化解析复杂输出
    3. 提取关键信息供后续步骤使用
    """
    
    @staticmethod
    def parse(result_data: Any, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        解析工具输出，返回结构化数据
        
        Args:
            result_data: 工具返回的原始数据
            tool_name: 工具名称（用于特定解析规则）
            
        Returns:
            结构化数据字典，包含：
            - type: 输出类型（list, json, text, etc.）
            - structured_data: 结构化后的数据
            - summary: 数据摘要
            - key_fields: 关键字段提取
        """
        if result_data is None:
            return {
                "type": "empty",
                "structured_data": None,
                "summary": "No data returned",
                "key_fields": {}
            }
        
        # 如果已经是字典，检查是否有content字段
        if isinstance(result_data, dict):
            content = result_data.get("content", result_data)
            
            # 尝试解析content字段
            if isinstance(content, str):
                parsed = ToolOutputParser._parse_string_content(content, tool_name)
                return parsed
            else:
                # content不是字符串，直接使用
                return ToolOutputParser._parse_dict(result_data, tool_name)
        
        # 如果是字符串，尝试解析
        if isinstance(result_data, str):
            return ToolOutputParser._parse_string_content(result_data, tool_name)
        
        # 如果是列表，直接返回
        if isinstance(result_data, list):
            return ToolOutputParser._parse_list(result_data, tool_name)
        
        # 其他类型，转换为字符串
        return {
            "type": "unknown",
            "structured_data": str(result_data),
            "summary": f"Unstructured data: {type(result_data).__name__}",
            "key_fields": {"raw": str(result_data)}
        }
    
    @staticmethod
    def _parse_string_content(content: str, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """解析字符串内容"""
        content = content.strip()
        
        # 1. 尝试解析为JSON
        json_result = ToolOutputParser._try_parse_json(content)
        if json_result:
            return json_result
        
        # 2. 尝试解析为列表（多行文本）
        list_result = ToolOutputParser._try_parse_list(content, tool_name)
        if list_result:
            return list_result
        
        # 3. 尝试提取结构化信息（表格、键值对等）
        structured_result = ToolOutputParser._try_extract_structured(content, tool_name)
        if structured_result:
            return structured_result
        
        # 4. 普通文本
        return {
            "type": "text",
            "structured_data": content,
            "summary": f"Text output ({len(content)} chars)",
            "key_fields": {"text": content[:500]}  # 只保留前500字符
        }
    
    @staticmethod
    def _try_parse_json(content: str) -> Optional[Dict[str, Any]]:
        """尝试解析JSON"""
        try:
            data = json.loads(content)
            return {
                "type": "json",
                "structured_data": data,
                "summary": f"JSON object with {len(data)} keys" if isinstance(data, dict) else f"JSON {type(data).__name__}",
                "key_fields": ToolOutputParser._extract_key_fields_from_dict(data) if isinstance(data, dict) else {"value": data}
            }
        except (json.JSONDecodeError, ValueError):
            # 尝试提取JSON片段
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return {
                        "type": "json",
                        "structured_data": data,
                        "summary": f"JSON object extracted from text",
                        "key_fields": ToolOutputParser._extract_key_fields_from_dict(data) if isinstance(data, dict) else {}
                    }
                except:
                    pass
            return None
    
    @staticmethod
    def _try_parse_list(content: str, tool_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """尝试解析为列表"""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if len(lines) < 2:
            return None
        
        # 检查是否是列表格式（每行一个项目）
        # 常见格式：
        # - 编号列表：1. item, 2. item
        # - 项目符号：- item, * item
        # - 纯列表：item1, item2
        # - 表格：| col1 | col2 |
        
        items = []
        is_numbered = False
        is_bulleted = False
        
        for line in lines:
            # 检查编号列表
            numbered_match = re.match(r'^\d+[\.\)]\s*(.+)', line)
            if numbered_match:
                items.append(numbered_match.group(1))
                is_numbered = True
                continue
            
            # 检查项目符号
            bulleted_match = re.match(r'^[-*•]\s*(.+)', line)
            if bulleted_match:
                items.append(bulleted_match.group(1))
                is_bulleted = True
                continue
            
            # 检查表格行
            if '|' in line:
                # 跳过表头分隔行
                if re.match(r'^\|[\s\-:]+\|', line):
                    continue
                # 提取表格单元格
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                if cells:
                    items.append(cells)
                continue
            
            # 普通行，如果前面已经有列表项，继续添加
            if items or len(lines) > 5:
                items.append(line)
        
        # 如果提取到多个项目，认为是列表
        if len(items) >= 2:
            # 根据工具名称进行特定解析
            if tool_name:
                parsed_items = ToolOutputParser._parse_tool_specific_list(tool_name, items)
                if parsed_items:
                    items = parsed_items
            
            return {
                "type": "list",
                "structured_data": items,
                "summary": f"List with {len(items)} items",
                "key_fields": {
                    "count": len(items),
                    "items": items[:20],  # 只保留前20项
                    "total": len(items)
                }
            }
        
        return None
    
    @staticmethod
    def _parse_tool_specific_list(tool_name: str, items: List[str]) -> Optional[List[Dict[str, Any]]]:
        """根据工具名称进行特定解析"""
        # VS Code扩展列表
        if "list_extensions" in tool_name or "extension" in tool_name.lower():
            parsed = []
            for item in items:
                # 格式通常是：ExtensionName (publisher.name) - version
                match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*-\s*(.+)$', item)
                if match:
                    parsed.append({
                        "name": match.group(1).strip(),
                        "id": match.group(2).strip(),
                        "version": match.group(3).strip()
                    })
                else:
                    parsed.append({"name": item, "raw": item})
            return parsed if parsed else None
        
        # 文件列表
        if "list" in tool_name.lower() and "file" in tool_name.lower():
            parsed = []
            for item in items:
                # 尝试解析文件路径和元数据
                parsed.append({
                    "path": item,
                    "name": item.split('/')[-1] if '/' in item else item.split('\\')[-1]
                })
            return parsed
        
        return None
    
    @staticmethod
    def _try_extract_structured(content: str, tool_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """尝试提取结构化信息（键值对、表格等）"""
        # 提取键值对
        kv_pattern = r'([^:\n]+):\s*(.+)'
        kv_matches = re.findall(kv_pattern, content)
        
        if len(kv_matches) >= 2:
            key_fields = {k.strip(): v.strip() for k, v in kv_matches}
            return {
                "type": "key_value",
                "structured_data": key_fields,
                "summary": f"Key-value pairs ({len(key_fields)} keys)",
                "key_fields": key_fields
            }
        
        return None
    
    @staticmethod
    def _parse_dict(data: Dict[str, Any], tool_name: Optional[str] = None) -> Dict[str, Any]:
        """解析字典数据"""
        key_fields = ToolOutputParser._extract_key_fields_from_dict(data)
        
        return {
            "type": "dict",
            "structured_data": data,
            "summary": f"Dictionary with {len(data)} keys",
            "key_fields": key_fields
        }
    
    @staticmethod
    def _parse_list(data: List[Any], tool_name: Optional[str] = None) -> Dict[str, Any]:
        """解析列表数据"""
        return {
            "type": "list",
            "structured_data": data,
            "summary": f"List with {len(data)} items",
            "key_fields": {
                "count": len(data),
                "items": data[:20],  # 只保留前20项
                "total": len(data)
            }
        }
    
    @staticmethod
    def _extract_key_fields_from_dict(data: Dict[str, Any], max_depth: int = 2) -> Dict[str, Any]:
        """从字典中提取关键字段"""
        key_fields = {}
        
        # 常见的关键字段名
        important_keys = [
            "id", "name", "path", "file_path", "url", "status", "success",
            "result", "data", "content", "message", "error", "count", "total"
        ]
        
        for key, value in data.items():
            # 提取重要字段
            if key.lower() in [k.lower() for k in important_keys]:
                if isinstance(value, (str, int, float, bool)):
                    key_fields[key] = value
                elif isinstance(value, dict) and max_depth > 0:
                    key_fields[key] = ToolOutputParser._extract_key_fields_from_dict(value, max_depth - 1)
                elif isinstance(value, list) and len(value) > 0:
                    # 只保留列表的第一个元素作为示例
                    key_fields[key] = value[0] if len(value) == 1 else f"{len(value)} items"
            
            # 限制提取的字段数量
            if len(key_fields) >= 10:
                break
        
        return key_fields

