# Research Agent 技术设计文档

## 1. 系统架构

### 1.0 多Agent系统架构（核心设计）

基于DeepSeek的设计思路，我们采用**多Agent协作系统**来解决多跳推理、信息验证和工具依赖等复杂问题。

#### 1.0.1 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                   CoordinationAgent                         │
│              (协调Agent - 整体流程控制)                      │
└───────────────┬─────────────────────────────────────────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│规划Agent│  │执行Agent│  │验证Agent│
│Planning │  │Execution│  │Verification│
└───┬───┘  └───┬───┘  └───┬───┘
    │           │           │
    │      ┌────┴────┐      │
    │      │工具注册表│      │
    │      │ToolRegistry│    │
    │      └────┬────┘      │
    │           │           │
    └───────────┼───────────┘
                │
    ┌───────────▼───────────┐
    │    LangGraph工作流     │
    │   (状态机编排)          │
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │    记忆管理器           │
    │  (短期+长期记忆)         │
    └────────────────────────┘
```

#### 1.0.2 核心Agent说明

**1. PlanningAgent (规划Agent)**
- **职责**: 任务分解和计划制定
- **能力**: 
  - 理解复杂问题
  - 将问题分解为3-8个子任务
  - 识别步骤间的依赖关系
  - 生成DAG式任务流
  - 支持动态重规划

**2. ExecutionAgent (执行Agent)**
- **职责**: 执行具体任务步骤
- **能力**:
  - 调用各种工具（搜索、计算等）
  - 直接推理（不使用工具）
  - 处理工具调用错误
  - 收集执行结果

**3. VerificationAgent (验证Agent)**
- **职责**: 验证信息准确性和一致性
- **能力**:
  - 基本验证（结果格式、完整性）
  - 一致性检查（多结果对比）
  - 交叉验证（多源验证）
  - 逻辑检查（数值合理性、因果关系）
  - 置信度评估

**4. CoordinationAgent (协调Agent)**
- **职责**: 协调多个Agent的工作
- **能力**:
  - 管理整体流程
  - 检查步骤依赖
  - 合成最终答案
  - 计算整体置信度

#### 1.0.3 LangGraph工作流

使用LangGraph构建状态机工作流，支持：
- **循环执行**: 执行→验证→继续执行
- **条件分支**: 根据验证结果决定下一步
- **状态管理**: 显式管理Agent状态
- **错误处理**: 失败重试和降级策略

工作流节点：
1. **Planning Node**: 任务规划
2. **Execution Node**: 步骤执行
3. **Verification Node**: 结果验证
4. **Synthesis Node**: 答案合成

#### 1.0.4 记忆管理

- **短期记忆**: 对话历史、当前上下文（deque，最大100条）
- **长期记忆**: 知识库、模式、经验（持久化存储）

### 1.1 整体架构（单Agent模式 - 向后兼容）

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Input Node                      │
│              (接收用户问题，解析请求)                     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              ReAct规划引擎 (Python节点)                  │
│  - 任务理解与分解                                        │
│  - 推理循环控制                                          │
│  - 工具调用决策                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐
│  搜索工具    │ │ 计算工具   │ │ 其他工具   │
│  (SerpAPI)   │ │ (Calculator)│ │ (Date/Unit)│
└───────┬──────┘ └─────┬─────┘ └─────┬─────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              答案合成器 (Python节点)                     │
│  - 整合多源信息                                          │
│  - 生成最终答案                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│           答案归一化处理器 (Python节点)                  │
│  - 格式标准化                                            │
│  - 数值处理                                              │
│  - 多实体格式化                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                    HTTP Output Node                      │
│              (返回最终答案JSON格式)                       │
└─────────────────────────────────────────────────────────┘
```

### 1.2 数据流

```
用户问题 (JSON)
  ↓
解析问题文本
  ↓
ReAct循环:
  ├─ Thought: 分析问题
  ├─ Action: 选择工具
  ├─ Observation: 获取结果
  └─ 判断是否需要继续
  ↓
答案合成
  ↓
答案归一化
  ↓
返回JSON响应
```

## 2. 核心模块设计

### 2.1 ReAct规划引擎

**设计思路**: 采用ReAct（Reasoning + Acting）框架，引导模型进行逐步思考并决定何时调用工具。

**核心提示词模板**:

