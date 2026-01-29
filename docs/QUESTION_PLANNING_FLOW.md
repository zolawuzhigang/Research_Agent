# 当前项目的问题规划流程

从用户输入一个问题到返回最终答案，整体流程如下。

---

## 一、总览（入口：Orchestrator.process_task）

```
用户问题 (task)
       │
       ▼
┌──────────────────┐
│ 1. 快速路径判断   │  问候 / 能力介绍 / 对话历史元问题 → 直接返回，不走规划
└────────┬─────────┘
         │ 未命中
         ▼
┌──────────────────┐
│ 2. 历史快照      │  create_snapshot()，用于“刚刚/之前”等时间语义
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. 请求级缓存    │  若命中且非“时间/历史”类问题 → 直接返回缓存答案
└────────┬─────────┘
         │ 未命中
         ▼
┌──────────────────┐
│ 4. 工作流执行    │  LangGraph 图 或 简化工作流（规划→执行→验证→合成）
└────────┬─────────┘
         ▼
    最终答案 + 写回缓存（若可缓存）
```

---

## 二、快速路径（Fast Path）

**位置**：`src/agent/orchestrator.py` → `_maybe_fast_path()`

**作用**：对少量“固定回答”类输入直接返回，不调用 LLM 规划、不跑工具，省时省 token。

| 类型       | 触发条件（示例）                         | 返回内容                     |
|------------|------------------------------------------|------------------------------|
| 简单问候   | 短文本且整词匹配 hi/hello，或含你好/嗨等 | 系统自我介绍                 |
| 能力介绍   | “你都能干什么”“what can you do”等        | 基于 ToolHub 的真实能力描述  |
| 对话历史元 | “上一个问题”“what did I ask”等           | 从 memory 取上一问/问题列表  |

**注意**：问候用整词+长度保护，长题（如含 "this"）不会误触发。

---

## 三、工作流（LangGraph 或 简化版）

**入口**：`orchestrator.process_task()` 中调用 `self.workflow.run(task, context)`。

**图结构**（`langgraph_workflow.py`）：

```
                    ┌─────────────┐
                    │  planning   │  规划节点：LLM 分解任务 → task_plan (steps)
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  execution  │  执行节点：按 current_step 执行一步
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        _should_verify   "continue"   "synthesize"
              │            │            │
              ▼            │            ▼
        ┌─────────────┐    │      ┌─────────────┐
        │ verification│────┘      │  synthesis   │ → END，返回 final_answer
        └──────┬──────┘           └─────────────┘
               │
               └──────────────────► execution（执行下一步）
```

- **planning → execution**：规划完成后进入执行。
- **execution → _should_verify**：每执行一步后判断：
  - 还有未执行步骤 → 去 **verification**；
  - 全部步骤完成 → 去 **synthesis**。
- **verification → execution**：验证完当前步骤后回到执行节点执行下一步。

---

## 四、各节点在做什么

### 1. 规划节点（Planning）

**位置**：`multi_agent_system.py` → `PlanningAgent.decompose_task(question)`

**流程**：

1. 用 `_build_decomposition_prompt(question)` 拼提示词，包含：
   - 用户问题；
   - 可用工具说明（none / search_web / advanced_web_search / calculate / get_time / get_conversation_history / list_workspace_files 等）。
2. 调用 **LLM**，要求输出 **JSON 计划**，例如：
   ```json
   {
     "steps": [
       { "id": 1, "description": "...", "tool_type": "advanced_web_search", "dependencies": [], "complexity": 3 },
       { "id": 2, "description": "...", "tool_type": "none", ... }
     ],
     "parallel_groups": [...],
     "total_estimated_time": 60
   }
   ```
3. `_parse_plan(response)` 解析 JSON，得到 `task_plan`（含 `steps` 列表）。

**结果**：状态里写入 `task_plan`，`current_step = 0`。

---

### 2. 执行节点（Execution）

**位置**：`multi_agent_system.py` → `ExecutionAgent.execute_step(step, context)`

**流程**：

1. 从 `task_plan.steps[current_step]` 取当前步骤，得到 `tool_type`（如 none / advanced_web_search / get_time 等）。
2. **分支**：
   - **tool_type == "none"**：`_direct_reasoning(step, context)`  
     - 用 LLM 根据步骤描述 + 前面步骤的 `step_results` 直接生成答案，不调工具。
   - **否则**：`_execute_with_tool(step, context)`  
     - 通过 **ToolHub** 解析并调用对应工具（如 advanced_web_search、get_time），把工具返回作为本步结果。
3. 将本步结果 append 到 `state["step_results"]`，`current_step += 1`。

**结果**：状态里多一条 `step_results`，`current_step` 指向下一步。

---

### 3. 验证节点（Verification）

**位置**：`multi_agent_system.py` → `VerificationAgent.verify_result(last_result, context)`

**流程**：

- 对**刚执行完的那一步**的结果做校验（如格式、合理性、与前面步骤一致性等）。
- 若未通过，可在 `state["errors"]` 里记一笔；流程仍会继续执行后续步骤。

**结果**：状态可能更新 `errors`，然后回到执行节点执行下一步。

---

### 4. 合成节点（Synthesis）

**位置**：`langgraph_workflow.py` → `_synthesis_node(state)`

**流程**：

- 从 `step_results` 中选一个作为最终答案：
  - 从**后往前**找第一个 `success=True` 且 `result` 非空的步骤，取其 `result` 作为 `final_answer`。
- 若没有符合条件的步骤，则 `final_answer = "无法生成答案"`。

**结果**：`state["final_answer"]` 写入，工作流结束，由 `workflow.run()` 返回给 Orchestrator。

---

## 五、数据流小结

| 阶段     | 输入                     | 输出 / 状态变化                          |
|----------|--------------------------|------------------------------------------|
| 快速路径 | task                     | 直接返回 answer，不写 task_plan          |
| 规划     | question                 | task_plan (steps), current_step=0       |
| 执行     | step, step_results       | step_results 增加一条，current_step+1    |
| 验证     | 最后一条 step_result     | 可能更新 errors                          |
| 合成     | step_results             | final_answer                             |

Orchestrator 拿到 `workflow.run()` 的返回后，会把 `final_answer` 作为 `result["answer"]` 返回给调用方，并视情况写对话历史与请求级缓存。

---

## 六、相关文件

| 职责           | 文件 |
|----------------|------|
| 入口、快速路径、缓存 | `src/agent/orchestrator.py` |
| 工作流图、节点编排 | `src/agent/langgraph_workflow.py` |
| 规划 / 执行 / 验证 | `src/agent/multi_agent_system.py`（PlanningAgent / ExecutionAgent / VerificationAgent） |
| 工具调用       | `src/toolhub.py` + `src/tools/*` |

若 LangGraph 不可用，会走 `_simple_workflow()`：顺序执行 planning → 循环（execution → verification）→ synthesis，逻辑与图等价，只是没有用图 API。
