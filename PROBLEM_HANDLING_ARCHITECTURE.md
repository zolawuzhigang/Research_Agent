# Research Agent - 问题处理架构与异常处理机制

## 📋 目录

1. [问题处理架构](#问题处理架构)
2. [异常处理机制](#异常处理机制)
3. [降级策略](#降级策略)
4. [错误恢复机制](#错误恢复机制)
5. [日志与监控](#日志与监控)

---

## 1. 问题处理架构

### 1.1 分层架构

```
┌─────────────────────────────────────────────┐
│           接口层 (Interface Layer)          │
│  - HTTP API / Console                       │
│  - 输入验证                                 │
│  - 错误格式化                               │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│        编排层 (Orchestration Layer)         │
│  - AgentOrchestrator                        │
│  - 任务路由                                 │
│  - 记忆管理                                 │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│        工作流层 (Workflow Layer)             │
│  - LangGraphWorkflow                        │
│  - 状态管理                                 │
│  - 节点编排                                 │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│        Agent层 (Agent Layer)                │
│  - PlanningAgent (规划)                     │
│  - ExecutionAgent (执行)                     │
│  - VerificationAgent (验证)                  │
│  - CoordinationAgent (协调)                 │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│        工具层 (Tool Layer)                   │
│  - ToolRegistry                             │
│  - SearchTool / CalculatorTool               │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│        LLM层 (LLM Layer)                    │
│  - LLMClient                                 │
│  - API调用                                   │
│  - 响应处理                                  │
└─────────────────────────────────────────────┘
```

### 1.2 问题处理流程

```
问题输入
    │
    ├─ 输入验证 (validate_question)
    │   ├─ 检查空值
    │   ├─ 检查长度
    │   └─ 清理字符串
    │
    ├─ 任务规划 (PlanningAgent)
    │   ├─ 构建规划提示词（包含可用工具列表）
    │   ├─ 调用LLM生成计划
    │   └─ 解析JSON格式的计划
    │
    ├─ 步骤执行 (ExecutionAgent)
    │   ├─ 判断工具类型
    │   ├─ 直接推理 或 工具调用
    │   └─ 处理执行结果
    │
    ├─ 结果验证 (VerificationAgent)
    │   ├─ 验证结果格式
    │   ├─ 计算置信度
    │   └─ 记录问题
    │
    ├─ 答案合成 (CoordinationAgent)
    │   ├─ 整合所有步骤结果
    │   ├─ 如果失败，尝试直接回答
    │   └─ 生成最终答案
    │
    └─ 答案归一化 (normalize_answer)
        ├─ 格式化输出
        └─ 返回结果
```

---

## 2. 异常处理机制

### 2.1 异常处理层次

系统实现了**四层异常处理机制**：

#### 第一层：接口层异常处理

**位置**: `src/api/http_server_fast.py`

```python
@app.post("/api/v1/predict")
async def predict(request: QuestionRequest):
    try:
        # 输入验证
        question = validate_question(request.question)
        
        # 处理任务（带超时）
        result = await asyncio.wait_for(
            agent.process_task(question),
            timeout=300.0
        )
        
        # 处理结果
        answer = normalize_answer(result.get("answer", ""))
        return AnswerResponse(answer=answer)
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="处理超时")
    except ValueError:
        raise HTTPException(status_code=400, detail="输入验证失败")
    except HTTPException:
        raise  # 重新抛出
    except Exception as e:
        logger.exception(f"处理请求时出错: {e}")
        raise HTTPException(status_code=500, detail="处理失败")
```

**特点**:
- ✅ 捕获所有异常，确保服务不崩溃
- ✅ 返回友好的HTTP错误码
- ✅ 记录完整异常堆栈

#### 第二层：编排层异常处理

**位置**: `src/agent/orchestrator.py`

```python
async def process_task(self, task: str, context: Dict) -> Dict[str, Any]:
    try:
        # 路由到工作流
        if self.use_multi_agent and self.workflow:
            result = await self.workflow.run(task, context)
        else:
            result = await self.multi_agent.process(task, context)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing task: {e}")
        return {
            "success": False,
            "error": str(e),
            "task": task
        }
```

**特点**:
- ✅ 统一错误格式
- ✅ 不中断服务
- ✅ 记录错误信息

#### 第三层：Agent层异常处理

**位置**: `src/agent/multi_agent_system.py`

##### 3.1 步骤执行异常

```python
async def execute_step(self, step: Dict, context: Dict) -> Dict[str, Any]:
    try:
        if tool_type == "none":
            result = await self._direct_reasoning(step, context)
        else:
            result = await self._execute_with_tool(step, context)
        return result
    except Exception as e:
        logger.error(f"执行步骤失败: {e}")
        return {
            "step_id": step_id,
            "success": False,
            "error": str(e)
        }
```

**特点**:
- ✅ 步骤失败不影响其他步骤
- ✅ 记录详细错误信息
- ✅ 返回失败标记，继续执行

##### 3.2 直接推理异常

```python
async def _direct_reasoning(self, step: Dict, context: Dict) -> Dict[str, Any]:
    try:
        # 调用LLM
        result = await self.llm.generate_async(prompt)
        
        if not result or not result.strip():
            return {"success": False, "error": "推理结果为空"}
        
        return {"success": True, "result": result.strip()}
        
    except ValueError as e:
        logger.error(f"直接推理参数错误: {e}")
        return {"success": False, "error": f"参数错误: {str(e)}"}
    except Exception as e:
        logger.exception(f"直接推理失败: {e}")
        return {"success": False, "error": f"推理失败: {str(e)}"}
```

**特点**:
- ✅ 区分不同类型的异常
- ✅ 记录完整堆栈
- ✅ 返回结构化错误信息

##### 3.3 工具调用异常

```python
async def _execute_with_tool(self, step: Dict, context: Dict) -> Dict[str, Any]:
    tool = self.tool_registry.get_tool(tool_type)
    
    if not tool:
        # 工具不存在 → 降级到直接推理
        logger.warning(f"工具 {tool_type} 不存在，降级到直接推理")
        return await self._direct_reasoning(step, context)
    
    try:
        tool_result = await tool.execute(tool_input)
        return {...}
    except Exception as e:
        logger.error(f"工具调用失败: {e}")
        # 工具调用失败 → 降级到直接推理
        return await self._direct_reasoning(step, context)
```

**特点**:
- ✅ 自动降级机制
- ✅ 工具失败不影响整体流程
- ✅ 记录降级原因

#### 第四层：LLM/Tool层异常处理

**位置**: `src/llm/llm_client.py`, `src/tools/search_tool.py`

##### 4.1 LLM调用异常

```python
def chat(self, messages: List[Dict]) -> Dict[str, Any]:
    try:
        response = requests.post(self.api_base, ...)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        logger.error("LLM API调用超时")
        raise Exception("LLM API调用超时，请稍后重试")
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"LLM API连接失败: {e}")
        raise Exception(f"无法连接到LLM服务: {str(e)}")
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"LLM API HTTP错误: {e.response.status_code}")
        raise Exception(f"LLM API HTTP错误: {e.response.status_code}")
        
    except json.JSONDecodeError as e:
        logger.error(f"LLM响应JSON解析失败: {e}")
        raise Exception("LLM响应格式错误: JSON解析失败")
```

**特点**:
- ✅ 区分不同类型的网络异常
- ✅ 记录详细的错误信息（状态码、响应内容）
- ✅ 抛出明确的异常信息

##### 4.2 工具执行异常

```python
async def execute(self, query: str) -> Dict[str, Any]:
    try:
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(self.base_url, params=params, timeout=10)
        )
        response.raise_for_status()
        return {"success": True, "results": [...]}
        
    except requests.exceptions.Timeout:
        return {"success": False, "error": "搜索请求超时"}
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"搜索请求失败: {str(e)}"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**特点**:
- ✅ 工具异常不向上抛出
- ✅ 返回结构化错误信息
- ✅ 允许调用方决定如何处理

---

## 3. 降级策略

### 3.1 工具降级

```
工具调用
    │
    ├─ 工具不存在
    │   └─ 降级到直接推理
    │       └─ _direct_reasoning()
    │
    ├─ 工具调用失败
    │   └─ 降级到直接推理
    │       └─ _direct_reasoning()
    │
    └─ 工具输入无效（计算器）
        └─ 降级到直接推理
            └─ _direct_reasoning()
```

### 3.2 答案生成降级

```
答案合成
    │
    ├─ 有成功步骤
    │   └─ 使用LLM整合所有成功步骤的结果
    │
    ├─ 所有步骤失败
    │   └─ 尝试直接回答用户问题
    │       ├─ 构建简单提示词
    │       ├─ 调用LLM
    │       └─ 如果成功 → 返回答案
    │       └─ 如果失败 → "抱歉，我无法回答这个问题。"
    │
    └─ 没有步骤结果
        └─ "无法生成答案"
```

### 3.3 工作流降级

```
工作流选择
    │
    ├─ LangGraph可用
    │   └─ 使用完整LangGraph工作流
    │
    └─ LangGraph不可用
        └─ 使用简化工作流 (_simple_workflow)
            └─ 顺序执行各个节点
```

### 3.4 异步方法降级

```
LLM调用
    │
    ├─ generate_async() 可用
    │   └─ 使用异步方法
    │
    └─ generate_async() 不可用
        └─ 使用同步方法（在线程池中）
            ├─ asyncio.to_thread() (Python 3.9+)
            └─ run_in_executor() (Python 3.8)
```

---

## 4. 错误恢复机制

### 4.1 步骤级错误恢复

**策略**: 步骤失败不影响其他步骤

```python
for step in steps:
    try:
        step_result = await execution_agent.execute_step(step, context)
        self.state["step_results"].append(step_result)
    except Exception as e:
        # 记录错误，继续执行下一步
        logger.error(f"步骤 {step.get('id')} 执行失败: {e}")
        self.state["step_results"].append({
            "step_id": step.get("id"),
            "success": False,
            "error": str(e)
        })
        self.state["errors"].append(f"步骤 {step.get('id')} 失败: {str(e)}")
```

### 4.2 工具级错误恢复

**策略**: 工具失败自动降级

```python
try:
    tool_result = await tool.execute(tool_input)
    return {...}
except Exception as e:
    # 降级到直接推理
    logger.warning("工具调用失败，降级到直接推理")
    return await self._direct_reasoning(step, context)
```

### 4.3 整体级错误恢复

**策略**: 所有步骤失败时，尝试直接回答

```python
successful_results = [r for r in step_results if r.get("success")]

if not successful_results:
    # 所有步骤失败，尝试直接回答
    question = self.state.get('question', '')
    if question and self.planning_agent.llm:
        try:
            answer = await self.planning_agent.llm.generate_async(
                f"请直接回答以下问题：{question}"
            )
            if answer:
                return answer.strip()
        except Exception:
            pass
    
    return "抱歉，我无法回答这个问题。"
```

---

## 5. 日志与监控

### 5.1 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| **DEBUG** | 详细调试信息 | API请求详情、响应内容 |
| **INFO** | 关键步骤信息 | 步骤执行、工具调用 |
| **WARNING** | 警告信息 | 工具不可用、降级操作 |
| **ERROR** | 错误信息 | 执行失败、API错误 |
| **EXCEPTION** | 异常堆栈 | 使用 `logger.exception()` |

### 5.2 关键日志点

```python
# 1. 请求入口
logger.info(f"Processing task: {task}")

# 2. 步骤执行
logger.info(f"[步骤{step_id}] 工具类型: {tool_type}")
logger.info(f"[步骤{step_id}] 开始调用LLM进行推理...")
logger.info(f"[步骤{step_id}] LLM调用完成，结果长度: {len(result)}")

# 3. 工具调用
logger.info(f"SearchTool: 搜索 - {query}")
logger.warning("SERPAPI_KEY未设置，使用模拟结果")

# 4. 异常记录
logger.exception(f"处理请求时出错: {e}")  # 记录完整堆栈
logger.error(f"[步骤{step_id}] 工具调用失败: {e}")

# 5. 降级操作
logger.warning(f"[步骤{step_id}] 工具 {tool_type} 不存在，降级到直接推理")
```

### 5.3 结构化日志

```python
# 建议的日志格式（用于SLS等日志服务）
log_entry = {
    "timestamp": time.time(),
    "step": "planning|execution|verification|synthesis",
    "message": "描述信息",
    "data": {
        "step_id": 1,
        "tool_type": "search_web",
        "result_length": 100
    }
}
print(f"[AGENT_LOG] {json.dumps(log_entry)}")
```

---

## 6. 当前问题与解决方案

### 6.1 已知问题

#### 问题1: 步骤执行失败但无详细错误

**现象**: 步骤返回 `success=False`，但没有看到异常日志

**可能原因**:
- LLM调用失败，但异常被捕获
- 结果为空，但没有记录原因

**解决方案**:
- ✅ 已添加详细日志（`[步骤X] 开始调用LLM...`）
- ✅ 已添加结果预览日志
- ✅ 使用 `logger.exception()` 记录完整堆栈

#### 问题2: 工具类型不匹配

**现象**: LLM规划时生成不存在的工具类型

**解决方案**:
- ✅ 在规划提示词中明确列出可用工具类型
- ✅ 添加工具类型说明
- ✅ 工具不存在时自动降级到直接推理

#### 问题3: 计算器工具误用

**现象**: 非数学任务被分配了计算器工具

**解决方案**:
- ✅ 改进工具输入准备逻辑
- ✅ 添加数学表达式提取
- ✅ 输入无效时降级到直接推理

### 6.2 改进方向

1. **增强错误诊断**:
   - 添加错误分类（网络错误、格式错误、逻辑错误等）
   - 实现错误统计和报告

2. **改进重试机制**:
   - 对临时性错误（如网络超时）实现自动重试
   - 添加指数退避策略

3. **增强监控**:
   - 添加性能指标（响应时间、成功率等）
   - 实现健康检查端点

4. **优化降级策略**:
   - 实现更智能的降级决策
   - 添加降级原因追踪

---

## 7. 最佳实践

### 7.1 异常处理

✅ **应该做的**:
- 在每一层都捕获异常
- 记录详细的错误信息
- 返回友好的错误消息
- 实现降级机制

❌ **不应该做的**:
- 静默吞掉异常
- 返回空结果而不说明原因
- 让异常向上传播导致服务崩溃

### 7.2 日志记录

✅ **应该做的**:
- 在关键步骤记录日志
- 使用适当的日志级别
- 记录结构化信息（步骤ID、工具类型等）
- 使用 `logger.exception()` 记录异常堆栈

❌ **不应该做的**:
- 记录敏感信息（如API密钥）
- 过度记录（影响性能）
- 使用错误的日志级别

### 7.3 错误恢复

✅ **应该做的**:
- 实现多层降级机制
- 确保总是返回一个答案
- 记录降级原因
- 允许部分失败

❌ **不应该做的**:
- 一个错误就中断整个流程
- 不提供降级选项
- 返回空结果

---

## 8. 总结

当前demo实现了**完善的异常处理和降级机制**：

### ✅ 优点

1. **多层异常处理**: 从接口层到工具层，每一层都有异常处理
2. **智能降级**: 工具失败时自动降级到直接推理
3. **详细日志**: 记录关键步骤和错误信息
4. **优雅失败**: 即使失败也返回友好的错误消息

### ⚠️ 待改进

1. **错误分类**: 需要更细粒度的错误分类
2. **重试机制**: 对临时性错误实现自动重试
3. **监控指标**: 添加性能指标和健康检查

### 🎯 架构优势

- **模块化设计**: 每个组件职责清晰
- **可扩展性**: 易于添加新工具和新Agent
- **容错性**: 多层降级确保系统稳定

---

**文档版本**: 1.0.0  
**最后更新**: 2026-01-28
