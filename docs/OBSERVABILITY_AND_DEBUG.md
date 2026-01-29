# 可观测与调试：工具调用、中间推理、证据整合

本文说明如何将**工具调用**、**中间推理**、**证据整合**等环节做到**模块化、可观测、可调试**。

---

## 一、模块划分（已实现）

| 环节         | 位置 / 模块 | 说明 |
|--------------|-------------|------|
| 规划         | `PlanningAgent.decompose_task` | LLM 分解问题为多步，每步带 tool_type |
| 工具调用     | `ExecutionAgent._execute_with_tool` + `ToolHub.execute` | 按 tool_type 调用工具，支持降级 |
| 中间推理     | `ExecutionAgent._direct_reasoning` | tool_type=none 时 LLM 直接推理 |
| 验证         | `VerificationAgent.verify_result` | 单步结果校验 |
| 证据整合     | `LangGraphWorkflow._synthesis_node` | 从 step_results 选最终答案 |

各环节通过 **context**（含 `step_results`、`_trace`）串联，便于单独测试或替换实现。

---

## 二、可观测：Trace 事件

开启可观测后，单次请求会记录一条 **trace**，包含按时间顺序的 **事件列表**，便于排查延迟、错误和中间结果。

### 配置

在 `config/config.yaml` 中增加：

```yaml
observability:
  enabled: true           # 设为 true 开启 trace
  max_events: 200         # 单次请求最多记录事件数
  max_preview: 500        # 每条事件的 input/output 预览最大字符数
  include_in_response: true   # 是否在 process_task 返回中附带 trace 字段
```

### 事件类型（phase）

| phase              | 含义           | 典型字段 |
|--------------------|----------------|----------|
| planning_start     | 规划开始       | input_preview（问题摘要） |
| planning_end       | 规划结束       | steps_count, duration_ms, success |
| step_start         | 单步开始       | step_id, tool_type, input_preview |
| tool_call          | 工具调用       | step_id, tool_type, input/output_preview, duration_ms, success |
| reasoning          | 中间推理       | step_id, input/output_preview, duration_ms, success |
| step_end           | 单步结束       | step_id, output_preview, duration_ms, success, method |
| verification       | 验证           | step_id, duration_ms, success, confidence |
| evidence_synthesis | 证据整合       | step_results_count, output_preview, duration_ms, success |

### 返回中的 trace 结构

当 `observability.enabled=true` 且 `include_in_response=true` 时，`process_task()` 的返回中会多一个 `trace` 字段，例如：

```json
{
  "success": true,
  "answer": "最终答案文本",
  "reasoning": "...",
  "trace": {
    "request_id": "a1b2c3d4",
    "events_count": 12,
    "events": [
      {"phase": "planning_start", "input_preview": "用户问题..."},
      {"phase": "planning_end", "steps_count": 3, "duration_ms": 1250.5, "success": true},
      {"phase": "step_start", "step_id": 1, "tool_type": "advanced_web_search", "input_preview": "..."},
      {"phase": "tool_call", "step_id": 1, "tool_type": "advanced_web_search", "status": "start", "input_preview": "..."},
      {"phase": "tool_call", "step_id": 1, "tool_type": "advanced_web_search", "status": "end", "duration_ms": 800, "success": true, "output_preview": "..."},
      {"phase": "step_end", "step_id": 1, "duration_ms": 810, "success": true, "method": "toolhub_advanced_web_search"},
      {"phase": "evidence_synthesis", "step_results_count": 3, "status": "end", "duration_ms": 2, "success": true, "output_preview": "最终答案..."}
    ]
  }
}
```

可用于：

- **调试**：看哪一步慢、哪一步失败、工具入参/出参是什么；
- **日志/监控**：将 `trace` 写入日志或发送到 APM；
- **复现**：结合 request_id 与 events 复现单次请求链路。

---

## 三、可调试：使用方式

### 1. 开启 trace 并查看返回

1. 将 `config/config.yaml` 中 `observability.enabled` 设为 `true`。
2. 调用 `process_task(question)`（如通过控制台、HTTP API 或 `scripts/smoke_test.py`）。
3. 在返回的 dict 中查看 `result["trace"]`，根据 `events` 顺序查看规划 → 各步执行（工具/推理）→ 验证 → 证据整合。

### 2. 仅日志、不附带在返回里

若不想在 API 返回里带 trace，可设 `include_in_response: false`，并在代码中订阅 `TraceContext` 的事件（例如在 `Observability` 模块中增加 logger 或 metrics 输出）。当前实现为「写入 context → 最后 to_dict 附在 result」；若需仅打日志，可在 orchestrator 中在 `workflow.run` 之后、附带到 result 之前，对 `trace_ctx.to_dict()` 打 logger.debug。

### 3. 按环节单独测试

- **工具调用**：直接调用 `ToolHub.execute(tool_type, tool_input)` 或各 `*Tool.execute(...)`。
- **中间推理**：直接调用 `ExecutionAgent._direct_reasoning(step, context)`。
- **证据整合**：构造 `state["step_results"]`，调用 `_synthesis_node(state)` 查看 `final_answer`。

各环节接口稳定，便于写单测或脚本复现问题。

---

## 四、扩展：自定义 Observer

若需要将事件发往其他系统（如 OpenTelemetry、自建监控），可：

1. 实现与 `TraceContext` 相同接口的类（如 `on_planning_start`, `on_tool_call_end`, `on_reasoning_end`, `on_synthesis_end` 等）。
2. 在 orchestrator 中根据配置实例化该实现，并放入 `run_context["_trace"]`，替代默认的 `TraceContext`。

这样无需改工作流与 ExecutionAgent 内部逻辑，即可接入新的可观测后端。

---

## 五、相关文件

| 文件 | 作用 |
|------|------|
| `src/observability/trace_context.py` | TraceEvent、TraceContext、NullTraceContext |
| `src/agent/orchestrator.py` | 创建 trace、注入 context、将 trace 附在返回 |
| `src/agent/langgraph_workflow.py` | 各节点内调用 trace（planning/verification/synthesis） |
| `src/agent/multi_agent_system.py` | ExecutionAgent 内 step/tool_call/reasoning 的 trace 调用 |
| `config/config.yaml` | `observability.enabled`、`max_events`、`max_preview`、`include_in_response` |
