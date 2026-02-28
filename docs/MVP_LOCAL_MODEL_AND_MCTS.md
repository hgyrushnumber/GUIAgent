# MVP: Local Model Connection + MCTS Placement

## 1) 本地模型接口（已接入）
在 `llm.provider=local` 时，系统将使用 `LocalModelClient` 连接 OpenAI-compatible 本地服务（如 Ollama/vLLM）。

- 实现位置：`src/pcguiagent/llms/local_model_client.py`
- 初始化入口：`Bootstrap._build_llm()`
- 推荐 base_url：
  - Ollama: `http://127.0.0.1:11434/v1`
  - vLLM: `http://127.0.0.1:8000/v1`

配置示例：

```yaml
llm:
  provider: local
  model: qwen2.5
  api_key: null
  base_url: http://127.0.0.1:11434/v1
  temperature: 0.2
  max_tokens: 2048
```

## 2) 最小化 MVP 测试
本次补充了两个最小测试：

1. `tests/test_local_model_client.py`
   - mock 本地接口响应，验证 `LocalModelClient.acomplete()` 能正确解析内容。
2. `tests/test_llm_factory_local_provider.py`
   - 用最小 `LLMConfig` 验证 `provider=local` 时会实例化 `LocalModelClient`。

运行方式：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## 3) MCTS 策略应放在哪里
建议放在 `planners/` 层，而不是 `agent.py`：

- `agent.py`：只保留 orchestration（接 observation -> 调 planner -> 返回 action）
- `roles/planner_role.py`：只负责调用 planner，不实现算法细节
- `planners/`：放 `mcts_planner.py`（或 `rl_mcts_planner.py`）
  - 输入：goal + observation + history + memory_context
  - 输出：与 `RecursivePlanner.next_action()` 兼容的 action JSON

这样可以直接做公平 ablation：
- `RecursivePlanner`（baseline）
- `MCTSPlanner`（搜索）
- `RLMCTSPlanner`（论文主方法）

并在 `Bootstrap._build_llm()` / planner 构建阶段按配置切换实现。