```python
SYSTEM_PROMPT = """你是一个严谨的研究助手(Research Agent)。请严格按照以下步骤回答用户问题：

1. **思考(Thought)**: 分析问题本质，确定需要哪些信息，以及如何获取（如是否需要搜索、计算等）。
2. **行动(Action)**: 如果需要工具，则调用相应工具。格式：`tool_name|tool_input`。如果不需要工具，则写 `None`。
3. **观察(Observation)**: 分析工具返回的结果。
4. 重复步骤1-3，直到你确信可以给出准确答案。
5. **最终回答(Answer)**: 仅输出最终的、简洁的答案，不要包含任何推理过程或多余解释。

请严格使用以下格式：
Thought: <你的思考>
Action: <工具名>|<工具输入> 或 None
Observation: <工具返回结果或 None>
... (此模式可重复)
Answer: <最终答案>

示例：
Question: 法国首都在哪里？
Thought: 这是一个关于地理知识的问题，我需要搜索法国首都的信息。
Action: search_web|法国首都
Observation: 巴黎是法国的首都和最大城市...
Answer: 巴黎
"""

def create_react_prompt(question: str, conversation_history: list = None) -> str:
    """
    创建ReAct提示词
    
    Args:
        question: 用户问题
        conversation_history: 对话历史（用于多轮对话）
    
    Returns:
        完整的提示词
    """
    prompt = SYSTEM_PROMPT + "\n\n"
    
    if conversation_history:
        prompt += "对话历史:\n"
        for turn in conversation_history:
            prompt += f"Q: {turn['question']}\nA: {turn['answer']}\n"
        prompt += "\n"
    
    prompt += f"Question: {question}\n"
    return prompt
```

**Python节点实现示例**:

```python
import json
import time
from typing import Dict, Any, List, Optional

def log(step: str, message: str, data: Any = None):
    """结构化日志输出"""
    log_entry = {
        "timestamp": time.time(),
        "step": step,
        "message": message,
        "data": data
    }
    print(f"[AGENT_LOG] {json.dumps(log_entry, ensure_ascii=False)}")

def react_engine(question: str, max_iterations: int = 5) -> Dict[str, Any]:
    """
    ReAct引擎核心逻辑
    
    Args:
        question: 用户问题
        max_iterations: 最大迭代次数
    
    Returns:
        包含最终答案的字典
    """
    log("react_start", "开始ReAct推理", {"question": question})
    
    conversation_history = []
    current_thought = ""
    current_action = None
    observations = []
    
    for iteration in range(max_iterations):
        log("react_iteration", f"第{iteration+1}次迭代")
        
        # 构建当前上下文
        context = build_context(question, conversation_history, observations)
        
        # 调用LLM进行推理
        llm_response = call_llm(context)
        
        # 解析LLM响应
        parsed = parse_react_response(llm_response)
        
        if parsed.get("answer"):
            # 找到最终答案
            log("react_complete", "找到最终答案", {"answer": parsed["answer"]})
            return {
                "success": True,
                "answer": parsed["answer"],
                "iterations": iteration + 1,
                "reasoning": observations
            }
        
        # 执行Action
        if parsed.get("action") and parsed["action"] != "None":
            tool_name, tool_input = parse_action(parsed["action"])
            observation = call_tool(tool_name, tool_input)
            observations.append(observation)
            log("tool_call", f"调用工具: {tool_name}", {"input": tool_input, "output": observation})
        else:
            # 没有Action，可能可以直接回答
            if parsed.get("thought"):
                # 基于思考直接生成答案
                final_answer = generate_answer_from_thought(parsed["thought"], observations)
                if final_answer:
                    return {
                        "success": True,
                        "answer": final_answer,
                        "iterations": iteration + 1,
                        "reasoning": observations
                    }
    
    # 达到最大迭代次数
    log("react_timeout", "达到最大迭代次数")
    return {
        "success": False,
        "error": "达到最大迭代次数，未能生成答案",
        "observations": observations
    }

def parse_react_response(response: str) -> Dict[str, Any]:
    """解析ReAct格式的响应"""
    result = {
        "thought": "",
        "action": None,
        "observation": None,
        "answer": None
    }
    
    lines = response.strip().split("\n")
    for line in lines:
        if line.startswith("Thought:"):
            result["thought"] = line.replace("Thought:", "").strip()
        elif line.startswith("Action:"):
            action_str = line.replace("Action:", "").strip()
            result["action"] = action_str if action_str != "None" else None
        elif line.startswith("Observation:"):
            result["observation"] = line.replace("Observation:", "").strip()
        elif line.startswith("Answer:"):
            result["answer"] = line.replace("Answer:", "").strip()
    
    return result

def parse_action(action_str: str) -> tuple:
    """解析Action字符串，提取工具名和输入"""
    if "|" in action_str:
        tool_name, tool_input = action_str.split("|", 1)
        return tool_name.strip(), tool_input.strip()
    return action_str.strip(), ""
```

### 2.2 工具集成

#### 2.2.1 搜索引擎工具

**SerpAPI集成示例**:

