import asyncio
import json
from typing import Optional
from urllib import request, error

from pcguiagent.llms.base_client import BaseLLMClient
from pcguiagent.utils.logger import get_logger

logger = get_logger("LocalModelClient")


class LocalModelClient(BaseLLMClient):
    """OpenAI-compatible local model client (vLLM/Ollama/TGI)."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434/v1",
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: float = 120.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    async def acomplete(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        return await asyncio.to_thread(self._post_chat_completion, payload)

    def _post_chat_completion(self, payload: dict) -> str:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            logger.error("[LocalModelClient] Local model error %s: %s", e.code, detail[:500])
            raise

        return data["choices"][0]["message"]["content"]

    async def aclose(self):
        return None
