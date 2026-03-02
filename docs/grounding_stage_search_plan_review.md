# Grounding + Stage + Shallow Search 方案评审与优化计划（高风险点修复版）

## 1. 结论（是否正确）

你的原始方案方向是正确的，且具备工程可落地性：

- 数据流闭环完整（在线执行 + 离线训练）。
- 模块边界清晰（解析/阶段/grounding/动作/搜索）。
- 训练路线合理（listwise + hard negative + 可选蒸馏）。

但要进入稳定工程化，必须先修掉 5 个高风险点：

1. `UIState` 大对象导致存储与训练 IO 负担。
2. `StepRecord` 重复内嵌状态导致数据冗余。
3. `Action` 与 OSWorld 字符串缺少双向契约。
4. `StageManager` 缺少置信度和回退，易误推进。
5. `ShallowSearch` reset/replay 成本高，易拖慢吞吐。

---

## 2. 与当前仓库的对齐约束

当前仓库主链路是“OSWorld observation -> 规划 -> pyautogui 字符串动作”，且已经有动作 schema 及校验模块。新方案应遵循：

1. **旁路接入、渐进替换**：先不破坏现有 `PCGuiAgent` 主流程。
2. **优先复用动作 schema**：避免定义平行 `Action` 体系。
3. **类型先行**：在 `core/types` 级别先冻结契约，再接模型。

---

## 3. 修复高风险点后的优化 Plan（可直接拆任务）

> 目标：先“可运行 + 可观测 + 可回放”，再“可训练 + 可提效”。

### Phase A（接口修复，1~2 天）

#### A1. 修复风险 #1/#2：状态与轨迹去重

- 引入分层状态：
  - `UIStateLive`: 在线使用，包含 `screenshot_rgb/dom_raw/elements`。
  - `UIStateLite`: 持久化使用，仅保留 `elements + refs + digest`。
- 重构轨迹记录：
  - `StepRecordLite` 只存 `ui_state_ref/screenshot_ref/dom_ref`。
  - 新增 `StateStore`（按 hash 去重落盘）。

**接口建议**

```python
class StateStore(Protocol):
    def put_ui_state(self, state_live: UIStateLive) -> str: ...  # return ui_state_ref
    def get_ui_state(self, ref: str) -> UIStateLive: ...
```

**验收**

- 连续记录 1000 step 无 OOM。
- 同一帧重复写入命中去重（hash 命中率可观测）。

#### A2. 修复风险 #3：动作双向契约

- 新增 `ActionAdapter` 作为唯一边界：
  - `from_osworld_str()`：字符串 -> 结构化 Action。
  - `to_osworld_str()`：结构化 Action -> 字符串。
- 与现有 action schema validator 集成：适配前后都验证。

**接口建议**

```python
class ActionAdapter:
    def from_osworld_str(self, raw: str) -> Action: ...
    def to_osworld_str(self, action: Action) -> str: ...
```

**验收**

- round-trip 一致性：`s -> a -> s2` 语义一致。
- 非法动作能被明确拒绝并返回可观测错误码。

---

### Phase B（阶段稳定性修复，2~3 天）

#### B1. 修复风险 #4：子目标推进防抖

- 在 `StageState` 中加入：
  - `current_subgoal_confidence`
  - `evidence`（触发推进的观测证据）
  - `rollback_count`
- 推进规则：
  - 仅当 `confidence >= τ_up` 且连续 `k` 步满足才推进。
  - 若后续 `confidence <= τ_down`，允许一次回退（防误判）。

**接口建议**

```python
class StageManager:
    def update(...)-> StageState:
        # return with confidence/evidence
        ...
```

**默认参数**

- `τ_up=0.8`, `τ_down=0.4`, `k=2`, `max_rollback=1`

**验收**

- 回放样例中，误推进率下降。
- 每次推进都能在日志中看到 evidence。

---

### Phase C（搜索吞吐修复，2~3 天）