```python
import requests
from typing import Dict, Any, Optional

def search_web(query: str, api_key: str = None) -> Dict[str, Any]:
    """
    使用SerpAPI进行网络搜索
    
    Args:
        query: 搜索查询
        api_key: SerpAPI密钥
    
    Returns:
        搜索结果
    """
    if not api_key:
        api_key = os.getenv("SERPAPI_KEY")
    
    url = "https://serpapi.com/search"
    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "hl": "zh-cn",
        "gl": "cn"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 提取关键信息
        results = []
        if "organic_results" in data:
            for item in data["organic_results"][:5]:  # 取前5个结果
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "link": item.get("link", "")
                })
        
        # 如果有知识图谱结果，优先使用
        if "knowledge_graph" in data:
            kg = data["knowledge_graph"]
            results.insert(0, {
                "title": kg.get("title", ""),
                "snippet": kg.get("description", ""),
                "type": "knowledge_graph"
            })
        
        return {
            "success": True,
            "results": results,
            "query": query
        }
    except Exception as e:
        log("search_error", f"搜索失败: {str(e)}", {"query": query})
        return {
            "success": False,
            "error": str(e),
            "results": []
        }
```

#### 2.2.2 计算工具

```python
def calculate(expression: str) -> Dict[str, Any]:
    """
    执行数学计算
    
    Args:
        expression: 数学表达式
    
    Returns:
        计算结果
    """
    try:
        # 安全计算，只允许数学表达式
        import re
        # 移除危险字符
        safe_expr = re.sub(r'[^0-9+\-*/().\s]', '', expression)
        result = eval(safe_expr)
        return {
            "success": True,
            "result": result,
            "expression": expression
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

#### 2.2.3 工具注册与调用

```python
class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools = {}
        self.register_default_tools()
    
    def register_default_tools(self):
        """注册默认工具"""
        self.register("search_web", search_web, "网络搜索工具")
        self.register("calculate", calculate, "数学计算工具")
        # 可以注册更多工具
    
    def register(self, name: str, func: callable, description: str):
        """注册工具"""
        self.tools[name] = {
            "func": func,
            "description": description
        }
    
    def call(self, tool_name: str, tool_input: str) -> Dict[str, Any]:
        """调用工具"""
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具 {tool_name} 不存在"
            }
        
        try:
            tool = self.tools[tool_name]
            result = tool["func"](tool_input)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# 全局工具注册表
tool_registry = ToolRegistry()

def call_tool(tool_name: str, tool_input: str) -> str:
    """调用工具并返回格式化结果"""
    result = tool_registry.call(tool_name, tool_input)
    
    if result.get("success"):
        # 格式化结果供模型阅读
        if tool_name == "search_web":
            results = result.get("results", [])
            formatted = "\n".join([
                f"- {r.get('title', '')}: {r.get('snippet', '')}"
                for r in results[:3]
            ])
            return formatted
        elif tool_name == "calculate":
            return str(result.get("result", ""))
        else:
            return str(result)
    else:
        return f"工具调用失败: {result.get('error', '未知错误')}"
```

### 2.3 答案归一化处理器

**核心功能**: 将模型输出的原始答案处理成符合赛题评分标准的格式。

```python
import re
from typing import Optional

def normalize_answer(raw_answer: str) -> str:
    """
    对答案进行归一化处理，匹配赛题要求
    
    Args:
        raw_answer: 模型原始输出
    
    Returns:
        归一化后的答案
    """
    if raw_answer is None:
        return ""
    
    # 1. 转为小写
    normalized = raw_answer.lower()
    
    # 2. 去除首尾空格
    normalized = normalized.strip()
    
    # 3. 提取答案（如果包含"Answer:"前缀，提取后面的内容）
    if "answer:" in normalized:
        normalized = normalized.split("answer:")[-1].strip()
    
    # 4. 处理数值格式
    # 尝试提取数字（包括可能包含的千位分隔符）
    number_match = re.search(r'(\d[\d,]*\.?\d*)', normalized)
    if number_match:
        num_str = number_match.group(1).replace(',', '')
        try:
            if '.' in num_str:
                # 浮点数：根据题目可能需要四舍五入或取整
                # 这里默认取整，可根据实际情况调整
                num_value = float(num_str)
                normalized = str(int(round(num_value)))
            else:
                # 整数：直接使用
                normalized = num_str
        except ValueError:
            pass
    
    # 5. 规范多实体分隔符
    # 将中文顿号、分号、连续逗号等统一为 ", "
    normalized = re.sub(r'[；、，]+', ', ', normalized)
    normalized = re.sub(r',\s*,', ',', normalized)  # 处理连续逗号
    normalized = normalized.strip(', ')  # 再次清理
    
    # 6. 移除多余的标点和空格
    normalized = re.sub(r'\s+', ' ', normalized)  # 多个空格合并为一个
    normalized = normalized.strip()
    
    # 7. 处理特殊格式
    # 移除引号
    normalized = normalized.strip('"\'')
    
    return normalized

