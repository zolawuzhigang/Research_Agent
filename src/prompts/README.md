# 提示词配置（与代码解耦）

所有 LLM 相关提示词存放在本目录下的 YAML 文件中，由 `loader.py` 加载，代码中通过 `get_prompt(key, **kwargs)` / `get_prompt_raw(key)` 获取，实现**提示词与代码彻底解耦**。

## 文件与 key 前缀

| 文件 | 前缀 | 说明 |
|------|------|------|
| planning.yaml | planning_ | 任务分解：tools_description、decomposition |
| execution.yaml | execution_ | 执行推理：direct_reasoning |
| synthesis.yaml | synthesis_ | 证据整合：fallback_direct_answer、evidence_synthesis、fallback_no_answer |
| toolhub.yaml | toolhub_ | 多工具结果综合：synthesize_results |
| orchestrator.yaml | orchestrator_ | 快速路径：greeting_answer、history_empty_cn/en、capability_* |

## 占位符

- `get_prompt_raw(key)`：返回原始字符串，不替换占位符。
- `get_prompt(key, **kwargs)`：返回 `raw.format(**kwargs)`，占位符如 `{question}`、`{tools_description}` 等需在调用时传入。

字面量花括号在 YAML 中写为 `{{`、`}}`。

## 使用示例

```python
from src.prompts import get_prompt, get_prompt_raw

# 带占位符
prompt = get_prompt("planning_decomposition", question="...", tools_description="...", tools_list_str="...")

# 仅取文案
greeting = get_prompt_raw("orchestrator_greeting_answer").strip()
```

## 修改提示词

直接编辑对应 YAML 文件即可，无需改代码。重启或调用 `reload_prompts()` 后生效（当前实现为首次 get 时加载并缓存）。
