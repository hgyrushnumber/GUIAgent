"""Local model client abstractions for MVP."""
from __future__ import annotations

import json
from typing import Protocol
from urllib import request


class LocalModelClient(Protocol):
    def generate(self, prompt: str, max_tokens: int = 128) -> str:
        ...


class OpenAICompatibleLocalClient:
    """Local endpoint client. Expects OpenAI-compatible /chat/completions."""

    def __init__(self, base_url: str, model: str, timeout_s: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def generate(self, prompt: str, max_tokens: int = 128) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


class DummyLocalClient:
    """Deterministic fallback for demo/testing."""

    def generate(self, prompt: str, max_tokens: int = 128) -> str:
        _ = max_tokens
        if "TYPE" in prompt:
            return json.dumps({"pick": "TYPE"})
        return json.dumps({"pick": "CLICK"})
