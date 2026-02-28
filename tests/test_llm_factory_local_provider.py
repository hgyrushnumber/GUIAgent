import unittest

from pcguiagent.core.config import LLMConfig
from pcguiagent.llms.factory import build_llm_client
from pcguiagent.llms.local_model_client import LocalModelClient


class TestLLMFactoryLocalProvider(unittest.TestCase):
    def test_build_local_llm_client(self):
        llm_cfg = LLMConfig(
            provider="local",
            model="qwen2.5",
            api_key=None,
            base_url="http://127.0.0.1:11434/v1",
            temperature=0.1,
            max_tokens=128,
        )

        client = build_llm_client(llm_cfg)

        self.assertIsInstance(client, LocalModelClient)
        self.assertEqual(client.base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(client.model, "qwen2.5")


if __name__ == "__main__":
    unittest.main()
