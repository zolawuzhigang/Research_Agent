# 工具调用策略升级（豆包策略）

## 概述

原先的静态优先级「本地工具 > skill > MCP」已升级为「任务先验路由 → 动态优先级打分 → 触发与兜底」策略，与豆包建议一致，充分发挥大模型与多源工具的能力。

## 核心改动

### 1. 任务先验路由（可选）

- **配置**：`config.yaml` → `tools.use_task_router: true/false`（默认 `false`，保持兼容）
- **逻辑**：在进入规划/执行前，由 LLM 对用户输入做三层判断：
  - **是否调用工具**：常识、简单计算、纯对话等判为「否」，直接由 LLM 回答，不进入工具链路
  - **能力标签**：文件操作、数据分析、通用查询、业务接口调用等
  - **属性标签**：时效性（高/中/低）、可靠性（高/中/低）、成本敏感（高/低）
  - **适配载体**：根据能力与属性筛选「本地工具 / skill / MCP」
- **实现**：`src/agent/task_router.py`、提示词 `src/prompts/tool_routing.yaml`
- **效果**：避免「小任务大调用」；核心业务/隐私任务可排除 MCP

### 2. 动态优先级打分（ToolHub）

- **触发**：执行层调用 `tool_hub.execute(name, input_data, task_ctx=...)` 或 `execute_by_capability(..., task_ctx=...)` 时，若传入 `task_ctx`，则按打分排序候选，不再按固定 tools > skills > mcps
- **打分维度**（总权重 100%）：
  - **能力适配度（50%）**：工具 `meta.capabilities` 与任务 `capability_tags` 的交集；不匹配则排除
  - **调用成本（25%）**：本地 9 分、skill 7 分、MCP 4 分
  - **属性匹配（25%）**：高可靠性/高时效/高成本敏感时本地与 skill 加分、MCP 降权
  - **附加分**：最近成功 +1
- **实现**：`ToolHub.score_candidates_by_task_context()`、`execute_with_task_context()`

### 3. 触发与兜底

- **无需调工具**：任务路由判为「否」时，直接 LLM 回答并返回
- **每候选仅重试 1 次**：`execute_with_task_context` 中每个候选失败后只重试 1 次，再失败则按打分顺序尝试下一候选
- **回退顺序**：按动态打分从高到低依次尝试（同载体/跨载体均按分数），全部失败则返回最后一次错误信息

### 4. 数据流

- **编排器**：若启用 `use_task_router`，先调用 `route_task(question, llm, tool_names)`；若 `use_tools=False` 则 `_direct_answer_without_tools` 后返回；否则将 `task_ctx`（capability_tags、attribute_tags、adapt_carriers）写入 `run_context["task_ctx"]`
- **工作流**：`run_context` 作为 `metadata` 传入各节点
- **执行 Agent**：从 `context["task_ctx"]` 读取并传给 `tool_hub.execute(..., task_ctx=task_ctx)` 与 `execute_by_capability(..., task_ctx=task_ctx)`

## 配置

```yaml
# config/config.yaml
tools:
  timeout: 10
  max_retries: 2
  use_task_router: false   # 改为 true 启用任务先验路由
```

## 多工具组合（后续可扩展）

豆包对话中提到的「组合任务识别 → 工具依赖图谱 → 串并行流水线 → 格式校验 → 断点续跑」可在本策略之上扩展：当前规划层已产出多步骤，执行层按步调用工具；若需显式「子任务列表 + 工具链 + 格式转换」，可增加组合任务路由与依赖表，再与现有 `task_ctx` 和动态打分衔接。
