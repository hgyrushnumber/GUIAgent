from pcguiagent.core.config import LLMConfig
from pcguiagent.llms.base_client import BaseLLMClient


def build_llm_client(llm_config: LLMConfig) -> BaseLLMClient:
    provider = llm_config.provider

    if provider == "deepseek":
        from pcguiagent.llms.deepseek_client import DeepSeekClient

        return DeepSeekClient(
            api_key=llm_config.api_key,
            model=llm_config.model,
            base_url=llm_config.base_url or "https://api.deepseek.com/v1",
        )

    if provider == "local":
        from pcguiagent.llms.local_model_client import LocalModelClient

        return LocalModelClient(
            model=llm_config.model,
            base_url=llm_config.base_url or "http://127.0.0.1:11434/v1",
            api_key=llm_config.api_key,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
        )

    from pcguiagent.llms.openai_client import OpenAIClient

    return OpenAIClient(
        api_key=llm_config.api_key,
        model=llm_config.model,
        base_url=llm_config.base_url,
    )
