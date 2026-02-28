import unittest
from unittest.mock import patch

from pcguiagent.llms.local_model_client import LocalModelClient


class TestLocalModelClient(unittest.IsolatedAsyncioTestCase):
    async def test_acomplete_success(self):
        client = LocalModelClient(model="qwen2.5", base_url="http://localhost:11434/v1")

        with patch.object(client, "_post_chat_completion", return_value="CLICK 100 100") as mock_post:
            result = await client.acomplete("test prompt")

        self.assertEqual(result, "CLICK 100 100")
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
