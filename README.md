# PC GUI Agent 框架

一个面向 **个人电脑（PC）自动化** 的智能 Agent 框架，采用 **Intra-Agent Multi-Role Reasoning（单 Agent 多角色推理）** 架构，支持 **基于 LLM 的任务规划**，并集成 **OSWorld** 用于真实桌面环境下的能力评估。

---

## ✨ 特性

* **Intra-Agent Multi-Role Reasoning 架构**

  * 单 Agent 内部多角色协作（PlannerRole / MemoryRole / ReflectorRole）
  * 角色间通过直接方法调用协作，无消息传递开销
  * 高效的角色协作机制
* **OSWorld 动作空间**

  * 直接生成 pyautogui Python 代码字符串
  * 与 OSWorld 评估框架完全兼容
  * 统一的动作格式验证
* **基于 LLM 的任务规划**

  * 任务理解与分解
  * 递归式规划生成
  * 动态重规划与计划修复
* **反思与修复机制**

  * 自动分析失败原因并重试
  * 任务验证器检查任务完成状态
* **记忆系统**

  * 任务历史与经验复用
  * 短期/情景/长期三层记忆架构
  * 记忆上下文自动构建
* **动作模式系统**

  * 统一的动作定义和验证
  * 确保各组件动作格式一致
  * OSWorld 动作格式转换
* **OSWorld 评估支持**

  * Acc / TIR / ACS 指标
  * 完整的 OSWorld observation 适配

---

## 🚀 快速开始

### 1. 环境准备

**推荐使用 Conda**

```bash
conda env create -f environment.yml
conda activate agentsec
```

（如需 GUI 自动化）

```bash
playwright install chromium
```

---

### 2. 配置 LLM

编辑 `src/pcguiagent/config.yaml`：

```yaml
llm:
  provider: deepseek   # deepseek | openai | doubao
  model: deepseek-chat
  api_key: YOUR_API_KEY
```

---

### 3. 运行一个任务

```bash
python -m src.pcguiagent.main \
  --goal "在浏览器中打开百度并搜索 Python"
```

---

## 🧪 Python API 示例

### OSWorld 集成示例

```python
from pcguiagent.agent import PCGuiAgent

# 创建 Agent 实例
agent = PCGuiAgent(
    action_space="osworld",
    observation_type="a11y_tree",
    config_path="src/pcguiagent/config.yaml"
)

# 初始化
await agent.initialize()

# OSWorld 调用接口
observation = {
    "instruction": "在浏览器中打开百度并搜索 Python",
    "a11y_tree": "...",  # 可访问性树
    "screenshot": b"...",  # 截图（可选）
    "step": 0
}

# 获取动作
action = agent.act(observation)  # 返回 pyautogui 代码字符串

# 关闭
await agent.close()
```

### 直接运行任务（CLI 模式）

```python
import asyncio
from pcguiagent.agent import PCGuiAgent

async def main():
    agent = PCGuiAgent(config_path="src/pcguiagent/config.yaml")
    await agent.initialize()
    
    # 注意：run() 方法主要用于 CLI，OSWorld 评估应使用 act/step 接口
    result = await agent.run("在浏览器中打开百度并搜索 Python")
    print(result)
    
    await agent.close()

asyncio.run(main())
```

---

## 📊 OSWorld 评估

```bash
python evaluation/run_osworld_eval.py \
  --test_all_meta_path evaluation_examples/test_all.json \
  --action_space osworld \
  --max_steps 50
```

**评估指标说明**

* **Acc（准确率）**：任务成功完成比例
* **TIR（工具调用率）**：正确选择工具的比例
* **ACS（平均步数）**：完成任务的平均操作步数

---

## 📁 项目结构

```
agentDaydayup/
├── src/
│   ├── main.py                  # 主入口（CLI）
│   └── pcguiagent/              # 核心框架
│       ├── agent.py             # PCGuiAgent 主类（OSWorld 适配器）
│       ├── bootstrap.py         # 系统引导
│       ├── config.yaml          # 配置文件
│       ├── agents/              # Agent 组件
│       │   └── task_verifier.py # 任务验证器
│       ├── roles/               # 角色模块（Intra-Agent Multi-Role Reasoning）
│       │   ├── base_role.py     # 角色基类
│       │   ├── planner_role.py  # 规划角色
│       │   ├── memory_role.py   # 记忆角色
│       │   └── reflector_role.py # 反思角色
│       ├── planners/            # 任务规划
│       │   ├── recursive_planner.py # 递归规划器
│       │   └── plan_repair.py   # 计划修复
│       ├── memory/              # 记忆模块
│       │   ├── storage.py       # 记忆存储（统一接口）
│       │   ├── short_term.py    # 短期记忆
│       │   ├── episodic.py      # 情景记忆
│       │   ├── long_term.py     # 长期记忆
│       │   └── context_builder.py # 上下文构建器
│       ├── llms/                # LLM 接入
│       │   ├── base_client.py    # LLM 基础客户端
│       │   ├── deepseek_client.py # DeepSeek 客户端
│       │   ├── openai_client.py  # OpenAI 客户端
│       │   ├── prompt_templates.py # Prompt 模板管理
│       │   ├── output_validator.py # 输出验证器
│       │   └── templates/        # Prompt 模板文件
│       │       ├── next_action_osworld.jinja
│       │       ├── plan_generate_osworld.jinja
│       │       └── ...
│       ├── core/                # 核心类型和工具
│       │   ├── config.py        # 配置管理
│       │   ├── types.py         # 类型定义
│       │   ├── osworld_actions.py # OSWorld 动作定义
│       │   └── action_schema/   # 动作模式系统
│       │       ├── action.py    # Action 定义
│       │       ├── registry.py  # 动作注册表
│       │       └── validator.py # 动作验证器
│       └── utils/               # 工具模块
│           ├── action_extractor.py # 动作提取器
│           ├── app_detector.py  # 应用检测器（Windows）
│           ├── a11y_preprocessor.py # 可访问性树预处理
│           ├── config_loader.py # 配置加载器
│           ├── logger.py        # 日志工具
│           ├── system_info.py   # 系统信息
│           └── ...
├── evaluation/                  # OSWorld 评估脚本
├── data/                        # 数据存储（SQLite）
├── logs/                        # 日志文件
└── traces/                      # 执行轨迹
```

