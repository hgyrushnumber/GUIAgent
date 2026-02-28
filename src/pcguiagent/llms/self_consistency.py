import json


class SelfConsistencyEngine:
    """
    多次调用 LLM → 选择格式最正确 + 最一致的那个
    """

    def __init__(self, llm, samples: int = 3):
        self.llm = llm
        self.samples = samples

    async def consistent_complete(self, prompt: str) -> str:
        results = []

        for _ in range(self.samples):
            out = await self.llm.acomplete(prompt)
            try:
                data = json.loads(out)
                results.append((True, out))
            except:
                results.append((False, out))

        # 优先选 JSON 解析成功者
        valid = [o for ok, o in results if ok]
        if valid:
            return valid[0]

        # 否则取第一条
        return results[0][1]
