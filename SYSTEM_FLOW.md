# Research Agent - 系统运行流程图

## 1. 完整请求处理流程

```
┌─────────────────────────────────────────────────────────────┐
│                    用户请求入口                              │
│  HTTP: POST /api/v1/predict                                │
│  Console: 用户输入问题                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  输入验证层              │
        │  - validate_question()  │
        │  - 检查长度、格式         │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │  AgentOrchestrator      │
        │  process_task()         │
        │  - 添加到记忆            │
        │  - 路由到工作流          │
        └────────┬───────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ LangGraph    │  │ MultiAgent  │
│ Workflow     │  │ System       │
│ (如果可用)    │  │ (简化模式)    │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                │
                ▼
    ┌───────────────────────┐
    │   CoordinationAgent   │
    │   process_question()   │
    └───────────┬───────────┘
                │
    ┌───────────┴───────────────────────────────────┐
    │                                                 │
    ▼                                                 ▼
┌──────────────┐                            ┌──────────────┐
│ 步骤1: 规划   │                            │ 步骤2: 执行   │
│ PlanningAgent│                            │ ExecutionAgent│
│ decompose_task│                            │ execute_step │
└──────┬───────┘                            └──────┬───────┘
       │                                           │
       │ 生成任务计划                               │
       │ {steps: [{id, description, tool_type}]}  │
       │                                           │
       └───────────────┬───────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  循环执行每个步骤      │
            │  for step in steps:   │
            └──────────┬───────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────┐            ┌──────────────┐
│ tool_type == │            │ tool_type != │
│ "none"       │            │ "none"       │
│              │            │              │
│ 直接推理      │            │ 工具调用      │
│ _direct_     │            │ _execute_    │
│ reasoning()  │            │ with_tool()  │
└──────┬───────┘            └──────┬───────┘
       │                          │
       │ LLM.generate_async()     │ tool.execute()
       │                          │ 如果失败 → 降级到直接推理
       └──────────┬───────────────┘
                  │
                  ▼
        ┌──────────────────────┐
        │  步骤3: 验证           │
        │  VerificationAgent    │
        │  verify_result()       │
        │  - 检查结果格式         │
        │  - 计算置信度           │
        └──────────┬─────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  步骤4: 合成答案       │
        │  _synthesize_answer() │
        │  - 整合所有步骤结果     │
        │  - 如果失败，直接回答   │
        └──────────┬─────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  答案归一化            │
        │  normalize_answer()   │
        │  - 格式化输出          │
        └──────────┬─────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  返回结果              │
        │  {answer: "...", ...} │
        └──────────────────────┘
```

## 2. 步骤执行详细流程

```
执行步骤 (execute_step)
    │
    ├─ 判断工具类型
    │
    ├─ tool_type == "none"
    │   │
    │   └─ _direct_reasoning()
    │       │
    │       ├─ 构建提示词
    │       │   "请回答以下问题：{step_desc}"
    │       │
    │       ├─ 调用LLM
    │       │   ├─ generate_async() (异步)
    │       │   └─ 或 generate() (在线程池中)
    │       │
    │       └─ 返回结果
    │           {success: True, result: "...", method: "direct_reasoning"}
    │
    └─ tool_type != "none"
        │
        └─ _execute_with_tool()
            │
            ├─ 检查工具是否存在
            │   ├─ 不存在 → 降级到 _direct_reasoning()
            │   └─ 存在 → 继续
            │
            ├─ 准备工具输入
            │   ├─ search_web: 提取搜索关键词
            │   ├─ calculate: 提取数学表达式
            │   └─ 其他: 使用描述或上下文
            │
            ├─ 调用工具
            │   ├─ tool.execute(input)
            │   └─ 如果失败 → 降级到 _direct_reasoning()
            │
            └─ 格式化结果
                └─ 返回 {success: True, result: "...", method: "tool_xxx"}
```

## 3. 异常处理流程

```
异常发生
    │
    ├─ LLM调用异常
    │   │
    │   ├─ TimeoutError
    │   │   └─ 返回: {success: False, error: "LLM API调用超时"}
    │   │
    │   ├─ ConnectionError
    │   │   └─ 返回: {success: False, error: "无法连接到LLM服务"}
    │   │
    │   ├─ HTTPError
    │   │   └─ 返回: {success: False, error: "LLM API HTTP错误: {status_code}"}
    │   │
    │   └─ 其他异常
    │       └─ 返回: {success: False, error: "推理失败: {str(e)}"}
    │
    ├─ 工具调用异常
    │   │
    │   ├─ 工具不存在
    │   │   └─ 降级到 _direct_reasoning()
    │   │
    │   ├─ 工具执行失败
    │   │   └─ 降级到 _direct_reasoning()
    │   │
    │   └─ 工具输入无效
    │       └─ 降级到 _direct_reasoning()
    │
    ├─ 步骤执行异常
    │   │
    │   └─ 捕获异常，返回: {success: False, error: str(e)}
    │       └─ 继续执行下一步
    │
    └─ HTTP请求异常
        │
        ├─ TimeoutError
        │   └─ HTTP 504: "处理超时"
        │
        ├─ ValueError (输入验证)
        │   └─ HTTP 400: "输入验证失败"
        │
        └─ 其他异常
            └─ HTTP 500: "处理失败，请稍后重试"
```

