# 用户问题解决全流程 - 流程图

以下 Mermaid 流程图可在支持 Mermaid 的编辑器（如 VS Code/Cursor 插件）中预览，或复制到 [Mermaid Live](https://mermaid.live) 导出为 PNG/JPG。

## 主流程图

```mermaid
flowchart TD
    Start([用户输入问题]) --> Validate[输入校验 validate_question]
    Validate --> FastPath{命中快速路径?<br/>问候/能力自描述/对话历史元问题}
    FastPath -->|是| FastReturn[直接返回快速路径答案]
    FastReturn --> End1([结束])
    FastPath -->|否| Snapshot[创建历史快照 create_snapshot]
    Snapshot --> Cache{命中请求级缓存?<br/>且非时间/历史相关}
    Cache -->|是| CacheReturn[返回缓存答案]
    CacheReturn --> End2([结束])
    Cache -->|否| Trace[注入 TraceContext<br/>构建 run_context]
    Trace --> Router{启用任务路由且<br/>判为「无需调工具」?}
    Router -->|是| DirectAnswer[LLM 直接回答<br/>_direct_answer_without_tools]
    DirectAnswer --> End3([结束])
    Router -->|否| Workflow[进入工作流 workflow.run]
    Workflow --> Planning[规划节点 Planning<br/>decompose_task → task_plan.steps]
    Planning --> Execution[执行节点 Execution<br/>execute_step 当前步骤]
    Execution --> ToolOrReason{步骤类型?}
    ToolOrReason -->|none| DirectReason[直接推理 _direct_reasoning]
    ToolOrReason -->|工具| ToolCall[ToolHub.execute /<br/>execute_by_capability]
    DirectReason --> StepResult[step_results.append]
    ToolCall --> StepResult
    StepResult --> HasResults{本步有结果?}
    HasResults -->|是| Verify[验证节点 Verification<br/>verify_result]
    HasResults -->|否| MoreSteps
    Verify --> MoreSteps{还有未执行步骤?}
    MoreSteps -->|是| Execution
    MoreSteps -->|否| Synthesis[合成节点 Synthesis<br/>取最后成功结果 → final_answer]
    Synthesis --> Memory[写入对话历史<br/>可选写缓存、清除快照]
    Memory --> End4([返回 answer, success, reasoning, errors])

    Exception[任意步骤异常] -.-> ClearSnapshot[清除快照]
    ClearSnapshot -.-> ErrorReturn([返回 success=False, error])
```

## 工作流内部循环（简化）

```mermaid
flowchart LR
    subgraph 工作流
        A[Planning 规划] --> B[Execution 执行]
        B --> C{有 step_results?}
        C -->|是| D[Verification 验证]
        C -->|否| E{还有步骤?}
        D --> E
        E -->|是| B
        E -->|否| F[Synthesis 合成]
        F --> G([final_answer])
    end
```

## 说明

- **快速路径**：问候（你好/hi）、能力自描述（你会什么）、对话历史元问题（上一个问题）→ 不走规划/执行，直接返回。
- **请求级缓存**：同问题重复问且非时间/历史相关时命中，直接返回缓存答案。
- **任务先验路由**：配置 `tools.use_task_router: true` 时，LLM 先判断是否需调工具；若否则直接 LLM 回答。
- **工作流**：规划 → 执行（每步可为直接推理或工具调用）→ 有结果则验证 → 无剩余步骤后合成 → 取最后成功结果作为最终答案。
- **异常**：任一步异常则清除快照并返回 `success: false, error`。
