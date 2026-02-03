# 当前版本与测试说明

## 一、当前是哪个版本

- **提交**: `4e3fa3e`
- **版本名**: **1.0 版本**（合并本地和远程仓库的历史）
- **项目版本号**: `1.0.0`（见 `pyproject.toml`）
- **分支**: `main`，与 `origin/main` 同步

---

## 二、当前项目是否正常运行

### 2.1 核心导入

- **结果**: ✅ 通过  
- **验证**: `ConsoleClient`、`ToolHub`、`LangGraphWorkflow` 等核心模块可正常导入。
- **说明**: 当前环境未安装 LangGraph，会使用 fallback 实现（见启动时的 WARNING），不影响在无 LangGraph 环境下的基本导入与运行。

### 2.2 单元测试（pytest）

- **结果**: ⚠️ 未执行  
- **原因**: 当前使用的 Python 环境中未安装 `pytest`（项目在 `requirements.txt` 中声明了 `pytest>=7.4.0`）。  
- **建议**: 在项目虚拟环境中安装依赖后执行测试：
  ```bash
  pip install -r requirements.txt
  python -m pytest tests/ -v --tb=short
  ```

### 2.3 运行方式

- **控制台**: `python run_console.py`（依赖配置与 API Key）
- **HTTP 服务**: 见 `src/api/` 与项目 README/RUN_GUIDE

---

## 三、1.0 版本包含的优化（提交历史）

1.0 由多次提交合并而成，本版本**已包含**的优化包括：

| 提交 | 说明 |
|------|------|
| `247e443` | Initial commit: Research Agent 多 Agent 流程、fast path、Python 3.13.9、文档 |
| `b0f1d32` | **可观测与调试**: 工具调用、推理、证据合成的 trace |
| `8f5cee6` | **提示词解耦 + 测试**: 从 `src/prompts/*.yaml` 加载提示词；归一化「绛旀」前缀；SearchTool mock；loader 修正 |
| `7cfc05d` | **规划与工具策略**: 规划节点传入 context、执行节点对 step_results 做防御性检查、任务路由与提示词 key 核对 |
| `ad564c8` | chore: 配置更新 |
| `4e3fa3e` | **1.0 版本**: 合并本地与远程仓库历史 |

对应文档中的策略与设计：

- **规划策略**: `PlanningAgent`、`planning.yaml`、规划节点可接收 `context`（含 task_ctx）
- **工具调用策略**: 任务先验路由（`task_router`）、`tool_routing.yaml`、ToolHub 动态打分、执行节点 `_execute_with_tool`
- **提示词**: 全部从 `src/prompts/*.yaml` 加载，与代码中 key 一致
- **工具策略升级**: 见 `docs/TOOL_STRATEGY_UPGRADE.md`（任务先验路由 → 动态优先级 → 触发与兜底）

---

## 四、1.0 版本之后我们做了什么（已回滚）

在你说「进行全代码检查，详细说明我们的问题处理架构，工具调用策略」之后，对以下文件做过**未提交的修改**（写文档、全代码检查相关）：

- `CODE_REVIEW.md`、`config/config.yaml`、`docs/TOOL_STRATEGY_UPGRADE.md`
- `src/agent/langgraph_workflow.py`、`src/agent/multi_agent_system.py`、`src/agent/orchestrator.py`
- `src/prompts/planning.yaml`、`src/prompts/tool_routing.yaml`
- `src/toolhub.py`、`src/utils/normalize.py`、`tests/test_tools.py`

因误操作导致代码被覆盖后，已按你的要求**恢复到「那句话」之前的版本**，即上述修改已全部用 `git restore` 撤销，当前工作区与提交 `4e3fa3e`（1.0）完全一致。

因此，**1.0 之后没有保留任何新的提交**；之前做的那轮「全代码检查 + 问题处理架构与工具调用策略说明」的改动已全部回滚，不再存在于当前代码中。

---

## 五、小结

| 项目 | 结论 |
|------|------|
| 当前版本 | **1.0**（提交 `4e3fa3e`） |
| 核心导入 | ✅ 正常 |
| 单元测试 | ⚠️ 需先 `pip install -r requirements.txt` 再运行 `pytest tests/` |
| 1.0 内已包含的优化 | 见上文「三」与 `CODE_REVIEW.md`、`docs/TOOL_STRATEGY_UPGRADE.md` |
| 1.0 之后的优化 | 仅有过一轮未提交的文档/检查改动，已全部恢复掉，当前无新提交 |

若需要重新做「全代码检查」或「问题处理架构、工具调用策略」说明，可以只生成文档、不直接改代码，避免再次覆盖。
