"""
阿里云 OCR 客户端

封装阿里云 OCR API 调用，从 screenshot 中提取文本和坐标信息。
"""

import os
import tempfile
from typing import Dict, Optional, Any
from io import BytesIO

from pcguiagent.utils.logger import get_logger

logger = get_logger("OCRClient")

try:
    from alibabacloud_ocr_api20210707.client import Client as OCRClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_ocr_api20210707 import models as ocr_models
    from alibabacloud_tea_util import models as util_models
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("阿里云 OCR SDK 未安装，OCR 功能将不可用")


class AliyunOCRClient:
    """
    阿里云 OCR 客户端封装
    """
    
    def __init__(
        self,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        endpoint: str = "ocr-api.cn-hangzhou.aliyuncs.com"
    ):
        """
        初始化阿里云 OCR 客户端
        
        Args:
            access_key_id: 阿里云 AccessKey ID（从环境变量 ALIYUN_ACCESS_KEY_ID 读取）
            access_key_secret: 阿里云 AccessKey Secret（从环境变量 ALIYUN_ACCESS_KEY_SECRET 读取）
            endpoint: OCR API 端点
        """
        if not OCR_AVAILABLE:
            raise RuntimeError("阿里云 OCR SDK 未安装，请安装: pip install alibabacloud-ocr-api20210707 alibabacloud-tea-openapi alibabacloud-tea-util")
        
        # 从参数或环境变量读取凭证
        self.access_key_id = access_key_id or os.getenv("ALIYUN_ACCESS_KEY_ID")
        self.access_key_secret = access_key_secret or os.getenv("ALIYUN_ACCESS_KEY_SECRET")
        self.endpoint = endpoint
        
        if not self.access_key_id or not self.access_key_secret:
            raise RuntimeError("缺少阿里云 AccessKey，请设置环境变量 ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET")
        
        # 创建 OCR 客户端
        self._client = None
        self._create_client()
    
    def _create_client(self):
        """创建 OCR 客户端"""
        try:
            config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret
            )
            config.endpoint = self.endpoint
            self._client = OCRClient(config)
            logger.info(f"[AliyunOCRClient] OCR 客户端初始化成功 (endpoint: {self.endpoint})")
        except Exception as e:
            logger.error(f"[AliyunOCRClient] 创建 OCR 客户端失败: {e}")
            raise
    
    def recognize(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        调用阿里云 OCR API 识别图片中的文本和坐标
        
        Args:
            image_bytes: 图片字节数据（PNG/JPEG 格式）
        
        Returns:
            OCR 结果字典，包含：
            - content: 识别的文本内容
            - words: 词列表，每个词包含 text, x, y, width, height, center_x, center_y
            如果失败返回 None
        """
        if not self._client:
            logger.error("[AliyunOCRClient] OCR 客户端未初始化")
            return None
        
        try:
            # 创建请求
            request = ocr_models.RecognizeAdvancedRequest()
            request.body = image_bytes
            
            runtime = util_models.RuntimeOptions()
            
            # 调用 API
            logger.info(f"[AliyunOCRClient] 调用 OCR API，图片大小: {len(image_bytes)} bytes")
            resp = self._client.recognize_advanced_with_options(request, runtime)
            
            if not resp or not resp.body:
                logger.warning("[AliyunOCRClient] OCR API 返回空结果")
                return None
            
            # 解析结果
            result = self._parse_ocr_result(resp.body)
            logger.info(f"[AliyunOCRClient] OCR 识别成功，识别到 {len(result.get('words', []))} 个词")
            return result
            
        except Exception as e:
            logger.error(f"[AliyunOCRClient] OCR 识别失败: {e}", exc_info=True)
            return None
    
    def _parse_ocr_result(self, ocr_body: Any) -> Dict[str, Any]:
        """
        解析 OCR API 返回的结果
        
        Args:
            ocr_body: OCR API 返回的 body 对象
        
        Returns:
            格式化的结果字典
        """
        result = {
            "content": "",
            "words": []
        }
        
        try:
            # 获取识别的文本内容
            if hasattr(ocr_body, 'data') and hasattr(ocr_body.data, 'content'):
                result["content"] = ocr_body.data.content or ""
            
            # 获取词级别信息
            if hasattr(ocr_body, 'data') and hasattr(ocr_body.data, 'prism_words_info'):
                words_info = ocr_body.data.prism_words_info
                if words_info:
                    for word_info in words_info:
                        word_data = {
                            "text": "",
                            "x": 0,
                            "y": 0,
                            "width": 0,
                            "height": 0,
                            "center_x": 0,
                            "center_y": 0
                        }
                        
                        if hasattr(word_info, 'word'):
                            word_data["text"] = word_info.word or ""
                        
                        if hasattr(word_info, 'x'):
                            word_data["x"] = int(word_info.x) if word_info.x is not None else 0
                        
                        if hasattr(word_info, 'y'):
                            word_data["y"] = int(word_info.y) if word_info.y is not None else 0
                        
                        if hasattr(word_info, 'width'):
                            word_data["width"] = int(word_info.width) if word_info.width is not None else 0
                        
                        if hasattr(word_info, 'height'):
                            word_data["height"] = int(word_info.height) if word_info.height is not None else 0
                        
                        # 计算中心点
                        if word_data["width"] > 0 and word_data["height"] > 0:
                            word_data["center_x"] = word_data["x"] + word_data["width"] // 2
                            word_data["center_y"] = word_data["y"] + word_data["height"] // 2
                        
                        if word_data["text"]:  # 只添加有文本的词
                            result["words"].append(word_data)
            
        except Exception as e:
            logger.warning(f"[AliyunOCRClient] 解析 OCR 结果时出错: {e}")
        
        return result
    
    def format_ocr_result(self, ocr_result: Optional[Dict[str, Any]]) -> str:
        """
        格式化 OCR 结果为文本字符串，用于传递给 LLM
        
        Args:
            ocr_result: OCR 识别结果
        
        Returns:
            格式化的文本字符串
        """
        if not ocr_result:
            return ""
        
        lines = ["# OCR Results (Text and Coordinates)"]
        
        # 添加完整文本内容
        if ocr_result.get("content"):
            lines.append(f"Full text: {ocr_result['content']}")
            lines.append("")
        
        # 添加词级别信息（包含坐标）
        words = ocr_result.get("words", [])
        if words:
            lines.append("Words with coordinates:")
            for word in words:
                text = word.get("text", "")
                x = word.get("x", 0)
                y = word.get("y", 0)
                width = word.get("width", 0)
                height = word.get("height", 0)
                center_x = word.get("center_x", 0)
                center_y = word.get("center_y", 0)
                
                lines.append(
                    f'  - "{text}" at ({x}, {y}) size ({width}, {height}) center: ({center_x}, {center_y})'
                )
        else:
            lines.append("No words detected")
        
        return "\n".join(lines)


def create_ocr_client(
    access_key_id: Optional[str] = None,
    access_key_secret: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Optional[AliyunOCRClient]:
    """
    创建 OCR 客户端（工厂函数）
    
    Args:
        access_key_id: 阿里云 AccessKey ID
        access_key_secret: 阿里云 AccessKey Secret
        endpoint: OCR API 端点
    
    Returns:
        OCR 客户端实例，如果创建失败返回 None
    """
    if not OCR_AVAILABLE:
        logger.warning("[create_ocr_client] OCR SDK 未安装，无法创建 OCR 客户端")
        return None
    
    try:
        client = AliyunOCRClient(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint or "ocr-api.cn-hangzhou.aliyuncs.com"
        )
        return client
    except Exception as e:
        logger.error(f"[create_ocr_client] 创建 OCR 客户端失败: {e}")
        return None