# 测试用例
def test_normalize_answer():
    """测试答案归一化函数"""
    test_cases = [
        ("Answer: 巴黎", "巴黎"),
        ("答案：140", "140"),
        ("北京, 上海, 广州", "北京, 上海, 广州"),
        ("1,234.56", "1235"),  # 浮点数取整
        ("   France  ", "france"),
        ("答案：\"北京\"", "北京"),
    ]
    
    for input_val, expected in test_cases:
        result = normalize_answer(input_val)
        print(f"Input: {input_val} -> Output: {result} (Expected: {expected})")
        assert result == expected.lower(), f"Failed: {input_val}"
    
    print("All tests passed!")
```

### 2.4 LLM调用封装

```python
import os
from typing import Dict, Any, Optional

def call_llm(prompt: str, model_name: str = "qwen-max", **kwargs) -> str:
    """
    调用Qwen模型
    
    Args:
        prompt: 提示词
        model_name: 模型名称
        **kwargs: 其他参数（temperature, max_tokens等）
    
    Returns:
        模型响应
    """
    # 这里需要根据PAI-LangStudio的实际API进行调整
    # 示例使用dashscope SDK
    
    try:
        import dashscope
        from dashscope import Generation
        
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY not set")
        
        dashscope.api_key = api_key
        
        response = Generation.call(
            model=model_name,
            prompt=prompt,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 2000),
            top_p=kwargs.get("top_p", 0.8)
        )
        
        if response.status_code == 200:
            return response.output.text
        else:
            raise Exception(f"API调用失败: {response.message}")
    
    except ImportError:
        # 如果在PAI-LangStudio中，可能需要使用不同的调用方式
        # 这里需要根据实际平台API调整
        log("llm_error", "LLM调用失败，请检查API配置")
        return ""
```

## 3. 关键配置

### 3.1 LangStudio工作流节点配置

**节点连接顺序**:
1. HTTP Input Node → 接收请求
2. Python Node (解析) → 解析问题
3. Python Node (ReAct引擎) → 核心推理
4. 循环判断节点 → 判断是否需要继续
5. 工具调用节点 → 执行工具
6. Python Node (结果处理) → 处理工具结果
7. Python Node (答案归一化) → 格式化答案
8. HTTP Output Node → 返回响应

### 3.2 模型参数配置

```yaml
model:
  name: "qwen-max"
  temperature: 0.1  # 低随机性以保证稳定性
  max_tokens: 2000
  top_p: 0.8
  timeout: 30
```

### 3.3 ReAct参数配置

```yaml
react:
  max_iterations: 5  # 最大迭代次数
  max_tool_calls: 10  # 最大工具调用次数
  timeout: 300  # 超时时间（秒）
```

## 4. 性能优化策略

### 4.1 提示词优化

- **Few-shot示例**: 在提示词中添加典型问题的示例
- **角色设定**: 明确Agent的角色和能力边界
- **格式约束**: 严格约束输出格式，便于解析

### 4.2 工具调用优化

- **智能搜索**: 优化搜索词提取，提高搜索准确性
- **结果过滤**: 对搜索结果进行相关性过滤
- **缓存机制**: 对常见问题缓存搜索结果

### 4.3 答案处理优化

- **多轮验证**: 对关键答案进行多轮验证
- **格式检查**: 严格检查答案格式
- **异常处理**: 处理各种边界情况

## 5. 错误处理与日志

### 5.1 错误处理策略

```python
def handle_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """统一错误处理"""
    log("error", f"发生错误: {str(error)}", context)
    
    # 根据错误类型采取不同策略
    if isinstance(error, TimeoutError):
        return {"success": False, "error": "请求超时", "retry": True}
    elif isinstance(error, ValueError):
        return {"success": False, "error": "参数错误", "retry": False}
    else:
        return {"success": False, "error": "未知错误", "retry": True}
```

### 5.2 日志规范

所有关键步骤都应记录结构化日志：

```python
log("step_name", "描述信息", {"key": "value"})
```

日志格式：`[AGENT_LOG] {"timestamp": ..., "step": ..., "message": ..., "data": ...}`

## 6. 测试与验证

### 6.1 单元测试

对核心函数进行单元测试：
- `normalize_answer()`: 答案归一化测试
- `parse_react_response()`: ReAct响应解析测试
- `search_web()`: 搜索工具测试

### 6.2 集成测试

在验证集上进行端到端测试，记录：
- 每题的推理过程
- 工具调用情况
- 最终答案和正确率

---

**最后更新**: 2026-01-28
**文档版本**: 1.0.0
