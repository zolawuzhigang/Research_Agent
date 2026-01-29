# 当前工具处理流程详解

## 一、工具注册阶段（启动时）

### 1.1 工具来源
系统支持三种工具来源，按优先级排序：
- **tools** (优先级0): 原生工具，位于 `src/tools/`
- **skills** (优先级1): 技能工具，位于 `src/skills/`
- **mcps** (优先级2): MCP工具，通过配置文件加载

### 1.2 注册流程
**位置**: `src/agent/orchestrator.py:_register_default_tools()`

```
1. 创建 ToolHub 实例
   ↓
2. 注册原生工具 (tools)
   - 扫描 src/tools/ 目录
   - 提取工具描述和能力标签
   - 注册到 ToolHub，priority=0
   ↓
3. 加载技能工具 (skills)
   - Python类技能: 扫描 .py 文件
   - SKILL.md技能: 扫描 SKILL.md 文件（延迟加载指令）
   - 注册到 ToolHub，priority=1
   ↓
4. 加载MCP工具 (mcps)
   - 从配置文件读取 (mcp.local.json)
   - 创建 ConfigOnlyMcpTool 实例
   - 注册到 ToolHub，priority=2
   ↓
5. 建立索引
   - 按名称索引: _candidates_by_name
   - 按能力索引: _candidates_by_capability
   ↓
6. 传递给 ExecutionAgent
   - self.tool_hub = hub
   - execution_agent.tool_hub = hub
   ↓
7. 通知 PlanningAgent
   - 提取所有工具名称
   - 传递给 PlanningAgent.set_available_tools()
```

### 1.3 能力标签提取
**位置**: `src/toolhub.py:_extract_capabilities_from_description()`

根据工具描述和名称自动提取能力标签，例如：
- "搜索" → `["search", "web", "research"]`
- "计算" → `["calculate"]`
- "时间" → `["time"]`

用于后续的"功能相似工具"并发调用。

---

## 二、任务规划阶段

### 2.1 PlanningAgent 任务分解
**位置**: `src/agent/multi_agent_system.py:PlanningAgent.decompose_task()`

```
用户问题
   ↓
PlanningAgent 分析问题
   ↓
构建提示词（包含可用工具列表，最多显示10个其他工具）
   ↓
LLM 生成任务计划
   ↓
返回步骤列表，每个步骤包含：
   - id: 步骤ID
   - description: 步骤描述
   - tool_type: 工具类型（从可用工具中选择）
   - dependencies: 依赖关系
   - complexity: 复杂度
```

### 2.2 工具列表优化
- 核心工具始终显示（none, search_web, calculate, get_time, get_conversation_history）
- 其他工具只显示前10个
- 超过10个时显示提示："（还有 X 个其他工具，可通过工具名称直接调用）"

---

## 三、工具执行阶段

### 3.1 ExecutionAgent 执行步骤
**位置**: `src/agent/multi_agent_system.py:ExecutionAgent.execute_step()`

```
步骤信息 (step)
   ↓
判断工具类型
   ├─ tool_type == "none" → 直接推理 (_direct_reasoning)
   └─ tool_type != "none" → 工具调用 (_execute_with_tool)
```

### 3.2 工具调用流程
**位置**: `src/agent/multi_agent_system.py:ExecutionAgent._execute_with_tool()`

```
步骤信息 (step)
   ↓
1. 准备工具输入 (_prepare_tool_input)
   - 根据工具类型提取输入
   - 计算类: 提取数学表达式
   - 搜索类: 提取关键词
   - 历史类: 根据描述确定查询类型
   ↓
2. 推断能力标签 (_infer_capability_from_step)
   - 从步骤描述中推断能力（如 "search", "calculate"）
   ↓
3. 尝试按名称调用 (tool_hub.execute)
   - 如果 tool_hub 可用，优先使用
   - 如果失败，尝试按能力调用
   ↓
4. 尝试按能力调用 (tool_hub.execute_by_capability)
   - 如果按名称调用失败，使用推断的能力标签
   - 查找所有功能相似的工具
   ↓
5. 降级处理
   - 如果工具调用失败，回退到直接推理
   - 特殊处理：计算类工具输入为空时，直接降级
```

### 3.3 ToolHub 执行逻辑
**位置**: `src/toolhub.py:ToolHub.execute()`

#### 场景1: 单一候选工具
```
工具名称
   ↓
查找候选列表
   ↓
如果只有1个候选 → 直接调用
   ↓
返回结果
```

#### 场景2: 多个候选工具（同名）
```
工具名称
   ↓
查找候选列表（可能来自 tools/skills/mcps）
   ↓
决定策略 (_should_synthesize)
   ├─ 计算类/时间类 → "选最优" (pick best)
   ├─ 搜索类/提取类 → "综合" (synthesize)
   └─ 2个相似工具 → "综合"
   ↓
构造候选顺序
   - 最近成功的优先
   - 然后按 priority 排序（tools > skills > mcps）
   ↓
并发调用第一批（最多3个，或全部如果<=2且需要综合）
   ├─ 如果策略是"选最优":
   │   - 使用 asyncio.wait(FIRST_COMPLETED)
   │   - 第一个成功后立即取消其他任务
   │   - 返回最优结果
   └─ 如果策略是"综合":
       - 等待所有任务完成
       - 收集所有成功结果
       - 调用 _synthesize_results 综合
   ↓
如果第一批全部失败 → 依次尝试剩余候选
   ↓
返回结果或错误
```

### 3.4 按能力调用流程
**位置**: `src/toolhub.py:ToolHub.execute_by_capability()`

