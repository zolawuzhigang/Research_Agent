"""
追踪上下文：记录工具调用、中间推理、证据整合等环节的事件，便于可观测与调试。
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvent:
    """单条追踪事件"""
    phase: str           # planning | step_start | tool_call | reasoning | evidence_synthesis | step_end | verification
    step_id: Optional[int] = None
    tool_type: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    duration_ms: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, max_preview: int = 500) -> Dict[str, Any]:
        d: Dict[str, Any] = {"phase": self.phase}
        if self.step_id is not None:
            d["step_id"] = self.step_id
        if self.tool_type is not None:
            d["tool_type"] = self.tool_type
        if self.input_preview is not None:
            d["input_preview"] = self.input_preview[:max_preview]
        if self.output_preview is not None:
            d["output_preview"] = self.output_preview[:max_preview]
        if self.duration_ms is not None:
            d["duration_ms"] = round(self.duration_ms, 2)
        if self.success is not None:
            d["success"] = self.success
        if self.error is not None:
            d["error"] = self.error[:max_preview] if isinstance(self.error, str) else str(self.error)[:max_preview]
        if self.extra:
            d["extra"] = self.extra
        return d


def _truncate(s: Any, max_len: int = 500) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    return t[:max_len] + ("..." if len(t) > max_len else "")


class TraceContext:
    """
    单次请求的追踪上下文。在各环节（规划、工具调用、推理、证据整合）调用 on_* 方法记录事件，
    最后通过 to_dict() 得到可序列化 trace，便于日志、调试或 API 返回。
    """

    def __init__(self, request_id: Optional[str] = None, max_events: int = 200, max_preview: int = 500):
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.events: List[TraceEvent] = []
        self.max_events = max_events
        self.max_preview = max_preview
        self._timers: Dict[str, float] = {}

    def _emit(self, event: TraceEvent) -> None:
        if len(self.events) < self.max_events:
            self.events.append(event)

    def _start_timer(self, key: str) -> None:
        self._timers[key] = time.perf_counter()

    def _pop_timer(self, key: str) -> float:
        t0 = self._timers.pop(key, None)
        if t0 is None:
            return 0.0
        return (time.perf_counter() - t0) * 1000

    # ---------- 规划 ----------
    def on_planning_start(self, question_preview: str = "") -> None:
        self._start_timer("planning")
        self._emit(TraceEvent(phase="planning_start", input_preview=_truncate(question_preview, self.max_preview)))

    def on_planning_end(self, steps_count: int = 0, success: bool = True, error: Optional[str] = None) -> None:
        duration_ms = self._pop_timer("planning")
        self._emit(TraceEvent(
            phase="planning_end",
            duration_ms=duration_ms,
            success=success,
            error=error,
            extra={"steps_count": steps_count}
        ))

    # ---------- 步骤 ----------
    def on_step_start(self, step_id: int, description: str = "", tool_type: str = "") -> None:
        key = f"step_{step_id}"
        self._start_timer(key)
        self._emit(TraceEvent(
            phase="step_start",
            step_id=step_id,
            tool_type=tool_type or None,
            input_preview=_truncate(description, self.max_preview)
        ))

    def on_step_end(
        self,
        step_id: int,
        success: bool,
        result_preview: str = "",
        error: Optional[str] = None,
        method: str = "",
    ) -> None:
        key = f"step_{step_id}"
        duration_ms = self._pop_timer(key)
        self._emit(TraceEvent(
            phase="step_end",
            step_id=step_id,
            output_preview=_truncate(result_preview, self.max_preview),
            duration_ms=duration_ms,
            success=success,
            error=error,
            extra={"method": method} if method else {}
        ))

    # ---------- 工具调用 ----------
    def on_tool_call_start(self, step_id: int, tool_type: str, tool_input: Any = None) -> None:
        key = f"tool_{step_id}_{tool_type}"
        self._start_timer(key)
        self._emit(TraceEvent(
            phase="tool_call",
            step_id=step_id,
            tool_type=tool_type,
            input_preview=_truncate(tool_input, self.max_preview),
            extra={"status": "start"}
        ))

    def on_tool_call_end(
        self,
        step_id: int,
        tool_type: str,
        success: bool,
        result_preview: Any = None,
        error: Optional[str] = None,
    ) -> None:
        key = f"tool_{step_id}_{tool_type}"
        duration_ms = self._pop_timer(key)
        self._emit(TraceEvent(
            phase="tool_call",
            step_id=step_id,
            tool_type=tool_type,
            output_preview=_truncate(result_preview, self.max_preview),
            duration_ms=duration_ms,
            success=success,
            error=error,
            extra={"status": "end"}
        ))

    # ---------- 推理 ----------
    def on_reasoning_start(self, step_id: int, description: str = "") -> None:
        key = f"reasoning_{step_id}"
        self._start_timer(key)
        self._emit(TraceEvent(
            phase="reasoning",
            step_id=step_id,
            input_preview=_truncate(description, self.max_preview),
            extra={"status": "start"}
        ))

    def on_reasoning_end(
        self,
        step_id: int,
        success: bool,
        result_preview: str = "",
        error: Optional[str] = None,
    ) -> None:
        key = f"reasoning_{step_id}"
        duration_ms = self._pop_timer(key)
        self._emit(TraceEvent(
            phase="reasoning",
            step_id=step_id,
            output_preview=_truncate(result_preview, self.max_preview),
            duration_ms=duration_ms,
            success=success,
            error=error,
            extra={"status": "end"}
        ))

    # ---------- 证据整合/合成 ----------
    def on_synthesis_start(self, step_results_count: int = 0) -> None:
        self._start_timer("synthesis")
        self._emit(TraceEvent(phase="evidence_synthesis", extra={"step_results_count": step_results_count}))

    def on_synthesis_end(self, success: bool, answer_preview: str = "", error: Optional[str] = None) -> None:
        duration_ms = self._pop_timer("synthesis")
        self._emit(TraceEvent(
            phase="evidence_synthesis",
            output_preview=_truncate(answer_preview, self.max_preview),
            duration_ms=duration_ms,
            success=success,
            error=error,
            extra={"status": "end"}
        ))

    # ---------- 验证 ----------
    def on_verification_start(self, step_id: int) -> None:
        key = f"verify_{step_id}"
        self._start_timer(key)
        self._emit(TraceEvent(phase="verification", step_id=step_id, extra={"status": "start"}))

    def on_verification_end(self, step_id: int, verified: bool, confidence: float = 0.0) -> None:
        key = f"verify_{step_id}"
        duration_ms = self._pop_timer(key)
        self._emit(TraceEvent(
            phase="verification",
            step_id=step_id,
            duration_ms=duration_ms,
            success=verified,
            extra={"status": "end", "confidence": confidence}
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "events": [e.to_dict(self.max_preview) for e in self.events],
            "events_count": len(self.events),
        }


class NullTraceContext:
    """空实现：不记录任何事件，用于 observability 关闭时。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def on_planning_start(self, question_preview: str = "") -> None:
        pass

    def on_planning_end(self, steps_count: int = 0, success: bool = True, error: Optional[str] = None) -> None:
        pass

    def on_step_start(self, step_id: int, description: str = "", tool_type: str = "") -> None:
        pass

    def on_step_end(
        self,
        step_id: int,
        success: bool,
        result_preview: str = "",
        error: Optional[str] = None,
        method: str = "",
    ) -> None:
        pass

    def on_tool_call_start(self, step_id: int, tool_type: str, tool_input: Any = None) -> None:
        pass

    def on_tool_call_end(
        self,
        step_id: int,
        tool_type: str,
        success: bool,
        result_preview: Any = None,
        error: Optional[str] = None,
    ) -> None:
        pass

    def on_reasoning_start(self, step_id: int, description: str = "") -> None:
        pass

    def on_reasoning_end(
        self,
        step_id: int,
        success: bool,
        result_preview: str = "",
        error: Optional[str] = None,
    ) -> None:
        pass

    def on_synthesis_start(self, step_results_count: int = 0) -> None:
        pass

    def on_synthesis_end(self, success: bool, answer_preview: str = "", error: Optional[str] = None) -> None:
        pass

    def on_verification_start(self, step_id: int) -> None:
        pass

    def on_verification_end(self, step_id: int, verified: bool, confidence: float = 0.0) -> None:
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {"request_id": "", "events": [], "events_count": 0}


def get_trace_context_from_context(context: Optional[Dict[str, Any]]) -> Any:
    """从 workflow/agent 的 context 中取出 TraceContext（可能为 NullTraceContext）。"""
    if not context:
        return NullTraceContext()
    trace = context.get("_trace") or context.get("observability")
    if trace is None:
        return NullTraceContext()
    return trace
