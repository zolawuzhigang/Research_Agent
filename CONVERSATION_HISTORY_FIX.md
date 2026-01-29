# 对话历史访问功能修复

## 问题描述

当用户询问"我刚刚问了你什么问题？"时，Agent无法正确访问对话历史，只能通过LLM推理，导致返回错误答案（返回了步骤描述而不是实际的历史消息）。

## 解决方案

### 1. 创建对话历史工具

**新文件**: `src/tools/conversation_history_tool.py`

实现了 `ConversationHistoryTool` 类，提供以下功能：
- 获取最后一条消息 (`last`)
- 获取最后一条用户消息 (`last_user`)
- 获取最近N条消息 (`last_n` 或数字)
- 获取所有对话历史 (`all`)

### 2. 注册工具

**修改文件**: `src/agent/orchestrator.py`

在 `_register_default_tools()` 方法中注册 `ConversationHistoryTool`，并传递 `memory_manager` 实例。

### 3. 更新PlanningAgent提示词

**修改文件**: `src/agent/multi_agent_system.py`

在 `_build_decomposition_prompt()` 方法中：
- 添加 `"get_conversation_history"` 到可用工具列表
- 在工具描述中说明何时使用对话历史工具

### 4. 更新执行逻辑

**修改文件**: `src/agent/multi_agent_system.py`

- 在 `_prepare_tool_input()` 中添加对 `get_conversation_history` 的处理，根据步骤描述智能选择查询类型
- 在 `_format_tool_result()` 中添加对对话历史结果的格式化

## 使用方式

### 工具查询类型

工具接受以下查询字符串：

| 查询字符串 | 说明 | 示例 |
|-----------|------|------|
| `"last"` 或 `"最近"` | 获取最后一条消息 | 最后一条消息 |
| `"last_user"` 或 `"最后用户"` | 获取最后一条用户消息 | 用户最后的问题 |
| `"all"` 或 `"全部"` | 获取所有对话历史 | 所有对话 |
| `"10"` 或 `"last_10"` | 获取最近10条消息 | 最近10条消息 |

### 自动识别

工具会根据步骤描述自动识别查询类型：
- 包含"最后"、"最近"、"上一条" → `"last"`
- 包含"最后用户"、"最后用户消息" → `"last_user"`
- 包含"全部"、"所有" → `"all"`
- 其他情况 → 默认返回最近10条

## 示例

### 用户问题："我刚刚问了你什么问题？"

**步骤分解**:
1. 识别用户意图（`tool_type: none`）
2. 检索对话历史中用户上一条消息（`tool_type: get_conversation_history`）
3. 格式化并返回答案（`tool_type: none`）

**执行流程**:
1. PlanningAgent识别需要访问对话历史
2. 步骤2使用 `get_conversation_history` 工具
3. 工具查询 `"last_user"`，返回用户最后的问题
4. 结果格式化后返回给用户

## 测试

运行控制台客户端测试：

```bash
python run_console.py
```

测试场景：
1. 问："现在几点了？"
2. 问："我刚刚问了你什么问题？"
3. 应该正确返回："现在几点了？"

## 相关文件

- `src/tools/conversation_history_tool.py` - 对话历史工具实现
- `src/agent/orchestrator.py` - 工具注册
- `src/agent/multi_agent_system.py` - PlanningAgent和执行逻辑更新
- `src/tools/__init__.py` - 工具模块导出

---

**修复完成时间**: 2026-01-28  
**版本**: 1.0.0