```
能力标签 (capability)
   ↓
查找所有具有该能力的工具 (find_by_capability)
   - 不管名称是否相同
   - 例如: capability="search" 可能找到多个搜索工具
   ↓
按 priority 排序，同优先级内随机打乱
   ↓
决定策略 (_should_synthesize)
   - 如果 <= 2 个工具 → 全部调用并综合
   - 否则根据工具类型决定
   ↓
并发调用（策略同 execute）
   ↓
返回综合结果或最优结果
```

### 3.5 结果综合策略
**位置**: `src/toolhub.py:ToolHub._synthesize_results()`

```
多个工具结果
   ↓
检查结果总长度和数量
   ├─ 如果总长度 > 2000 字符 或 数量 > 3
   │   → 直接使用简单合并（不调用LLM）
   └─ 否则 → 准备LLM综合
   ↓
智能截断每个结果
   - 计算类: 100字符
   - 搜索类: 200-300字符（根据数量调整）
   - 提取类: 300字符
   - 默认: 250字符
   ↓
构建综合提示词
   ↓
调用LLM综合（带10秒超时）
   ├─ 成功 → 返回综合结果
   └─ 失败/超时 → 降级到简单合并
   ↓
简单合并 (_simple_merge_results)
   - 每个结果最多300字符
   - 直接文本拼接
   - 不调用LLM
```

---

## 四、结果处理阶段

### 4.1 结果格式化
**位置**: `src/agent/multi_agent_system.py:ExecutionAgent._format_tool_result()`

```
工具原始结果
   ↓
根据工具类型格式化
   - search_web: 只取前3个结果
   - calculate: 直接返回结果
   - get_time: 返回格式化时间
   - get_conversation_history: 格式化历史记录
   ↓
应用长度限制（Token优化）
   - 计算类: 100字符
   - 时间类: 200字符
   - 搜索类: 500字符
   - 历史类: 1000字符
   - 其他: 500字符
   ↓
智能截断（在句子边界）
   ↓
返回格式化结果
```

### 4.2 结果验证
**位置**: `src/agent/multi_agent_system.py:VerificationAgent.verify_result()`

```
步骤结果
   ↓
一致性检查 (_check_consistency)
   - 与之前步骤结果对比
   - 使用 Jaccard 相似度
   ↓
逻辑检查 (_check_logic)
   - 数值范围验证
   - 时间格式验证
   ↓
返回验证结果
   - verified: 是否通过
   - confidence: 置信度
   - issues: 问题列表
```

### 4.3 最终答案合成
**位置**: `src/agent/multi_agent_system.py:CoordinationAgent._synthesize_answer()`

```
所有步骤结果
   ↓
选择最后一个成功且非空的结果
   ↓
如果所有步骤都失败 → 返回错误信息
   ↓
返回最终答案
```

---

## 五、关键优化点

### 5.1 Token优化
1. **工具结果长度限制**: 根据工具类型设置最大长度
2. **智能截断**: 在句子边界截断，保留关键部分
3. **提前降级**: 大量结果时直接使用简单合并，不调用LLM
4. **工具列表限制**: 只显示前10个其他工具

### 5.2 性能优化
1. **并发调用**: 同名或功能相似的工具并发执行
2. **早期取消**: 第一个成功后立即取消其他任务
3. **结果缓存**: 最近成功的工具索引，优先调用
4. **超时控制**: 每个工具调用有30秒超时

### 5.3 鲁棒性优化
1. **多级降级**: 按名称 → 按能力 → 直接推理
2. **错误处理**: 每个环节都有错误处理和日志
3. **资源清理**: 确保所有任务都被正确取消
4. **结果验证**: 一致性检查和逻辑验证

---

## 六、流程图总结

```
用户问题
   ↓
PlanningAgent 分解任务
   ↓
生成步骤列表（每个步骤指定 tool_type）
   ↓
ExecutionAgent 执行每个步骤
   ├─ tool_type == "none" → 直接推理
   └─ tool_type != "none" → 工具调用
       ↓
       ToolHub.execute(tool_type, input)
       ├─ 按名称查找候选
       ├─ 决定策略（选最优/综合）
       ├─ 并发调用（最多3个）
       ├─ 结果综合（如需要）
       └─ 返回结果
   ↓
格式化工具结果（应用长度限制）
   ↓
验证结果（一致性、逻辑）
   ↓
CoordinationAgent 合成最终答案
   ↓
返回给用户
```

---

## 七、关键数据结构

### ToolCandidate
```python
@dataclass
class ToolCandidate:
    name: str              # 工具名称
    source: str            # 来源 (tools/skills/mcps)
    tool: Any              # 工具对象
    priority: int          # 优先级 (0/1/2)
    meta: Dict[str, Any]   # 元数据（包含 capabilities）
```

### 工具结果格式
```python
{
    "success": bool,       # 是否成功
    "result": Any,         # 结果内容
    "error": str,          # 错误信息（如果失败）
    "_meta": {             # 元数据
        "source": str,     # 工具来源
        "synthesized": bool,  # 是否经过综合
        "source_count": int,  # 来源数量
        "sources": List[str]  # 来源列表
    }
}
```

---

## 八、配置和扩展

### 工具配置
- **原生工具**: 在 `src/tools/` 目录下添加 Python 类
- **技能工具**: 在 `src/skills/` 目录下添加 `.py` 或 `SKILL.md` 文件
- **MCP工具**: 在 `src/config/mcp.local.json` 中配置

### 能力标签扩展
在 `_extract_capabilities_from_description()` 中添加新的关键词映射。

### 策略调整
在 `_should_synthesize()` 中调整"选最优"vs"综合"的规则。
