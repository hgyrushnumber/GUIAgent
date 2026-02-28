from pcguiagent.utils.logger import configure_global_logging, get_logger
from pcguiagent.utils.errors import (
    AgentError,
    ToolExecutionError,
    LLMOutputError,
    PlanningError,
)

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
    "AliyunOCRClient",
    "create_ocr_client",
]


def __getattr__(name):
    if name == "get_system_info":
        from pcguiagent.utils.system_info import get_system_info
        return get_system_info
    if name == "find_config_file":
        from pcguiagent.utils.config_loader import find_config_file
        return find_config_file
    if name == "ActionExtractor":
        from pcguiagent.utils.action_extractor import ActionExtractor
        return ActionExtractor
    if name == "A11yTreePreprocessor":
        from pcguiagent.utils.a11y_preprocessor import A11yTreePreprocessor
        return A11yTreePreprocessor
    if name in {"AliyunOCRClient", "create_ocr_client"}:
        from pcguiagent.utils.ocr_client import AliyunOCRClient, create_ocr_client
        return {"AliyunOCRClient": AliyunOCRClient, "create_ocr_client": create_ocr_client}[name]
    raise AttributeError(f"module 'pcguiagent.utils' has no attribute {name!r}")
