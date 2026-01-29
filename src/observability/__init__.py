"""
可观测性模块：工具调用、中间推理、证据整合等环节的模块化、可观测、可调试。

- TraceContext: 单次请求的追踪上下文，收集 planning / tool_call / reasoning / synthesis 等事件
- 通过 config.observability.enabled 开启，结果中可携带 trace 供调试
"""

from .trace_context import (
    TraceContext,
    TraceEvent,
    NullTraceContext,
    get_trace_context_from_context,
)

__all__ = [
    "TraceContext",
    "TraceEvent",
    "NullTraceContext",
    "get_trace_context_from_context",
]