## 4. 降级策略流程

```
工具调用失败
    │
    ├─ 工具不存在
    │   └─ 降级到直接推理
    │       └─ _direct_reasoning()
    │
    ├─ 工具执行失败
    │   └─ 降级到直接推理
    │       └─ _direct_reasoning()
    │
    └─ 工具输入无效
        └─ 降级到直接推理
            └─ _direct_reasoning()

所有步骤失败
    │
    └─ 尝试直接回答用户问题
        │
        ├─ 构建简单提示词
        │   "请直接回答以下问题：{question}"
        │
        ├─ 调用LLM
        │   └─ generate_async()
        │
        └─ 如果成功
            └─ 返回答案
        └─ 如果失败
            └─ 返回 "抱歉，我无法回答这个问题。"

LLM合成失败
    │
    └─ 使用最后一个成功步骤的结果
        │
        └─ 如果都没有
            └─ 返回 "无法生成答案"
```

## 5. 数据流

```
用户问题: "从北京到上海有多远？"
    │
    ▼
PlanningAgent
    │
    └─ 生成计划:
        {
            steps: [
                {id: 1, description: "确定北京和上海的地理坐标", tool_type: "search_web"},
                {id: 2, description: "计算两地直线距离", tool_type: "calculate"},
                {id: 3, description: "整理答案", tool_type: "none"}
            ]
        }
    │
    ▼
ExecutionAgent (循环执行)
    │
    ├─ 步骤1: search_web("北京 上海 地理坐标")
    │   └─ 返回: {success: True, result: "北京: 39.9°N, 116.4°E; 上海: 31.2°N, 121.5°E"}
    │
    ├─ 步骤2: calculate("计算距离")
    │   └─ 输入无效 → 降级到 _direct_reasoning()
    │       └─ 返回: {success: True, result: "约1068公里"}
    │
    └─ 步骤3: _direct_reasoning("整理答案")
        └─ 返回: {success: True, result: "从北京到上海的直线距离约为1068公里"}
    │
    ▼
VerificationAgent (验证每个步骤)
    │
    └─ 验证结果，计算置信度
    │
    ▼
CoordinationAgent._synthesize_answer()
    │
    └─ 整合所有步骤结果
        └─ 生成最终答案: "从北京到上海的直线距离约为1068公里"
    │
    ▼
normalize_answer()
    │
    └─ 格式化: "从北京到上海的直线距离约为1068公里"
    │
    ▼
返回: {"answer": "从北京到上海的直线距离约为1068公里"}
```

## 6. 状态管理

```
AgentState (CoordinationAgent)
    │
    ├─ question: str                    # 用户问题
    ├─ task_plan: Dict                  # 任务计划
    ├─ current_step: int                # 当前步骤索引
    ├─ step_results: List[Dict]        # 步骤结果列表
    │   └─ [{step_id, success, result, method, ...}, ...]
    ├─ verification_results: List[Dict] # 验证结果列表
    │   └─ [{verified, confidence, issues}, ...]
    ├─ final_answer: str                # 最终答案
    ├─ confidence: float                # 整体置信度
    └─ errors: List[str]                # 错误列表

WorkflowState (LangGraphWorkflow)
    │
    ├─ question: str
    ├─ messages: List[Dict]
    ├─ task_plan: Dict
    ├─ current_step: int
    ├─ step_results: List[Dict]
    ├─ final_answer: str
    ├─ errors: List[str]
    └─ metadata: Dict
```

## 7. 关键决策点

### 7.1 工具类型判断

```
tool_type = step.get("tool_type", "none")
    │
    ├─ "none" → _direct_reasoning()
    │   └─ 使用LLM直接推理
    │
    ├─ "search_web" → SearchTool.execute()
    │   └─ 网络搜索
    │
    ├─ "calculate" → CalculatorTool.execute()
    │   └─ 数学计算
    │
    └─ 其他 → 降级到 _direct_reasoning()
        └─ 工具不存在，使用LLM推理
```

### 7.2 答案生成策略

```
step_results
    │
    ├─ 有成功步骤
    │   └─ 使用LLM整合所有成功步骤的结果
    │
    ├─ 所有步骤失败
    │   └─ 尝试直接回答用户问题
    │       └─ 如果失败 → "抱歉，我无法回答这个问题。"
    │
    └─ 没有步骤结果
        └─ "无法生成答案"
```

---

**文档版本**: 1.0.0  
**最后更新**: 2026-01-28
