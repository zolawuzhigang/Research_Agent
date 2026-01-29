"""
提示词配置 - 与代码解耦，通过 src/prompts 下的 YAML 加载。
"""

from .loader import get_prompt, get_prompt_raw, reload_prompts

__all__ = ["get_prompt", "get_prompt_raw", "reload_prompts"]
