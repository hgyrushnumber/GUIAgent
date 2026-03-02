# OSWorld 单任务最小化 MVP 计划（本地模型版）

## 1) 目标与边界

### 目标
在本地模型驱动下，跑通 **1 个固定 OSWorld 任务**：

- `在浏览器中打开百度并搜索 Python`

### 非目标（本次不做）

- 不做多任务泛化。
- 不做训练/蒸馏。
- 不做 shallow search。
- 不做视觉检测 fallback（仅依赖 a11y/DOM）。

---

## 2) 成功标准（DoD）

满足全部：

1. 连续运行 10 次，成功次数 >= 7。
2. 平均步数 <= 15。
3. 单步决策延迟 P95 <= 2.5s（不含环境等待）。
4. 每一步有可追踪日志（可复盘失败原因）。

---

## 3) 最小架构

```
OSWorld.observe
  -> UIParser.parse
  -> StageManager.update
  -> GroundingRanker.rank(top_k=5)
  -> ActionComposer.compose(max_actions=8)
  -> LocalModelPolicy.select_one
  -> env.step
  -> TrajectoryLogger.append
```

---

## 4) 模块最小接口（MVP）

## 4.1 UIParser

```python
class UIParser:
    def parse(self, observation: dict) -> dict:
        """return {'elements': [...], 'window_meta': {...}, 'raw_a11y': str}"""
```

实现要点：
- 从 a11y tree 提取 `element_id/role/text/clickable/editable/enabled`。
- 过滤不可交互噪声节点。

## 4.2 StageManager（固定子目标）

```python
class StageManager:
    def init(self) -> dict: ...
    def update(self, state: dict, obs: dict, last_action: dict, info: dict) -> dict: ...
```

固定子目标：
1. 聚焦地址栏；
2. 输入 baidu URL 并回车；
3. 聚焦搜索框输入 Python；
4. 提交搜索并等待结果。

## 4.3 GroundingRanker（规则 + 本地模型轻打分）

```python
class GroundingRanker:
    def rank(self, elements: list, subgoal: str, top_k: int = 5) -> list:
        """return [{'element_id':..., 'score':...}, ...]"""
```

打分策略：
- 规则分：role 匹配 + text 关键词命中；
- 本地模型分：对 top-N 元素做一次轻量 rerank（可选）。

## 4.4 ActionComposer

```python
class ActionComposer:
    def compose(self, ranked: list, subgoal: str) -> list:
        """return action candidates <= 8"""
```

动作集合：
- CLICK: top-5 clickable
- TYPE: top-2 editable（每个仅 1 个文本）
- WAIT: 1 个

## 4.5 LocalModelPolicy

```python
class LocalModelPolicy:
    def select_one(self, candidates: list, subgoal: str, obs_summary: str) -> dict:
        """return one action"""
```

要求：
- 支持本地 endpoint（OpenAI-compatible）优先。
- 若模型超时/失败，回退到规则优先动作。

## 4.6 TrajectoryLogger

```python
class TrajectoryLogger:
    def append(self, record: dict) -> None: ...
```

每步必记：
- `step, subgoal, topk_elements, candidates, chosen_action, done, success_signal, latency_ms`

---

## 5) 执行策略（单任务专用）

### 成功信号
任意满足：
- 窗口为浏览器；
- URL/文本出现 `baidu`；
- 结果页出现 `Python` 相关关键词。

### fail-fast
任意满足即提前失败：
- 步数 > 20；
- 连续 3 步 UI 无明显变化；
- 连续 2 次动作执行报错。

---

## 6) 三天实施排期

### Day 1
- 接入 `LocalModelPolicy`（本地 endpoint）。
- 完成 `UIParser` + `StageManager`。
- 能从 observation 产出候选动作。

### Day 2
- 完成 `GroundingRanker` + `ActionComposer`。
- 跑通 1 次 end-to-end episode。
- 加入超时回退逻辑（模型失败 -> 规则动作）。

### Day 3
- 加 `TrajectoryLogger`。
- 连跑 10 次，输出成功率/步数/延迟。
- 调整 3 个阈值（top_k、max_steps、无变化判定）。

---

## 7) 交付物

1. `mvp_runner.py`（或等价入口）
2. `mvp_modules/` 下 6 个最小模块实现
3. `logs/mvp_single_task_*.jsonl`
4. `reports/mvp_result.md`（10 次统计 + 失败复盘）

---

## 8) 验收清单（Checklist）

- [ ] 可读取 OSWorld observation 并解析出元素。
- [ ] 能输出最多 8 个候选动作。
- [ ] 本地模型不可用时可自动回退。
- [ ] 单任务可完成且满足 DoD 指标。
- [ ] 日志可复盘每步选择依据。

