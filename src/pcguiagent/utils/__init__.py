from pcguiagent.utils.logger import configure_global_logging, get_logger
from pcguiagent.utils.errors import (
    AgentError,
    ToolExecutionError,
    LLMOutputError,
    PlanningError
)
from pcguiagent.utils.system_info import get_system_info
from pcguiagent.utils.config_loader import find_config_file
from pcguiagent.utils.action_extractor import ActionExtractor
from pcguiagent.utils.a11y_preprocessor import A11yTreePreprocessor

# OCR client (optional, only if alibabacloud SDK is installed)
try:
    from pcguiagent.utils.ocr_client import AliyunOCRClient, create_ocr_client
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    AliyunOCRClient = None
    create_ocr_client = None

__all__ = [
    "configure_global_logging",
    "get_logger",
    "AgentError",
    "ToolExecutionError",
    "LLMOutputError",
    "PlanningError",
    "get_system_info",
    "find_config_file",
    "ActionExtractor",
    "A11yTreePreprocessor",
]

if OCR_AVAILABLE:
    __all__.extend(["AliyunOCRClient", "create_ocr_client"])