---

## 🏗 架构说明

### Intra-Agent Multi-Role Reasoning 架构

本框架采用 **Intra-Agent Multi-Role Reasoning（单 Agent 多角色推理）** 架构，在单个 Agent 实例内部通过多个角色协作完成任务。

#### 核心组件

1. **PCGuiAgent（主 Agent）**
   - **位置**: `src/pcguiagent/agent.py`
   - **功能**: OSWorld 适配器，接收 OSWorld observation，通过角色协作生成 action
   - **职责**:
     - 转换 OSWorld observation 格式
     - 协调角色协作
     - 将 action 转换为 pyautogui 代码字符串

2. **角色系统（Roles）**
   - **位置**: `src/pcguiagent/roles/`
   - **架构**: 角色间通过直接方法调用协作，无消息传递开销
   - **角色**:
     - **PlannerRole**: 任务规划和分解，生成下一步动作
     - **MemoryRole**: 构建记忆上下文，提供历史经验
     - **ReflectorRole**: 任务验证和反思，分析失败原因

#### 核心模块

#### 1. **规划模块（Planners）**
- **位置**: `src/pcguiagent/planners/`
- **功能**: 任务规划和动作生成
- **组件**:
  - `recursive_planner.py`: 递归规划器，生成完整计划或下一步动作
  - `plan_repair.py`: 计划修复，当计划失败时进行修复

#### 2. **记忆模块（Memory）**
- **位置**: `src/pcguiagent/memory/`
- **功能**: 三层记忆架构，存储和检索任务经验
- **组件**:
  - `storage.py`: 统一记忆接口
  - `short_term.py`: 短期记忆（当前任务上下文）
  - `episodic.py`: 情景记忆（执行事件记录）
  - `long_term.py`: 长期记忆（用户偏好/通用知识）
  - `context_builder.py`: 记忆上下文构建器

#### 3. **LLM 模块**
- **位置**: `src/pcguiagent/llms/`
- **功能**: LLM 客户端和 Prompt 管理
- **组件**:
  - `base_client.py`: LLM 基础客户端接口
  - `deepseek_client.py`: DeepSeek 客户端实现
  - `openai_client.py`: OpenAI 客户端实现
  - `prompt_templates.py`: Prompt 模板管理
  - `templates/`: Prompt 模板文件（Jinja2 格式）

#### 4. **动作模式系统（Action Schema）**
- **位置**: `src/pcguiagent/core/action_schema/`
- **功能**: 统一动作定义和验证
- **组件**:
  - `action.py`: Action 数据类定义
  - `registry.py`: 动作注册表
  - `validator.py`: 动作验证器

#### 5. **OSWorld 适配**
- **位置**: `src/pcguiagent/core/osworld_actions.py`
- **功能**: OSWorld 动作空间定义和转换
- **特性**:
  - 定义 OSWorld 支持的动作类型
  - 将内部动作格式转换为 pyautogui 代码字符串
  - 动作格式验证

#### 6. **工具模块（Utils）**
- **位置**: `src/pcguiagent/utils/`
- **功能**: 系统级工具和辅助功能
- **组件**:
  - `action_extractor.py`: 从 LLM 输出中提取动作
  - `app_detector.py`: 应用检测器（Windows）
  - `a11y_preprocessor.py`: 可访问性树预处理
  - `config_loader.py`: 配置文件加载
  - `logger.py`: 日志工具
  - `system_info.py`: 系统信息获取

#### 7. **任务验证器（Task Verifier）**
- **位置**: `src/pcguiagent/agents/task_verifier.py`
- **功能**: 验证任务是否完成
- **特性**:
  - 分析当前状态判断任务完成度
  - 支持 ReflectorRole 进行任务反思

### 数据存储

- **memory.db**: 记忆数据库（SQLite），存储任务历史和经验
- **logs/**: 日志文件目录
- **traces/**: 执行轨迹文件（JSON 格式）

### 工作流程

1. **接收 Observation**: PCGuiAgent 接收 OSWorld observation（包含 instruction、a11y_tree 等）
2. **构建记忆上下文**: MemoryRole 从记忆系统中检索相关经验
3. **生成动作**: PlannerRole 基于目标、观察和记忆上下文生成下一步动作
4. **动作转换**: 将内部动作格式转换为 pyautogui 代码字符串
5. **任务验证**: ReflectorRole 验证任务完成状态（可选）
6. **返回动作**: 返回 pyautogui 代码字符串给 OSWorld 执行

---

## 🛠 技术栈

* Python 3.8+
* DeepSeek / OpenAI
* asyncio + SQLite
* Pydantic
* Jinja2（Prompt 模板）
* OSWorld（评估框架）

---

## 📄 开源协议

MIT License



# agentDaydayup
