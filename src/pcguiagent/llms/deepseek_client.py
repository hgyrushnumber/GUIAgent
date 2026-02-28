from typing import Optional
import httpx
import time

from pcguiagent.llms.base_client import BaseLLMClient
from pcguiagent.utils.logger import get_logger

logger = get_logger("DeepSeekClient")

# Try to import tenacity for retry mechanism, fallback if not available
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False
    logger.warning("[DeepSeekClient] tenacity not available, retry mechanism disabled. Install with: pip install tenacity")

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.
    Simple estimation: ~4 characters per token for English/Chinese mixed text.
    """
    return len(text) // 4

class DeepSeekClient(BaseLLMClient):

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.deepseek.com/v1", timeout: float = 180.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def _acomplete_with_retry(self, prompt: str) -> str:
        """Internal method that can be wrapped with retry decorator"""
        start_time = time.time()
        prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        prompt_chars = len(prompt)
        estimated_tokens = estimate_tokens(prompt)
        
        logger.info(f"[DeepSeek] Sending request to {self.base_url}")
        logger.info(f"[DeepSeek] Model: {self.model}, Timeout: {self.timeout}s")
        logger.info(f"[DeepSeek] Prompt stats: {prompt_chars} chars, ~{estimated_tokens} tokens")
        logger.debug(f"[DeepSeek] Prompt preview: {prompt_preview}")
        # Log full prompt (DEBUG level to avoid log file bloat)
        logger.debug(f"[DeepSeek] ===== LLM INPUT (PROMPT) =====")
        logger.debug(f"[DeepSeek] Full prompt:\n{prompt}")
        logger.debug(f"[DeepSeek] ===== END LLM INPUT =====")
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt},
            ]
        }
        headers = {"Authorization": f"Bearer {self.api_key[:10]}..."}  # Log partial key for security

        logger.debug(f"[DeepSeek] Request payload size: {len(str(payload))} chars")
        resp = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout
        )
        elapsed = time.time() - start_time
        elapsed_ms = elapsed * 1000
        logger.info(f"[DeepSeek] Response received in {elapsed:.2f}s, status: {resp.status_code}")
        
        if resp.status_code != 200:
            logger.error(f"[DeepSeek] Error response: {resp.status_code} - {resp.text[:500]}")
            resp.raise_for_status()
        
        data = resp.json()
        response_text = data["choices"][0]["message"]["content"]
        response_chars = len(response_text)
        response_preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
        logger.debug(f"[DeepSeek] Response preview: {response_preview}")
        logger.info(f"[DeepSeek] Response received: {response_chars} chars, latency: {elapsed_ms:.2f}ms")
        # Log full response (DEBUG level to avoid log file bloat)
        logger.debug(f"[DeepSeek] ===== LLM OUTPUT (RESPONSE) =====")
        logger.debug(f"[DeepSeek] Full response:\n{response_text}")
        logger.debug(f"[DeepSeek] ===== END LLM OUTPUT =====")
        return response_text

    async def acomplete(self, prompt: str) -> str:
        """Complete with retry mechanism if tenacity is available"""
        if HAS_TENACITY:
            # Use retry decorator with proper exception handling
            # Retry on network errors and timeouts
            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type((httpx.TimeoutException, httpx.RequestError)),
                reraise=True
            )
            async def _retry_wrapper():
                return await self._acomplete_with_retry(prompt)
            
            try:
                return await _retry_wrapper()
            except (httpx.TimeoutException, httpx.RequestError) as e:
                logger.error(f"[DeepSeek] Request failed after all retries: {type(e).__name__}: {str(e)}")
                raise
            except Exception as e:
                # Non-retryable errors (like HTTP 4xx, 5xx) are raised immediately
                logger.error(f"[DeepSeek] Request failed: {type(e).__name__}: {str(e)}")
                raise
        else:
            # Fallback to implementation without retry
            return await self._acomplete_with_retry(prompt)

    async def aclose(self):
        await self.client.aclose()
