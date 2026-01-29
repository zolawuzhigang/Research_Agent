# 多工具组合调用能力优化方案

## 当前能力总结

### ✅ 已具备的能力
1. **任务分解**: PlanningAgent 可以将复杂问题分解为多个步骤
2. **顺序执行**: ExecutionAgent 可以按顺序执行每个步骤
3. **依赖检查**: CoordinationAgent 会检查步骤的依赖关系
4. **基本数据传递**: 步骤结果会传递到 context 中

### ⚠️ 需要优化的地方

#### 1. 步骤间数据传递不够智能
**当前问题**:
- `_prepare_tool_input()` 只使用最后一个步骤的结果
- 没有根据步骤描述智能选择需要的结果
- 没有明确引用特定步骤的结果

**优化方案**:
- 增强 `_prepare_tool_input()` 以智能提取和引用前面步骤的结果
- 支持步骤结果的命名引用（如 `step_1_result`, `step_2_data`）
- 自动将前面步骤的结果格式化为当前工具需要的输入格式

#### 2. 依赖关系处理不够完善
**当前问题**:
- 只支持简单的依赖检查（所有依赖必须满足）
- 不支持部分依赖（OR依赖）
- 不支持条件依赖

**优化方案**:
- 实现更完善的依赖检查（包括循环依赖检测）
- 支持部分依赖（OR依赖）
- 支持条件依赖（如果步骤1成功，执行步骤2；否则执行步骤3）

#### 3. 并行执行支持有限
**当前问题**:
- 虽然规划阶段支持 `parallel_groups`，但执行阶段是顺序执行
- 没有真正利用并行执行提升性能

**优化方案**:
- 对于 `parallel_groups` 中的步骤，真正并行执行
- 使用 `asyncio.gather()` 并发执行独立步骤

## 优化实现

### 优化1: 增强步骤间数据传递

#### 1.1 智能提取前面步骤的结果

```python
def _prepare_tool_input(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> str:
    """准备工具输入（增强版）"""
    tool_type = step.get("tool_type", "")
    description = step.get("description", "")
    step_id = step.get("id")
    
    if not description:
        logger.warning("步骤描述为空，无法准备工具输入")
        return ""
    
    # 提取前面步骤的结果
    previous_results = self._extract_previous_results(step, context)
    
    # 根据工具类型准备不同的输入
    if tool_type == "calculate":
        return self._prepare_calculate_input(description, previous_results)
    elif tool_type == "search_web":
        return self._prepare_search_input(description, previous_results)
    # ... 其他工具类型
    
    # 默认：智能组合描述和前面步骤的结果
    return self._smart_combine_input(description, previous_results, tool_type)

def _extract_previous_results(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[int, Any]:
    """提取前面步骤的结果"""
    if not context:
        return {}
    
    step_results = context.get("step_results", [])
    results = {}
    
    for result in step_results:
        step_id = result.get("step_id")
        if step_id and result.get("success"):
            results[step_id] = result.get("result")
    
    return results

def _smart_combine_input(self, description: str, previous_results: Dict[int, Any], tool_type: str) -> str:
    """智能组合输入：将描述和前面步骤的结果组合"""
    # 检查描述中是否提到步骤编号（如 "使用步骤1的结果"）
    import re
    step_refs = re.findall(r'步骤(\d+)|step\s*(\d+)', description, re.IGNORECASE)
    
    if step_refs:
        # 提取引用的步骤编号
        referenced_steps = []
        for match in step_refs:
            step_num = int(match[0] or match[1])
            if step_num in previous_results:
                referenced_steps.append((step_num, previous_results[step_num]))
        
        if referenced_steps:
            # 使用引用的步骤结果
            if len(referenced_steps) == 1:
                return str(referenced_steps[0][1])[:500]
            else:
                # 多个步骤结果，组合它们
                combined = " ".join([str(r[1])[:200] for r in referenced_steps])
                return combined[:500]
    
    # 如果没有明确引用，使用最后一个成功的结果
    if previous_results:
        last_result = previous_results[max(previous_results.keys())]
        # 将描述和结果组合
        return f"{description}\n\n基于前面的结果: {str(last_result)[:300]}"
    
    return description
```

#### 1.2 支持步骤结果的模板化引用

