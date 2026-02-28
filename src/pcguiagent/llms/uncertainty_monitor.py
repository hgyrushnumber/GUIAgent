class UncertaintyMonitor:
    """
    判断 LLM 输出是否不稳定：例如包含：
    - 多个 JSON
    - JSON 前后有自然语言
    - 认为自己不确定
    
    可用于触发 retry 或 repair
    """

    @staticmethod
    def is_uncertain(text: str) -> bool:
        # 简单启发式检测
        lower = text.lower()
        if "i am not sure" in lower:
            return True
        if "maybe" in lower:
            return True
        if text.count("{") > 1:   # 多个 JSON → 不确定
            return True
        if not text.strip().startswith("{"):
            return True
        if not text.strip().endswith("}"):
            return True

        return False
