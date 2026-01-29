# 多Agent系统架构设计文档

## 1. 设计背景

### 1.1 问题挑战

在高阶知识工作场景中，用户需求具有以下特征：
- **多跳推理**: 需要多步推理才能得到答案
- **信息验证**: 需要从多个来源验证信息准确性
- **工具依赖**: 需要调用外部工具（搜索、计算、API等）
- **复杂规划**: 需要动态调整执行计划

单轮问答无法满足这些需求，因此需要设计多Agent协作系统。

### 1.2 设计原则

基于DeepSeek的设计思路，我们遵循以下原则：

1. **任务可分解性**: 将复杂问题拆解为有序子任务
2. **状态持久化**: 维护多轮对话的状态、历史与中间结果
3. **工具即能力**: 无缝集成外部工具，扩展LLM边界
4. **验证与纠错**: 对每一步结果进行可信度评估与交叉验证
5. **用户协同**: 允许用户中途干预、澄清或修正

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                   用户问题输入                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              CoordinationAgent (协调Agent)                   │
│  - 流程控制                                                  │
│  - 状态管理                                                  │
│  - 错误处理                                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐
│ PlanningAgent│ │ExecutionAgent│ │VerificationAgent│
│  规划Agent   │ │  执行Agent   │ │  验证Agent      │
└───────┬──────┘ └─────┬─────┘ └─────┬─────┘
        │              │              │
        │      ┌───────┴───────┐      │
        │      │  工具注册表    │      │
        │      │ ToolRegistry  │      │
        │      └───────┬───────┘      │
        │              │              │
        └──────────────┼──────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              LangGraph工作流编排                              │
│  - 状态机管理                                                │
│  - 循环控制                                                  │
│  - 条件分支                                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              记忆管理器 (MemoryManager)                       │
│  - 短期记忆 (对话历史)                                       │
│  - 长期记忆 (知识、模式、经验)                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   最终答案输出                                │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 PlanningAgent (规划Agent)

**职责**: 任务分解和计划制定

**核心方法**:
- `decompose_task(question, context)`: 将问题分解为子任务
- `_build_decomposition_prompt()`: 构建任务分解提示词
- `_parse_plan()`: 解析LLM返回的计划

**输出格式**:
```json
{
    "steps": [
        {
            "id": 1,
            "description": "步骤描述",
            "tool_type": "search_web",
            "dependencies": [],
            "complexity": 3,
            "estimated_time": 10
        }
    ],
    "parallel_groups": [[1, 2], [3, 4]],
    "total_estimated_time": 60
}
```

#### 2.2.2 ExecutionAgent (执行Agent)

**职责**: 执行具体任务步骤

**核心方法**:
- `execute_step(step, context)`: 执行单个步骤
- `_direct_reasoning()`: 直接推理（不使用工具）
- `_execute_with_tool()`: 使用工具执行

**工具类型**:
- `search_web`: 网络搜索
- `calculate`: 数学计算
- `code_execution`: 代码执行
- `none`: 不需要工具，直接推理

#### 2.2.3 VerificationAgent (验证Agent)

**职责**: 验证信息准确性和一致性

**核心方法**:
- `verify_result(result, context)`: 验证结果
- `_check_consistency()`: 一致性检查
- `_cross_validate()`: 交叉验证
- `_check_logic()`: 逻辑检查

**验证维度**:
1. **基本验证**: 结果格式、完整性
2. **一致性检查**: 与其他结果对比
3. **交叉验证**: 多源验证
4. **逻辑检查**: 数值合理性、因果关系

**输出格式**:
```json
{
    "step_id": 1,
    "verified": true,
    "confidence": 0.85,
    "consistency_check": true,
    "cross_validation": true,
    "issues": []
}
```

#### 2.2.4 CoordinationAgent (协调Agent)

**职责**: 协调多个Agent的工作

**核心方法**:
- `process_question(question, context)`: 处理用户问题的主入口
- `_check_dependencies()`: 检查步骤依赖
- `_synthesize_answer()`: 合成最终答案
- `_calculate_overall_confidence()`: 计算整体置信度

**工作流程**:
1. 初始化状态
2. 任务规划（调用PlanningAgent）
3. 循环执行步骤（调用ExecutionAgent）
4. 验证结果（调用VerificationAgent）
5. 合成最终答案
6. 计算整体置信度

## 3. LangGraph工作流

### 3.1 工作流图

```
[Planning] → [Execution] → [Verification] → [Execution] → ... → [Synthesis] → [END]
                ↑                              │
                └──────────────────────────────┘
```

### 3.2 状态定义

```python
class WorkflowState(TypedDict):
    question: str
    messages: Annotated[List[Dict], add_messages]
    task_plan: Optional[Dict[str, Any]]
    current_step: int
    step_results: List[Dict[str, Any]]
    final_answer: Optional[str]
    errors: List[str]
    metadata: Dict[str, Any]
```