#### C1. 修复风险 #5：浅层搜索预算化

- 引入 `SearchBudget`：
  - `max_expansions`
  - `max_ms`
  - `per_action_timeout_ms`
- `ShallowSearch` 默认“保守模式”：
  - `depth=1`
  - 仅评估 top-N（如 5）
  - 超时立即降级为 ranker top-1
- replay 优化：
  - 支持 `root_token` 快照优先；无快照时启用 action replay cache。

**接口建议**

```python
@dataclass
class SearchBudget:
    max_expansions: int = 8
    max_ms: int = 800
    per_action_timeout_ms: int = 120
```

**验收**

- 在线 P95 时延可控（不含大模型推理）。
- 打开搜索后吞吐下降在可接受范围内。

---

### Phase D（模型增强，5~7 天）

- GroundingRanker 从 rule baseline 切换到可训练模型。
- 训练阶段先用 explicit subgoal 文本拼接 query。
- 加入蒸馏前置门槛：仅高置信 search 轨迹参与。

**离线指标**

- `acc@1/acc@5/MRR`
- 分 role（button/input/menuitem）统计。
- 分 stage 统计（early/mid/late）。

---

## 4. 高风险点 -> 修复动作映射表（执行用）

| 高风险点 | 根因 | 修复动作 | 负责人建议 |
|---|---|---|---|
| UIState 体量大 | 原图+DOM 全量内嵌 | `UIStateLive/UIStateLite` 分层 + `StateStore` | 平台/数据 |
| StepRecord 冗余 | 每步重复存同类信息 | `StepRecordLite` 引用化 + hash 去重 | 数据 |
| Action 无契约 | 字符串和结构化不一致 | `ActionAdapter` + validator 前后置 | 平台 |
| Stage 误推进 | 仅规则、无置信度防抖 | `confidence + evidence + rollback` | 算法 |
| Search 吞吐差 | reset/replay 成本高 | `SearchBudget` + 超时降级 + replay cache | 平台/算法 |

---

## 5. 最小可交付里程碑（修复版）

- **M1（第 1 周）**：A+B 完成（接口修复 + 阶段防抖）。
- **M2（第 2 周）**：C 完成（预算化浅层搜索 + 降级策略）。
- **M3（第 3 周）**：D 第一版（可训练 ranker + 离线评估）。

每个里程碑必须带：

1. 一页延迟/吞吐报表；
2. 一页 grounding 错误类型分布；
3. 10 条失败案例可视化（bbox + rank + action）。

---

## 6. 你可以直接开工的任务拆分（Issue 模板）

1. 定义 `UIStateLive/UIStateLite/StepRecordLite` 类型与序列化协议。
2. 实现 `StateStore`（hash 去重 + 引用读取）。
3. 实现 `ActionAdapter` 与 round-trip 测试。
4. 在 `StageManager` 增加 confidence/evidence/rollback。
5. 在 `ShallowSearch` 接入 `SearchBudget` 与超时降级。
6. 增加统一日志字段（rank top-k / stage evidence / evaluator 分解分）。
7. 跑 1000-step 压测与 50-task 小规模离线评估。

> 如果你希望，我下一步可以直接给出 **M1 的代码骨架文件树 + 每个文件的最小可运行 stub**，你照着填实现即可。

---

## 7. 当前目标：仅用本地模型跑通 1 个 OSWorld 任务（最小化 MVP）

> 范围收敛：**只追求“能稳定完成 1 个固定任务”**，先不追求泛化、多任务、训练闭环。

### 7.1 MVP 成功标准（Definition of Done）

选择一个固定任务（建议难度低）：

- `在浏览器中打开百度并搜索 Python`。

判定成功（满足任一可观测信号组合）：

1. active window/app 为浏览器；
2. URL 或页面文本出现 `baidu`；
3. 页面出现关键词 `Python` 搜索结果相关文本。

通过标准：