```python
def _prepare_tool_input_with_template(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> str:
    """使用模板化方式准备工具输入"""
    description = step.get("description", "")
    step_results = context.get("step_results", []) if context else []
    
    # 检查描述中是否有模板变量（如 {step_1_result}, {step_2_data}）
    import re
    template_vars = re.findall(r'\{step_(\d+)_result\}|\{step_(\d+)_data\}', description)
    
    if template_vars:
        # 替换模板变量
        result = description
        for match in template_vars:
            step_num = int(match[0] or match[1])
            if step_num <= len(step_results):
                step_result = step_results[step_num - 1]
                if step_result.get("success"):
                    var_value = str(step_result.get("result", ""))[:200]
                    result = result.replace(f"{{step_{step_num}_result}}", var_value)
                    result = result.replace(f"{{step_{step_num}_data}}", var_value)
        return result
    
    return description
```

### 优化2: 改进依赖关系处理

```python
def _check_dependencies(self, step: Dict[str, Any], completed_results: List[Dict[str, Any]]) -> bool:
    """检查步骤依赖是否满足（增强版）"""
    dependencies = step.get("dependencies", [])
    if not dependencies:
        return True
    
    completed_ids = {r.get("step_id") for r in completed_results if r.get("success")}
    
    # 支持多种依赖类型
    dep_type = step.get("dependency_type", "all")  # "all", "any", "conditional"
    
    if dep_type == "all":
        # 所有依赖必须满足（默认）
        return all(dep_id in completed_ids for dep_id in dependencies)
    elif dep_type == "any":
        # 任意一个依赖满足即可（OR依赖）
        return any(dep_id in completed_ids for dep_id in dependencies)
    elif dep_type == "conditional":
        # 条件依赖（如果步骤1成功，需要步骤2；否则需要步骤3）
        condition = step.get("dependency_condition", {})
        if_step = condition.get("if_step")
        then_need = condition.get("then_need", [])
        else_need = condition.get("else_need", [])
        
        if if_step in completed_ids:
            return all(dep_id in completed_ids for dep_id in then_need)
        else:
            return all(dep_id in completed_ids for dep_id in else_need)
    
    return True
```

### 优化3: 实现真正的并行执行

```python
async def _execute_parallel_steps(self, steps: List[Dict[str, Any]], context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """并行执行多个步骤"""
    tasks = []
    for step in steps:
        task = asyncio.create_task(
            self.execution_agent.execute_step(step, context)
        )
        tasks.append((step.get("id"), task))
    
    # 等待所有任务完成
    results = []
    for step_id, task in tasks:
        try:
            result = await task
            results.append(result)
        except Exception as e:
            logger.error(f"并行执行步骤 {step_id} 失败: {e}")
            results.append({
                "step_id": step_id,
                "success": False,
                "error": str(e)
            })
    
    return results
```

## 测试场景

### 场景1: 数据传递任务
**问题**: "搜索'Python异步编程'的最新文章，然后总结前3篇的核心观点"

**优化后的处理**:
1. 步骤1: 使用 `search_web` 搜索文章
2. 步骤2: 使用 `none` (直接推理)，输入: "基于步骤1的搜索结果，总结前3篇的核心观点"
   - `_prepare_tool_input()` 会自动提取步骤1的结果并注入到步骤2的输入中

### 场景2: 复杂依赖任务
**问题**: "如果今天是工作日，搜索'今日股市行情'；否则搜索'周末活动推荐'"

**优化后的处理**:
1. 步骤1: 使用 `get_time` 获取当前时间和星期
2. 步骤2: 根据步骤1的结果，使用条件依赖决定执行哪个搜索

### 场景3: 并行执行任务
**问题**: "同时搜索'AI最新进展'和'机器学习趋势'，然后对比分析"

**优化后的处理**:
1. 步骤1和步骤2: 并行执行两个搜索（使用 `parallel_groups`）
2. 步骤3: 等待步骤1和步骤2完成后，对比分析

## 实施优先级

### 高优先级（立即实施）
1. ✅ 增强 `_prepare_tool_input()` 以智能提取前面步骤的结果
2. ✅ 支持步骤结果的模板化引用

### 中优先级（短期实施）
3. ⚠️ 改进依赖关系处理（支持OR依赖和条件依赖）
4. ⚠️ 实现真正的并行执行

### 低优先级（长期优化）
5. ⚠️ 支持动态计划调整
6. ⚠️ 实现步骤级别的重试机制
