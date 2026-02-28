# Prompt Template System

## Overview

This directory contains the prompt template system built with the Jinja2 template engine. All prompt templates use the `.jinja` format and are managed by `PromptTemplateManager`.

## Template Files

### 1. `system_prompt.jinja`
System-level prompt defining the agent's role and behavior rules.

### 2. `plan_generate.jinja`
Prompt template for generating a complete plan.

**Variables:**
- `system_prompt`: System prompt
- `goal`: Task goal
- `observation`: Current observation
- `action_history`: Action history (optional)
- `memory_context`: Working-memory context (optional)
- `tools_description`: Tool descriptions

### 3. `plan_replan.jinja`
Prompt template for local replanning.

**Variables:**
- `system_prompt`: System prompt
- `goal`: Task goal
- `observation`: Current observation
- `error_info`: Error details (optional)
- `current_step`: Current failed step (JSON string)
- `previous_steps`: Completed steps (JSON string)
- `remaining_steps`: Remaining steps (JSON string)
- `memory_context`: Working-memory context (optional)
- `tools_description`: Tool descriptions
- `tool_names`: Comma-separated tool names

### 4. `task_breakdown.jinja`
Prompt template for task decomposition.

**Variables:**
- `system_prompt`: System prompt
- `goal`: Task goal

### 5. `plan_repair.jinja`
Prompt template for repairing invalid JSON outputs.

**Variables:**
- `system_prompt`: System prompt
- `invalid_output`: Invalid output
- `tools_description`: Tool descriptions
- `tool_names`: Comma-separated tool names

### 6. `action_repair.jinja`
Prompt template for fixing failed actions.

**Variables:**
- `system_prompt`: System prompt
- `error_context`: Error context
- `tools_description`: Tool descriptions

## Usage

### Option 1: Use the DSL (recommended)

```python
from pcguiagent.llms.prompt_templates import get_dsl

dsl = get_dsl()

# Generate planning prompt
prompt = dsl.plan_generation(
    goal="open vscode",
    observation="None (initial planning)",
    tools_description="...",
    memory_context="..."
)

# Local replanning
prompt = dsl.step_replan(
    goal="...",
    observation="...",
    current_step={"step": 1, "action": {...}},
    previous_steps=[],
    remaining_steps=[...],
    tools_description="...",
    tool_names=["code.launch_vscode", ...],
    error_info="..."
)

# Task decomposition
prompt = dsl.task_decomposition(goal="open vscode and create excel")

# JSON repair
prompt = dsl.json_repair(
    invalid_output="...",
    tools_description="...",
    tool_names=["code.*", "excel.*"]
)

# Action repair
prompt = dsl.action_repair(
    error_context="Tool execution failed: ...",
    tools_description="..."
)
```

### Option 2: Use the template manager directly

```python
from pcguiagent.llms.prompt_templates import get_template_manager

tm = get_template_manager()

# Render template
prompt = tm.render(
    "plan_generate",
    system_prompt=tm.render_system_prompt(),
    goal="open vscode",
    observation="...",
    tools_description="...",
    action_history="...",
    memory_context="..."
)
```

### Option 3: Custom templates

1. Create a new `.jinja` file in the `templates/` directory
2. Load and render via `PromptTemplateManager.render()`

```python
tm = get_template_manager()
prompt = tm.render("my_custom_template", arg1="value1", arg2="value2")
```

## Jinja2 语法

Templates use standard Jinja2 syntax:

- `{{ variable }}`: 变量插值
- `{% if condition %}...{% endif %}`: 条件语句
- `{% for item in list %}...{% endfor %}`: 循环语句
- `{% include "other_template.jinja" %}`: 包含其他模板

## Template layering

The system supports layered templates:

1. **System layer** (`system_prompt.jinja`): Base role and behaviors
2. **Task layer** (`task_breakdown.jinja`): Task decomposition
3. **Planning layer** (`plan_generate.jinja`, `plan_replan.jinja`): Plan generation and replanning
4. **Repair layer** (`plan_repair.jinja`, `action_repair.jinja`): Error repair

Each template can reference the system prompt via `{{ system_prompt }}` for modular composition.

## Modifying templates

1. Edit the corresponding `.jinja` file directly
2. Templates are auto-loaded and cached
3. Restart the app to clear the cache

## Notes

1. Template files must use UTF-8 encoding
2. Variable names must match those used in the templates
3. Jinja2 auto-escapes special characters; use `|safe` for raw output
4. Template syntax errors raise exceptions at runtime

