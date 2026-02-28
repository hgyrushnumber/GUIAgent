import asyncio
from typing import Optional

from openai import AsyncOpenAI

from pcguiagent.llms.base_client import BaseLLMClient
from pcguiagent.utils.logger import get_logger

logger = get_logger("OpenAIClient")

class OpenAIClient(BaseLLMClient):

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def acomplete(self, prompt: str) -> str:
        import time
        start_time = time.time()
        prompt_chars = len(prompt)
        
        logger.info(f"[OpenAI] Sending request to {self.model}")
        logger.info(f"[OpenAI] Prompt stats: {prompt_chars} chars")
        logger.info(f"[OpenAI] ===== LLM INPUT (PROMPT) =====")
        logger.info(f"[OpenAI] Full prompt:\n{prompt}")
        logger.info(f"[OpenAI] ===== END LLM INPUT =====")
        
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        
        elapsed = time.time() - start_time
        response_text = resp.choices[0].message.content
        response_chars = len(response_text)
        
        logger.info(f"[OpenAI] Response received: {response_chars} chars, latency: {elapsed*1000:.2f}ms")
        logger.info(f"[OpenAI] ===== LLM OUTPUT (RESPONSE) =====")
        logger.info(f"[OpenAI] Full response:\n{response_text}")
        logger.info(f"[OpenAI] ===== END LLM OUTPUT =====")
        
        return response_text

    async def aclose(self):
        await asyncio.sleep(0)  # placeholder