### 3.3 节点说明

1. **Planning Node**: 任务规划
   - 调用PlanningAgent分解任务
   - 生成执行计划

2. **Execution Node**: 步骤执行
   - 调用ExecutionAgent执行当前步骤
   - 更新步骤结果

3. **Verification Node**: 结果验证
   - 调用VerificationAgent验证结果
   - 记录验证信息

4. **Synthesis Node**: 答案合成
   - 整合所有步骤结果
   - 生成最终答案

### 3.4 条件分支

根据执行状态决定下一步：
- `verify`: 需要验证当前步骤
- `continue`: 继续执行下一步
- `synthesize`: 所有步骤完成，合成答案

## 4. 工具系统

### 4.1 工具注册表

统一管理所有工具，支持：
- 工具注册
- 工具检索
- Schema生成（用于LLM function calling）

### 4.2 内置工具

1. **SearchTool**: 网络搜索
   - 使用SerpAPI
   - 支持知识图谱结果
   - 结果提取和格式化

2. **CalculatorTool**: 数学计算
   - 安全计算（限制操作符）
   - 表达式清理
   - 错误处理

### 4.3 工具扩展

可以轻松添加新工具：
```python
class CustomTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="custom_tool",
            description="工具描述"
        )
    
    async def execute(self, input_data):
        # 实现工具逻辑
        pass
```

## 5. 记忆管理

### 5.1 短期记忆 (ShortTermMemory)

- **对话历史**: 使用deque存储，最大100条
- **当前上下文**: 存储临时状态信息
- **消息格式**: `{role, content, timestamp, metadata}`

### 5.2 长期记忆 (LongTermMemory)

- **知识库**: 存储结构化知识
- **模式库**: 存储常见问题模式和解决方案
- **经验库**: 存储成功/失败的案例

### 5.3 记忆检索

- **相似模式匹配**: 查找相似的历史模式
- **相关经验检索**: 基于上下文检索相关经验

## 6. 工作流程示例

### 6.1 示例问题

**问题**: "请分析最近三年人工智能在医疗影像诊断方面的研究进展"

### 6.2 执行流程

1. **Planning阶段**:
   ```
   步骤1: 搜索近三年AI医疗影像诊断相关论文
   步骤2: 提取关键方法、数据集、性能指标
   步骤3: 总结研究进展
   步骤4: 预测未来趋势
   ```

2. **Execution阶段**:
   - 执行步骤1: 调用SearchTool搜索论文
   - 执行步骤2: 从搜索结果中提取信息
   - 执行步骤3: 使用LLM总结
   - 执行步骤4: 使用LLM预测

3. **Verification阶段**:
   - 验证每个步骤的结果
   - 检查信息一致性
   - 评估置信度

4. **Synthesis阶段**:
   - 整合所有步骤结果
   - 生成最终答案和推理过程

## 7. 技术实现

### 7.1 依赖库

- **LangChain**: 基础组件（工具、检索器等）
- **LangGraph**: 工作流编排
- **DashScope**: 阿里云通义千问模型

### 7.2 代码结构

```
src/
├── agent/
│   ├── multi_agent_system.py    # 多Agent系统
│   ├── langgraph_workflow.py    # LangGraph工作流
│   ├── orchestrator.py          # 编排器（整合）
│   └── memory.py                # 记忆管理
├── tools/
│   ├── tool_registry.py         # 工具注册表
│   ├── search_tool.py           # 搜索工具
│   └── calculator_tool.py       # 计算工具
└── main_multi_agent.py          # 主入口
```

## 8. 优势与特点

### 8.1 相比单Agent的优势

1. **专业化**: 每个Agent专注于特定任务
2. **可扩展**: 易于添加新的Agent或工具
3. **可验证**: 每个步骤都有验证机制
4. **可解释**: 完整的推理过程追踪

### 8.2 技术特点

1. **状态管理**: 使用LangGraph显式管理状态
2. **循环控制**: 支持复杂的循环和条件分支
3. **错误处理**: 完善的错误处理和重试机制
4. **记忆持久化**: 支持短期和长期记忆

## 9. 使用示例

```python
from src.agent import AgentOrchestrator

# 初始化（使用多Agent模式）
agent = AgentOrchestrator(use_multi_agent=True)

# 处理问题
result = await agent.process_task(
    "请分析最近三年人工智能在医疗影像诊断方面的研究进展"
)

# 获取结果
print(f"答案: {result['answer']}")
print(f"置信度: {result['confidence']}")
print(f"推理过程: {result['reasoning']}")
```

## 10. 未来优化方向

1. **并行执行**: 支持独立步骤的并行执行
2. **动态重规划**: 根据执行结果动态调整计划
3. **用户交互**: 支持中途询问用户澄清
4. **学习机制**: 从历史经验中学习优化
5. **多模态支持**: 支持图像、表格等多模态输入

---

**最后更新**: 2026-01-28
**文档版本**: 1.0.0
