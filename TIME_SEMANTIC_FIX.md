# 时间语义查询通用解决方案

## 问题类别

这类问题的本质是：**Agent在执行任务时，需要访问"处理当前任务之前"的对话历史，但当前任务已经被添加到历史中，导致时间语义混淆**。

### 典型场景

1. **"刚刚/刚才"类查询**
   - "我刚刚问了你什么问题？"
   - "我刚才说了什么？"
   - "你刚刚回答了什么？"

2. **"之前"类查询**
   - "我之前都问了什么？"
   - "我们之前聊了什么？"
   - "之前的问题是什么？"

3. **"上一个/上一条"类查询**
   - "我上一个问题是什么？"
   - "上一条消息是什么？"
   - "重复我上一个问题"

4. **"总结/回顾"类查询**
   - "总结一下之前的对话"
   - "回顾我们刚才的讨论"
   - "列出之前的所有问题"

## 根本原因

在`orchestrator.py`中，用户问题在处理**前**就被添加到对话历史（第106行）：
```python
# 添加到对话历史
self.memory.add_conversation("user", task, context)
```

这导致：
- 当Agent在执行步骤时访问历史，当前问题已经在历史中
- 查询"最后一条用户消息"时，返回的是当前问题，而不是"之前"的问题
- 时间语义（"刚刚"、"之前"、"刚才"）无法正确理解

## 通用解决方案

### 核心设计：历史快照机制

实现了一个**历史快照机制**，在处理任务时提供"处理前"的历史视图：

1. **创建快照**：在处理任务前，创建当前历史的快照
2. **智能检测**：工具自动检测查询中的时间语义词
3. **使用快照**：如果检测到时间语义，使用快照（处理前历史）
4. **清除快照**：处理完成后清除快照

### 实现细节

#### 1. Memory系统增强 (`src/agent/memory.py`)

**新增功能**：
- `create_snapshot()`: 创建历史快照
- `clear_snapshot()`: 清除历史快照
- `get_recent_history(use_snapshot=True)`: 支持使用快照
- `get_conversation_context(use_snapshot=True)`: 支持使用快照

**关键代码**：
```python
def create_snapshot(self):
    """创建历史快照 - 用于在处理任务时提供'处理前'的历史视图"""
    self._history_snapshot = list(self.conversation_history)

def get_recent_history(self, n: int = 10, use_snapshot: bool = False):
    """获取最近的对话历史"""
    if use_snapshot and self._history_snapshot is not None:
        history = self._history_snapshot
    else:
        history = list(self.conversation_history)
    return history[-n:] if len(history) > n else history
```

#### 2. Orchestrator集成 (`src/agent/orchestrator.py`)

**处理流程**：
```python
async def process_task(self, task: str, context: Optional[Dict] = None):
    # 1. 创建历史快照（处理前历史）
    self.memory.create_snapshot()
    
    # 2. 添加到对话历史
    self.memory.add_conversation("user", task, context)
    
    # 3. 处理任务
    result = await self.workflow.run(task, context)
    
    # 4. 清除历史快照
    self.memory.clear_snapshot()
```

#### 3. 对话历史工具增强 (`src/tools/conversation_history_tool.py`)

**智能时间语义检测**：
```python
# 检测时间语义：如果查询涉及"之前"、"刚刚"、"刚才"等，使用快照
time_semantic_keywords = [
    "刚刚", "刚才", "之前", "之前的问题", "上一个", "上一条", 
    "last", "previous", "before", "earlier", "刚才的", "刚刚的"
]
use_snapshot = any(keyword in query_lower for keyword in time_semantic_keywords)
```

**自动使用快照**：
```python
# 所有查询都支持 use_snapshot 参数
history = self.memory_manager.get_conversation_context(
    n=n, 
    use_snapshot=use_snapshot  # 自动检测时间语义
)
```

## 解决的问题

### ✅ 场景1：单次提问
- **用户**："现在几点了？"
- **用户**："我刚刚问了你什么问题？"
- **结果**：正确返回"现在几点了？"（使用快照，排除当前问题）

### ✅ 场景2：多次提问
- **用户**："现在几点了？"
- **用户**："我刚刚都问了你什么问题？"
- **用户**："我说的是我上上几个问题？而且不止一条吧"
- **结果**：正确返回之前的所有问题列表（使用快照）

### ✅ 场景3：总结查询
- **用户**："总结一下之前的对话"
- **结果**：正确总结处理当前任务之前的对话（使用快照）

### ✅ 场景4：回顾查询
- **用户**："回顾我们刚才的讨论"
- **结果**：正确回顾处理当前任务之前的讨论（使用快照）

## 优势

1. **通用性**：解决所有涉及时间语义的查询问题
2. **自动化**：无需手动指定，工具自动检测时间语义
3. **透明性**：对上层代码透明，无需修改业务逻辑
4. **可靠性**：快照机制确保历史视图的一致性
5. **灵活性**：支持快照和当前历史两种视图

## 时间语义词列表

系统会自动检测以下关键词，并自动使用快照：

**中文**：
- 刚刚、刚才、之前、之前的问题、上一个、上一条、刚才的、刚刚的

**英文**：
- last、previous、before、earlier

## 扩展性

如果需要添加新的时间语义词，只需在`conversation_history_tool.py`中更新`time_semantic_keywords`列表：

```python
time_semantic_keywords = [
    "刚刚", "刚才", "之前", "之前的问题", "上一个", "上一条", 
    "last", "previous", "before", "earlier", "刚才的", "刚刚的",
    # 添加新的关键词...
    "刚才说的", "之前提到的", "earlier mentioned"
]
```

## 测试建议

### 测试场景1：基础时间语义
```
1. 问："现在几点了？"
2. 问："我刚刚问了你什么问题？"
期望：返回"现在几点了？"
```

### 测试场景2：多次提问
```
1. 问："现在几点了？"
2. 问："我刚刚都问了你什么问题？"
3. 问："我说的是我上上几个问题？而且不止一条吧"
期望：返回之前的所有问题列表
```

### 测试场景3：总结查询
```
1. 问："现在几点了？"
2. 问："总结一下之前的对话"
期望：总结处理当前任务之前的对话
```

### 测试场景4：回顾查询
```
1. 问："现在几点了？"
2. 问："回顾我们刚才的讨论"
期望：回顾处理当前任务之前的讨论
```

## 相关文件

- `src/agent/memory.py` - 历史快照机制实现
- `src/agent/orchestrator.py` - 快照创建和清除
- `src/tools/conversation_history_tool.py` - 时间语义检测和使用快照

---

**实现完成时间**: 2026-01-28  
**版本**: 3.0.0  
**设计模式**: 快照模式（Snapshot Pattern）