- 同一环境下连续跑 10 次，成功 >= 7 次；
- 平均步数 <= 15；
- 单步决策延迟 P95 <= 2.5s（不含环境渲染等待）。

### 7.2 MVP 最小模块集（只保留必要件）

只实现以下组件，其他全部延后：

1. `UIParser`（a11y tree -> elements）
2. `StageManager`（explicit，最多 4 个子目标）
3. `GroundingRanker`（本地模型/规则混合打分，top-k=5）
4. `ActionComposer`（CLICK/TYPE/WAIT 三类）
5. `LocalModelPolicy`（调用本地模型生成 text/type 候选与 tie-break）
6. `TrajectoryLogger`（jsonl 记录关键字段）

**不做项（明确砍掉）**

- 不做 ShallowSearch；
- 不做训练与蒸馏；
- 不做视觉检测 fallback；
- 不做多任务 benchmark。

### 7.3 本地模型接入策略（MVP 版）

目标是“本地可跑”，不绑定特定厂商：

- 提供统一接口：

```python
class LocalModelClient(Protocol):
    def generate(self, prompt: str, max_tokens: int = 256) -> str: ...
```

- 默认支持两种后端（二选一即可）：
  - `transformers` 本地权重推理；
  - 本地推理服务（OpenAI-compatible endpoint）。

MVP 推荐：优先用“本地 endpoint”方式，减少工程复杂度。

### 7.4 单任务执行流程（MVP）

```
observe -> UIParser
        -> StageManager(current_subgoal)
        -> GroundingRanker(top-5)
        -> ActionComposer(候选动作)
        -> LocalModelPolicy(选1个动作)
        -> env.step
```

终止条件：

- 成功信号命中；或
- 步数达到上限（如 20）；或
- 连续 3 步无状态变化（触发 fail-fast）。

### 7.5 任务专用子目标模板（先写死）

针对“打开百度并搜索 Python”，固定子目标：

1. 聚焦浏览器地址栏；
2. 输入 `https://www.baidu.com` 并回车；
3. 聚焦搜索框并输入 `Python`；
4. 提交搜索并等待结果页。

推进规则：

- 每个子目标由 1~2 条规则判断完成；
- 若连续两步未完成当前子目标，则允许 fallback 动作（如 `WAIT` 或重新聚焦地址栏）。

### 7.6 候选动作最小策略（避免动作爆炸）

每步最多生成 8 个候选：

- CLICK：ranked top-5 中 clickable 元素；
- TYPE：仅对 top-2 editable 元素，文本候选最多 1 个；
- WAIT：固定 1 个。

动作选择优先级：

1. 与当前 subgoal 直接匹配的动作；
2. 本地模型打分最高动作；
3. 若分数接近，优先 CLICK（更稳）。

### 7.7 最小可观测性（必须做）

每步记录到 `jsonl`：

- `task_id, step, current_subgoal`
- `topk_element_ids + 简要文本`
- `candidate_actions`
- `chosen_action`
- `done/success_signal`
- `latency_ms`

并保存失败案例截图索引（仅失败步）。

### 7.8 3 天落地排期（可直接执行）

Day 1：

- 打通本地模型 client；
- 完成 `UIParser` + 固定 `StageManager`；
- 能输出候选动作。

Day 2：

- 接 `GroundingRanker`（规则+本地模型打分）；
- 接 `ActionComposer` + `LocalModelPolicy`；
- 跑通 1 次完整 episode。

Day 3：

- 加日志与 fail-fast；
- 连跑 10 次并统计成功率/步数/延迟；
- 根据失败样例调 3 处阈值（top-k、max_steps、subgoal 规则）。

### 7.9 MVP 之后的下一步（不在本次实现范围）

当单任务稳定后，再按顺序打开：

1. ShallowSearch depth=1（小预算）；
2. `StepRecordLite + StateStore` 数据闭环；
3. GroundingRanker 训练化（listwise）；
4. 多任务泛化评估。
