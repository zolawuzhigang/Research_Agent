# 多Agent系统使用示例

## 1. 快速开始

### 1.1 基本使用

```python
import asyncio
from src.agent import AgentOrchestrator

async def main():
    # 初始化Agent（使用多Agent模式）
    agent = AgentOrchestrator(use_multi_agent=True)
    
    # 处理问题
    result = await agent.process_task("法国首都在哪里？")
    
    # 输出结果
    print(f"答案: {result['answer']}")
    print(f"置信度: {result.get('confidence', 0.0):.2f}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 1.2 带上下文的使用

```python
async def main():
    agent = AgentOrchestrator(use_multi_agent=True)
    
    # 第一次对话
    result1 = await agent.process_task("什么是人工智能？")
    print(f"答案1: {result1['answer']}")
    
    # 第二次对话（会记住上下文）
    result2 = await agent.process_task("它有哪些应用？")
    print(f"答案2: {result2['answer']}")
    
    # 查看对话历史
    history = agent.get_conversation_history()
    print(f"对话历史: {len(history)} 条消息")
```

## 2. 复杂问题示例

### 2.1 多跳推理问题

```python
async def complex_question():
    agent = AgentOrchestrator(use_multi_agent=True)
    
    question = """
    请分析最近三年人工智能在医疗影像诊断方面的研究进展，
    并预测未来趋势。
    """
    
    result = await agent.process_task(question)
    
    print(f"答案: {result['answer']}")
    print(f"\n推理过程:\n{result.get('reasoning', '')}")
    print(f"\n置信度: {result.get('confidence', 0.0):.2f}")
```

### 2.2 需要计算的问题

```python
async def calculation_question():
    agent = AgentOrchestrator(use_multi_agent=True)
    
    question = "如果一辆车以每小时60公里的速度行驶，3小时后行驶了多少公里？"
    
    result = await agent.process_task(question)
    print(f"答案: {result['answer']}")
```

## 3. 自定义工具

### 3.1 添加自定义工具

```python
from src.tools import BaseTool, ToolRegistry

class CustomTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="custom_tool",
            description="自定义工具描述"
        )
    
    async def execute(self, input_data: str) -> dict:
        # 实现工具逻辑
        return {
            "success": True,
            "result": f"处理了: {input_data}"
        }

# 注册工具
tool_registry = ToolRegistry()
tool_registry.register(CustomTool())

# 在Agent中使用
agent = AgentOrchestrator(use_multi_agent=True)
# 工具会自动注册到ExecutionAgent
```

## 4. 直接使用多Agent系统

### 4.1 使用MultiAgentSystem

```python
from src.agent import MultiAgentSystem

async def main():
    # 初始化多Agent系统
    system = MultiAgentSystem()
    
    # 处理问题
    result = await system.process("复杂问题")
    
    print(f"答案: {result['answer']}")
    print(f"置信度: {result['confidence']}")
```

### 4.2 使用LangGraph工作流

```python
from src.agent import LangGraphWorkflow, PlanningAgent, ExecutionAgent, VerificationAgent

async def main():
    # 初始化各个Agent
    planning = PlanningAgent()
    execution = ExecutionAgent()
    verification = VerificationAgent()
    
    # 创建工作流
    workflow = LangGraphWorkflow(agents={
        "planning": planning,
        "execution": execution,
        "verification": verification
    })
    
    # 运行工作流
    result = await workflow.run("用户问题")
    print(f"答案: {result['answer']}")
```

## 5. 记忆管理

### 5.1 使用记忆管理器

```python
from src.agent import MemoryManager

# 初始化记忆管理器
memory = MemoryManager(short_term_size=100)

# 添加对话
memory.add_conversation("user", "你好")
memory.add_conversation("assistant", "你好！有什么可以帮助你的？")

# 获取对话历史
history = memory.get_conversation_context(n=10)
print(f"最近10条消息: {history}")

# 存储知识
memory.store_knowledge("fact", "巴黎是法国首都", {"source": "wikipedia"})

# 检索知识
knowledge = memory.retrieve_knowledge("fact")
print(f"知识: {knowledge}")
```

## 6. 错误处理

### 6.1 处理执行错误

```python
async def handle_errors():
    agent = AgentOrchestrator(use_multi_agent=True)
    
    result = await agent.process_task("问题")
    
    if not result.get("success"):
        print(f"处理失败: {result.get('error')}")
        print(f"错误列表: {result.get('errors', [])}")
    else:
        print(f"处理成功: {result['answer']}")
```

## 7. 批量处理

### 7.1 处理多个问题

```python
async def batch_process():
    agent = AgentOrchestrator(use_multi_agent=True)
    
    questions = [
        "问题1",
        "问题2",
        "问题3"
    ]
    
    results = []
    for question in questions:
        result = await agent.process_task(question)
        results.append({
            "question": question,
            "answer": result.get("answer"),
            "confidence": result.get("confidence", 0.0)
        })
    
    # 输出结果
    for r in results:
        print(f"Q: {r['question']}")
        print(f"A: {r['answer']} (置信度: {r['confidence']:.2f})")
```

## 8. 配置选项

### 8.1 自定义配置

```python
config = {
    "memory": {
        "short_term_size": 200  # 增加短期记忆大小
    },
    "react": {
        "max_iterations": 10  # 增加最大迭代次数
    }
}

agent = AgentOrchestrator(config=config, use_multi_agent=True)
```

## 9. 调试和日志

### 9.1 查看详细日志

```python
from loguru import logger

# 设置日志级别
logger.add("logs/agent.log", level="DEBUG")

agent = AgentOrchestrator(use_multi_agent=True)
result = await agent.process_task("问题")

# 日志会自动记录到文件
```

### 9.2 查看状态

```python
agent = AgentOrchestrator(use_multi_agent=True)
result = await agent.process_task("问题")

# 获取Agent状态（如果使用MultiAgentSystem）
if hasattr(agent, 'multi_agent'):
    state = agent.multi_agent.get_state()
    print(f"当前步骤: {state.get('current_step')}")
    print(f"步骤结果: {len(state.get('step_results', []))}")
```

## 10. 完整示例

```python
import asyncio
from src.agent import AgentOrchestrator
from loguru import logger

async def complete_example():
    # 配置日志
    logger.add("logs/agent.log", rotation="10 MB")
    
    # 初始化Agent
    agent = AgentOrchestrator(
        config={
            "memory": {"short_term_size": 100}
        },
        use_multi_agent=True
    )
    
    # 处理复杂问题
    question = """
    请分析最近三年人工智能在医疗影像诊断方面的研究进展，
    包括主要方法、数据集和性能指标，并预测未来趋势。
    """
    
    logger.info(f"处理问题: {question}")
    result = await agent.process_task(question)
    
    # 输出结果
    if result.get("success"):
        print("=" * 50)
        print("问题:", question)
        print("=" * 50)
        print("答案:", result["answer"])
        print("置信度:", f"{result.get('confidence', 0.0):.2f}")
        print("\n推理过程:")
        print(result.get("reasoning", ""))
        
        if result.get("errors"):
            print("\n警告:")
            for error in result["errors"]:
                print(f"  - {error}")
    else:
        print(f"处理失败: {result.get('error')}")
    
    # 查看对话历史
    history = agent.get_conversation_history()
    print(f"\n对话历史: {len(history)} 条消息")

if __name__ == "__main__":
    asyncio.run(complete_example())
```

---

**更多示例**: 参考 `src/main_multi_agent.py`
