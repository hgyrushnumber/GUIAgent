import abc
from typing import Any


class BaseLLMClient(abc.ABC):
    """
    所有 LLM 客户端需要统一实现的异步接口
    """

    @abc.abstractmethod
    async def acomplete(self, prompt: str) -> str:
        """
        异步生成文本，返回完整字符串
        """
        raise NotImplementedError()

    async def aclose(self):
        """
        可覆盖，用于关闭连接等
        """
        pass
