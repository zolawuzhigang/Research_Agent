"""
提示词加载器：从 src/prompts/*.yaml 加载提示词，支持占位符 {key} 格式化。
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

_CACHE: Dict[str, str] = {}
_PROMPTS_DIR: Optional[Path] = None


def _prompts_dir() -> Path:
    global _PROMPTS_DIR
    if _PROMPTS_DIR is None:
        _PROMPTS_DIR = Path(__file__).resolve().parent
    return _PROMPTS_DIR


def _load_all_yaml() -> Dict[str, str]:
    """加载 prompts 目录下所有 .yaml 文件并合并为 key -> value（仅取字符串值或展平嵌套）。"""
    if yaml is None:
        return {}
    merged: Dict[str, Any] = {}
    d = _prompts_dir()
    if not d.exists():
        return {}
    for f in sorted(d.glob("*.yaml")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = yaml.safe_load(fp)
            if not isinstance(data, dict):
                continue
            # 使用文件名作前缀，避免多文件 key 冲突，如 planning_decomposition
            prefix = f.stem + "_"
            _flatten_into(merged, data, prefix=prefix)
        except Exception:
            continue
    result: Dict[str, str] = {}
    for k, v in merged.items():
        if isinstance(v, str):
            result[k] = v
    return result


def _flatten_into(target: Dict[str, Any], data: Dict[str, Any], prefix: str) -> None:
    for key, value in data.items():
        full = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict) and not _looks_like_prompt(value):
            _flatten_into(target, value, full + "_")
        else:
            if isinstance(value, str):
                target[full] = value
            elif isinstance(value, (list, dict)):
                # 多行提示词可能被解析为 list（按行），转回字符串
                if isinstance(value, list):
                    target[full] = "\n".join(str(x) for x in value)
                else:
                    target[full] = str(value)


def _looks_like_prompt(d: dict) -> bool:
    """简单判断是否为「提示词对象」（含 content 等）还是嵌套 key 命名空间。"""
    return "content" in d or "text" in d


def reload_prompts() -> None:
    """重新加载所有提示词（清除缓存）。"""
    global _CACHE
    _CACHE = {}
    _CACHE.update(_load_all_yaml())


def get_prompt_raw(key: str) -> str:
    """获取原始提示词字符串，不进行占位符替换。若不存在返回空字符串。"""
    if not _CACHE:
        reload_prompts()
    return _CACHE.get(key, "")


def get_prompt(key: str, **kwargs: Any) -> str:
    """
    获取提示词并替换占位符。例如 get_prompt("execution_direct_reasoning", step_desc="...", context_info="...")。
    占位符使用 Python 格式：{step_desc}、{context_info} 等；字面量花括号用双写 {{、}}。
    """
    raw = get_prompt_raw(key)
    if not raw:
        return ""
    try:
        return raw.format(**kwargs)
    except KeyError as e:
        # 缺少占位符参数时保留原占位符，避免崩溃
        return raw
    except Exception:
        return raw
