"""
任务先验路由 - 豆包策略第一步
对用户输入做三层判断：是否调用工具、能力标签、属性标签、适配载体。
供编排器在进入规划/执行前决定是否走工具链路，并将 task_ctx 传给 ToolHub 做动态打分。
"""

import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from ..prompts import get_prompt
except Exception:
    get_prompt = None


# 能力标签与工具能力映射（用于后续 ToolHub 能力匹配）
CAPABILITY_TO_TAGS: Dict[str, List[str]] = {
    "文件操作": ["document", "filesystem", "pdf"],
    "数据分析": ["analyze", "document"],
    "业务接口调用": ["research", "document"],
    "通用查询": ["search", "web", "research"],
    "外部交互": ["search", "web", "weather", "map"],
    "权限操作": [],
    "其他": [],
}


def _normalize_capability_tags(cap_str: str) -> List[str]:
    """从路由输出的能力标签字符串解析为标准化标签列表（用于与工具 meta.capabilities 匹配）。"""
    if not cap_str or cap_str.strip() in ("无", "无。"):
        return []
    tags = [t.strip() for t in re.split(r"[,，、]", str(cap_str)) if t.strip()]
    out = []
    for t in tags:
        lower = t.lower()
        if lower in ("文件操作", "文件"):
            out.extend(["document", "filesystem"])
        elif lower in ("数据分析", "分析"):
            out.extend(["analyze", "document"])
        elif lower in ("通用查询", "查询", "搜索"):
            out.extend(["search", "web", "research"])
        elif lower in ("外部交互", "天气", "地图"):
            out.extend(["search", "web", "weather", "map"])
        elif lower in ("业务接口调用"):
            out.extend(["research", "document"])
        else:
            out.append(t)
    return list(dict.fromkeys(out))  # 去重保序


def route_task(
    question: str,
    llm_client: Any,
    tool_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    对用户输入做三层判断，返回是否调用工具及任务上下文（能力标签、属性标签、适配载体）。

    Returns:
        use_tools: bool，是否进入工具调用流程
        capability_tags: List[str]，能力标签（标准化后，可与工具 capabilities 匹配）
        attribute_tags: Dict，时效性/可靠性/成本敏感
        adapt_carriers: List[str]，适配载体 ["本地工具","skill","MCP"]
        raw: 原始解析出的 dict（便于调试）
    """
    default_ctx = {
        "use_tools": True,
        "capability_tags": [],
        "attribute_tags": {"时效性": "中", "可靠性": "中", "成本敏感": "低"},
        "adapt_carriers": ["本地工具", "skill", "MCP"],
        "raw": {},
    }
    if not question or not str(question).strip():
        return default_ctx

    if get_prompt is None:
        logger.debug("task_router: prompts loader not available, use default task_ctx")
        return default_ctx

    try:
        system = get_prompt("tool_routing_task_router_system")
        output_format = get_prompt("tool_routing_task_router_output_format")
        user_msg = get_prompt("tool_routing_task_router_user_template", user_input=question.strip())
    except Exception as e:
        logger.warning(f"task_router: load prompts failed: {e}")
        return default_ctx

    if not system or not user_msg:
        return default_ctx

    full_system = (system + "\n\n" + (output_format or "")).strip()
    try:
        if hasattr(llm_client, "chat") and callable(getattr(llm_client, "chat")):
            resp = llm_client.chat(
                messages=[
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=512,
                temperature=0,
            )
        elif hasattr(llm_client, "generate") and callable(getattr(llm_client, "generate")):
            resp = llm_client.generate(
                prompt=full_system + "\n\n" + user_msg,
                max_tokens=512,
                temperature=0,
            )
        else:
            logger.warning("task_router: llm_client has no chat/generate, use default")
            return default_ctx
    except Exception as e:
        logger.warning(f"task_router: LLM call failed: {e}")
        return default_ctx

    text = ""
    if isinstance(resp, dict):
        text = (resp.get("content") or resp.get("text") or resp.get("response") or "").strip()
    elif isinstance(resp, str):
        text = resp.strip()
    if not text:
        return default_ctx

    # 抽取 JSON
    jmatch = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if not jmatch:
        logger.debug(f"task_router: no JSON found in response: {text[:200]}")
        return default_ctx

    try:
        raw = json.loads(jmatch.group())
    except json.JSONDecodeError as e:
        logger.debug(f"task_router: JSON parse error: {e}, text: {text[:200]}")
        return default_ctx

    use_tools = raw.get("是否调用工具", "是") in ("是", "true", "True", "1", True)
    cap_str = raw.get("能力标签", "") or raw.get("能力标签 ", "")
    capability_tags = _normalize_capability_tags(cap_str)
    attr = raw.get("属性标签") or raw.get("属性标签 ", {})
    if not isinstance(attr, dict):
        attr = {}
    attribute_tags = {
        "时效性": attr.get("时效性") or attr.get("时效性 ", "中"),
        "可靠性": attr.get("可靠性") or attr.get("可靠性 ", "中"),
        "成本敏感": attr.get("成本敏感") or attr.get("成本敏感 ", "低"),
    }
    adapt_carriers = raw.get("适配载体") or raw.get("适配载体 ", [])
    if not isinstance(adapt_carriers, list):
        adapt_carriers = []

    return {
        "use_tools": use_tools,
        "capability_tags": capability_tags,
        "attribute_tags": attribute_tags,
        "adapt_carriers": adapt_carriers,
        "raw": raw,
    }
