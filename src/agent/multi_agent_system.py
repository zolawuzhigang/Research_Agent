"""
多Agent系统 - 基于LangGraph的协作式智能体系统
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
import json
import time
from loguru import logger

# LangGraph 相关导入（兼容 0.2x 与 1.x）：先 StateGraph/END，再可选 add_messages
LANGGRAPH_AVAILABLE = False
add_messages = None  # noqa: F811
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    try:
        from langgraph.graph.state import StateGraph
        from langgraph.constants import END
        LANGGRAPH_AVAILABLE = True
    except ImportError:
        pass
if LANGGRAPH_AVAILABLE:
    try:
        from langgraph.graph.message import add_messages
    except ImportError:
        add_messages = None
if not LANGGRAPH_AVAILABLE:
    logger.warning("LangGraph not available, using fallback implementation")

# 定义 AgentState（兼容 LangGraph 不可用或 add_messages 不可用）
if LANGGRAPH_AVAILABLE and add_messages is not None:
    try:
        class AgentState(TypedDict):
            """Agent系统状态"""
            question: str
            conversation_history: Annotated[List[Dict], add_messages]
            task_plan: Optional[Dict[str, Any]]
            current_step: int
            step_results: List[Dict[str, Any]]
            tool_calls: List[Dict[str, Any]]
            verification_results: List[Dict[str, Any]]
            final_answer: Optional[str]
            confidence: float
            errors: List[str]
            metadata: Dict[str, Any]
    except Exception:
        LANGGRAPH_AVAILABLE = False
        add_messages = None

if LANGGRAPH_AVAILABLE and add_messages is None:
    class AgentState(TypedDict):
        """Agent系统状态（无 add_messages 时）"""
        question: str
        conversation_history: List[Dict]
        task_plan: Optional[Dict[str, Any]]
        current_step: int
        step_results: List[Dict[str, Any]]
        tool_calls: List[Dict[str, Any]]
        verification_results: List[Dict[str, Any]]
        final_answer: Optional[str]
        confidence: float
        errors: List[str]
        metadata: Dict[str, Any]

if not LANGGRAPH_AVAILABLE:
    class AgentState(TypedDict):
        """Agent系统状态（简化版，LangGraph不可用时）"""
        question: str
        conversation_history: List[Dict]
        task_plan: Optional[Dict[str, Any]]
        current_step: int
        step_results: List[Dict[str, Any]]
        tool_calls: List[Dict[str, Any]]
        verification_results: List[Dict[str, Any]]
        final_answer: Optional[str]
        confidence: float
        errors: List[str]
        metadata: Dict[str, Any]


class PlanningAgent:
    """
    规划Agent - 负责任务分解和计划制定
    """
    
    def __init__(self, llm=None):
        self.llm = llm
        # 可用工具名称（包括原生工具、skills、mcps），由编排层注入
        self.available_tools: List[str] = ["none", "search_web", "advanced_web_search", "calculate", "get_time", "get_conversation_history", "list_workspace_files"]
        # 延迟导入LLM客户端
        if llm is None:
            try:
                from ..llm.llm_client import LLMClient
                self.llm = LLMClient()
            except Exception as e:
                logger.warning(f"无法初始化LLM客户端: {e}")
        logger.info("PlanningAgent initialized")

    def set_available_tools(self, tool_names: List[str]) -> None:
        """
        由外部注入“当前系统可用的工具名称列表”，用于构建规划提示词。
        会自动补充基础的 'none' 选项。
        """
        base = {"none"}
        try:
            base.update({str(n) for n in tool_names})
        except Exception:
            pass
        self.available_tools = sorted(base)
    
    def decompose_task(self, question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        将复杂问题分解为子任务
        
        Args:
            question: 用户问题
            context: 上下文信息
        
        Returns:
            任务计划（包含步骤列表和依赖关系）
        """
        logger.info(f"PlanningAgent: 开始分解任务 - {question}")
        
        # 构建任务分解提示词
        prompt = self._build_decomposition_prompt(question, context)
        
        # 调用LLM进行任务分解
        if self.llm:
            response = self._call_llm(prompt)
            plan = self._parse_plan(response)
        else:
            # 占位实现
            plan = self._default_decomposition(question)
        
        logger.info(f"PlanningAgent: 任务分解完成，共{len(plan.get('steps', []))}个步骤")
        return plan
    
    def _build_decomposition_prompt(self, question: str, context: Dict[str, Any] = None) -> str:
        """构建任务分解提示词（优化：限制工具列表长度以控制token消耗）"""
        # 获取可用工具列表（来自 ToolHub/ToolRegistry 注入）
        available_tools = self.available_tools or [
            "none",
            "search_web",
            "advanced_web_search",
            "calculate",
            "get_time",
            "get_conversation_history",
            "list_workspace_files",
        ]
        
        # 优化：限制工具列表长度，避免token爆炸
        # 核心工具始终包含，其他工具只显示前10个
        CORE_TOOLS = {"none", "search_web", "advanced_web_search", "calculate", "get_time", "get_conversation_history", "list_workspace_files"}
        core_tools_list = [t for t in available_tools if t in CORE_TOOLS]
        other_tools = [t for t in available_tools if t not in CORE_TOOLS]
        
        # 只显示前10个其他工具，避免列表过长
        MAX_OTHER_TOOLS = 10
        if len(other_tools) > MAX_OTHER_TOOLS:
            displayed_other_tools = other_tools[:MAX_OTHER_TOOLS]
            tools_list_str = ", ".join(core_tools_list + displayed_other_tools)
            tools_list_str += f"（还有 {len(other_tools) - MAX_OTHER_TOOLS} 个其他工具，可通过工具名称直接调用）"
        else:
            tools_list_str = ", ".join(available_tools)
        
        try:
            from ..prompts import get_prompt, get_prompt_raw
        except ImportError:
            get_prompt = lambda k, **kw: ""
            get_prompt_raw = lambda k: ""
        tools_description = get_prompt_raw("planning_tools_description").strip()
        if not tools_description:
            tools_description = "可用工具类型：none, search_web, advanced_web_search, calculate, get_time, get_conversation_history, list_workspace_files 等。"
        prompt = get_prompt("planning_decomposition", question=question, tools_description=tools_description, tools_list_str=tools_list_str)
        if not prompt:
            prompt = f"请将以下问题分解为可执行步骤。问题：{question}\n可用工具：{tools_list_str}"
        if context:
            # 排除不可 JSON 序列化的 _trace，避免 NullTraceContext 导致序列化失败
            ctx_serializable = {k: v for k, v in context.items() if k != "_trace"}
            if ctx_serializable:
                prompt += f"\n上下文信息：{json.dumps(ctx_serializable, ensure_ascii=False)}"
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM（同步方法，在异步环境中需要特殊处理）"""
        if not prompt or not prompt.strip():
            logger.warning("LLM调用：提示词为空")
            return ""
        
        if self.llm:
            try:
                # LLM.generate 是同步方法，在异步环境中直接调用
                # 如果性能有问题，可以考虑使用 asyncio.to_thread
                result = self.llm.generate(prompt)
                if not result:
                    logger.warning("LLM返回空结果")
                return result or ""
            except ValueError as e:
                logger.error(f"LLM调用参数错误: {e}")
                return ""
            except Exception as e:
                logger.error(f"LLM调用失败: {e}")
                return ""
        else:
            logger.warning("LLM客户端未初始化")
        return ""
    
    def _parse_plan(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的计划"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"解析计划失败: {e}")
        
        return self._default_decomposition("")
    
    def _default_decomposition(self, question: str) -> Dict[str, Any]:
        """默认任务分解（占位实现）"""
        return {
            "steps": [
                {
                    "id": 1,
                    "description": f"理解问题：{question}",
                    "tool_type": "none",
                    "dependencies": [],
                    "complexity": 2,
                    "estimated_time": 5
                },
                {
                    "id": 2,
                    "description": "搜索相关信息",
                    "tool_type": "search_web",
                    "dependencies": [1],
                    "complexity": 3,
                    "estimated_time": 10
                },
                {
                    "id": 3,
                    "description": "整合信息并生成答案",
                    "tool_type": "none",
                    "dependencies": [2],
                    "complexity": 4,
                    "estimated_time": 15
                }
            ],
            "parallel_groups": [],
            "total_estimated_time": 30
        }


class ExecutionAgent:
    """
    执行Agent - 负责执行具体任务步骤
    """
    
    def __init__(self, tool_registry=None, llm=None):
        self.tool_registry = tool_registry
        self.tool_hub = None
        self.llm = llm
        # 延迟导入LLM客户端
        if llm is None:
            try:
                from ..llm.llm_client import LLMClient
                self.llm = LLMClient()
            except Exception as e:
                logger.warning(f"无法初始化LLM客户端: {e}")
        logger.info("ExecutionAgent initialized")
    
    async def execute_step(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行单个步骤
        
        Args:
            step: 步骤信息
            context: 上下文信息（包含之前步骤的结果）
        
        Returns:
            执行结果
        """
        if not step:
            logger.error("步骤信息为空")
            return {
                "step_id": None,
                "success": False,
                "error": "步骤信息为空"
            }
        
        step_id = step.get("id")
        step_desc = step.get("description", "未知步骤")
        tool_type = step.get("tool_type", "none")
        logger.info(f"ExecutionAgent: 执行步骤 {step_id} - {step_desc}")
        logger.info(f"[步骤{step_id}] 工具类型: {tool_type}")

        trace = None
        try:
            from ..observability import get_trace_context_from_context
            trace = get_trace_context_from_context(context)
        except Exception:
            pass
        if trace and hasattr(trace, "on_step_start"):
            trace.on_step_start(step_id or 0, step_desc, tool_type)

        try:
            if tool_type == "none":
                logger.info(f"[步骤{step_id}] 使用直接推理模式")
                result = await self._direct_reasoning(step, context)
            else:
                logger.info(f"[步骤{step_id}] 使用工具模式: {tool_type}")
                result = await self._execute_with_tool(step, context)

            if not result:
                logger.warning(f"步骤 {step_id} 返回空结果")
                result = {
                    "step_id": step_id,
                    "success": False,
                    "error": "执行返回空结果"
                }

            if trace and hasattr(trace, "on_step_end"):
                trace.on_step_end(
                    step_id or 0,
                    result.get("success", False),
                    result_preview=str(result.get("result", ""))[:500],
                    error=result.get("error"),
                    method=result.get("method", ""),
                )
            logger.info(f"ExecutionAgent: 步骤 {step_id} 执行完成，成功={result.get('success', False)}")
            return result

        except Exception as e:
            logger.error(f"执行步骤 {step_id} 时发生异常: {e}")
            if trace and hasattr(trace, "on_step_end"):
                trace.on_step_end(step_id or 0, False, error=str(e))
            return {
                "step_id": step_id,
                "success": False,
                "error": str(e)
            }
    
    async def _direct_reasoning(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """直接推理（不使用工具）"""
        step_id = step.get("id")
        step_desc = step.get('description', '') or "处理任务"
        trace = None
        try:
            from ..observability import get_trace_context_from_context
            trace = get_trace_context_from_context(context)
        except Exception:
            pass
        if trace and hasattr(trace, "on_reasoning_start"):
            trace.on_reasoning_start(step_id or 0, step_desc)

        if not self.llm:
            logger.warning(f"[步骤{step_id}] LLM不可用，无法进行直接推理")
            if trace and hasattr(trace, "on_reasoning_end"):
                trace.on_reasoning_end(step_id or 0, False, error="LLM不可用")
            return {
                "step_id": step_id,
                "success": False,
                "error": "LLM不可用",
                "method": "direct_reasoning"
            }

        logger.info(f"[步骤{step_id}] LLM可用，开始直接推理")

        try:
            context_info = self._format_context(context) if context else ''
            try:
                from ..prompts import get_prompt
                prompt = get_prompt(
                    "execution_direct_reasoning",
                    step_desc=step_desc,
                    context_info=context_info,
                )
            except Exception:
                prompt = f"请回答以下问题：\n{step_desc}\n\n如果需要参考之前的步骤结果，请使用以下信息：\n{context_info}\n\n请直接给出答案，不要包含推理过程。"
            if not prompt:
                prompt = f"请回答以下问题：\n{step_desc}\n\n参考信息：\n{context_info}\n\n请直接给出答案，不要包含推理过程。"
            
            # 使用异步方法（如果可用），否则在线程池中执行同步方法
            logger.info(f"[步骤{step.get('id')}] 开始调用LLM进行推理...")
            try:
                if hasattr(self.llm, 'generate_async'):
                    logger.info(f"[步骤{step.get('id')}] 使用异步方法 generate_async")
                    result = await self.llm.generate_async(prompt)
                else:
                    # 在线程池中执行同步方法，避免阻塞事件循环
                    logger.info(f"[步骤{step.get('id')}] 使用同步方法 generate（在线程池中）")
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if hasattr(asyncio, 'to_thread'):
                        result = await asyncio.to_thread(self.llm.generate, prompt)
                    else:
                        result = await loop.run_in_executor(None, lambda: self.llm.generate(prompt))
                
                logger.info(f"[步骤{step.get('id')}] LLM调用完成，结果长度: {len(result) if result else 0}")
                if result:
                    logger.info(f"[步骤{step.get('id')}] 结果预览: {result[:100]}...")
                
                if not result or not result.strip():
                    logger.warning(f"[步骤{step.get('id')}] 直接推理返回空结果")
                    if trace and hasattr(trace, "on_reasoning_end"):
                        trace.on_reasoning_end(step.get("id") or 0, False, error="推理结果为空")
                    return {
                        "step_id": step.get("id"),
                        "success": False,
                        "error": "推理结果为空",
                        "method": "direct_reasoning"
                    }
                if trace and hasattr(trace, "on_reasoning_end"):
                    trace.on_reasoning_end(step.get("id") or 0, True, result_preview=result.strip()[:500])
                return {
                    "step_id": step.get("id"),
                    "success": True,
                    "result": result.strip(),
                    "method": "direct_reasoning"
                }
            except Exception as llm_error:
                # 通用业务场景：限流/429/449/网关返回非标准格式
                msg = str(llm_error)
                lowered = msg.lower()
                if ("rate limit" in lowered) or ("429" in lowered) or ("449" in lowered) or ("限流" in lowered) or ("too many" in lowered):
                    logger.warning(f"[步骤{step.get('id')}] LLM疑似被限流，触发用户可见降级: {msg}")
                    if trace and hasattr(trace, "on_reasoning_end"):
                        trace.on_reasoning_end(step.get("id") or 0, True, result_preview="限流降级")
                    return {
                        "step_id": step.get("id"),
                        "success": True,
                        "result": "我这边请求有点频繁（可能触发限流），请稍等几十秒再试一次；如果你愿意，也可以把你现在最想让我做的具体任务说一下，我会优先处理关键步骤。",
                        "method": "direct_reasoning_rate_limited_fallback"
                    }
                logger.exception(f"[步骤{step.get('id')}] LLM调用过程中出错: {llm_error}")
                if trace and hasattr(trace, "on_reasoning_end"):
                    trace.on_reasoning_end(step.get("id") or 0, False, error=msg)
                raise  # 重新抛出，让外层catch处理
        except ValueError as e:
            logger.error(f"直接推理参数错误: {e}")
            if trace and hasattr(trace, "on_reasoning_end"):
                trace.on_reasoning_end(step.get("id") or 0, False, error=str(e))
            return {
                "step_id": step.get("id"),
                "success": False,
                "error": f"参数错误: {str(e)}",
                "method": "direct_reasoning"
            }
        except Exception as e:
            logger.exception(f"直接推理失败: {e}")  # 使用 exception 记录完整堆栈
            if trace and hasattr(trace, "on_reasoning_end"):
                trace.on_reasoning_end(step.get("id") or 0, False, error=str(e))
            return {
                "step_id": step.get("id"),
                "success": False,
                "error": f"推理失败: {str(e)}",
                "method": "direct_reasoning"
            }
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文信息"""
        if not context:
            return ""
        
        formatted = []
        step_results = context.get("step_results", [])
        for i, result in enumerate(step_results):
            if result.get("success"):
                formatted.append(f"步骤{i+1}结果: {result.get('result', '')}")
        
        return "\n".join(formatted)
    
    def _infer_capability_from_step(self, step: Dict[str, Any]) -> Optional[str]:
        """
        从步骤描述中推断所需的能力标签（用于功能相似工具发现）。
        例如: "搜索最新AI新闻" -> "search"
        """
        desc = str(step.get("description", "")).lower()
        tool_type = str(step.get("tool_type", "")).lower()

        # 能力标签推断规则
        if "搜索" in desc or "search" in desc or "查找" in desc or "检索" in desc or tool_type in ["search_web", "search"]:
            return "search"
        if "计算" in desc or "算" in desc or "calculate" in desc or "math" in desc or tool_type in ["calculate", "calc"]:
            return "calculate"
        if "时间" in desc or "time" in desc or "日期" in desc or "date" in desc or tool_type in ["get_time", "time"]:
            return "time"
        if "天气" in desc or "weather" in desc or "forecast" in desc or "预报" in desc:
            return "weather"
        if "pdf" in desc or "pdf" in tool_type:
            return "pdf"
        if "文档" in desc or "document" in desc or "docx" in desc or "xlsx" in desc:
            return "document"
        if "测试" in desc or "test" in desc or "testing" in desc or "webapp" in tool_type:
            return "test"
        if "历史" in desc or "history" in desc or "对话" in desc or "conversation" in desc or tool_type in ["get_conversation_history", "history"]:
            return "history"
        if (
            "目录" in desc
            or "文件" in desc
            or "file" in desc
            or "folder" in desc
            or "directory" in desc
            or "list" in desc
            or "ls" in desc
            or tool_type in ["list_workspace_files"]
        ):
            return "filesystem"
        if "地图" in desc or "map" in desc or "位置" in desc or "location" in desc or "amap" in tool_type:
            return "map"

        return None

    async def _execute_with_tool(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """使用工具执行"""
        tool_type = step.get("tool_type")
        step_id = step.get("id")
        trace = None
        try:
            from ..observability import get_trace_context_from_context
            trace = get_trace_context_from_context(context)
        except Exception:
            pass

        if not tool_type:
            logger.warning(f"[步骤{step_id}] 工具类型未指定")
            return {
                "step_id": step_id,
                "success": False,
                "error": "工具类型未指定",
                "method": "tool_execution"
            }
        
        # Prefer ToolHub (supports tools>skills>mcps with fallback)
        if self.tool_hub and self.tool_hub.has_tool(tool_type):
            try:
                tool_input = self._prepare_tool_input(step, context)
                tool_input_preview = ""
                try:
                    tool_input_preview = str(tool_input)[:100] if tool_input else "空"
                except Exception:
                    tool_input_preview = "空"
                logger.info(f"[步骤{step_id}] ToolHub输入: {tool_input_preview}")

                if tool_type == "calculate" and (tool_input is None or str(tool_input).strip() == ""):
                    logger.warning(f"[步骤{step_id}] 计算器工具输入为空，直接降级到推理，避免语法错误")
                    return await self._direct_reasoning(step, context)

                if trace and hasattr(trace, "on_tool_call_start"):
                    trace.on_tool_call_start(step_id or 0, tool_type, tool_input)

                task_ctx = (context or {}).get("task_ctx")
                tool_result = await self.tool_hub.execute(
                    tool_type, tool_input, llm_client=self.llm, task_ctx=task_ctx
                )
                if tool_result is None:
                    tool_result = {"success": False, "error": "toolhub_returned_none"}
                elif not isinstance(tool_result, dict):
                    tool_result = {"success": True, "result": tool_result}

                formatted_result = self._format_tool_result(tool_result, tool_type)
                if trace and hasattr(trace, "on_tool_call_end"):
                    trace.on_tool_call_end(
                        step_id or 0,
                        tool_type,
                        tool_result.get("success", True),
                        result_preview=formatted_result,
                        error=tool_result.get("error"),
                    )
                return {
                    "step_id": step.get("id"),
                    "success": tool_result.get("success", True),
                    "result": formatted_result,
                    "raw_result": tool_result,
                    "method": f"toolhub_{tool_type}",
                    "tool_input": tool_input
                }
            except Exception as e:
                logger.error(f"[步骤{step_id}] ToolHub调用失败: {e}")
                if trace and hasattr(trace, "on_tool_call_end"):
                    trace.on_tool_call_end(step_id or 0, tool_type, False, error=str(e))
                logger.warning(f"[步骤{step_id}] ToolHub失败，降级到直接推理")
                return await self._direct_reasoning(step, context)

        # 如果按名字找不到，尝试按“功能相似”查找并并发调用
        if self.tool_hub:
            inferred_cap = self._infer_capability_from_step(step)
            if inferred_cap:
                logger.info(f"[步骤{step_id}] 工具名 '{tool_type}' 未找到，尝试按能力 '{inferred_cap}' 查找功能相似工具")
                try:
                    tool_input = self._prepare_tool_input(step, context)
                    task_ctx = (context or {}).get("task_ctx")
                    tool_result = await self.tool_hub.execute_by_capability(
                        inferred_cap, tool_input, max_parallel=3, llm_client=self.llm, task_ctx=task_ctx
                    )
                    if tool_result.get("success"):
                        formatted_result = self._format_tool_result(tool_result, tool_type)
                        return {
                            "step_id": step.get("id"),
                            "success": True,
                            "result": formatted_result,
                            "raw_result": tool_result,
                            "method": f"toolhub_capability_{inferred_cap}",
                            "tool_input": tool_input,
                        }
                    logger.warning(f"[步骤{step_id}] 能力 '{inferred_cap}' 的所有工具都失败，继续降级")
                except Exception as e:
                    logger.warning(f"[步骤{step_id}] 按能力查找失败: {e}，继续降级")

        if self.tool_registry:
            # 从工具注册表获取工具
            tool = self.tool_registry.get_tool(tool_type)
            if tool:
                try:
                    # 准备工具输入
                    tool_input = self._prepare_tool_input(step, context)
                    tool_input_preview = ""
                    try:
                        tool_input_preview = str(tool_input)[:100] if tool_input else "空"
                    except Exception:
                        tool_input_preview = "空"
                    logger.info(f"[步骤{step_id}] 工具输入: {tool_input_preview}")
                    
                    if not tool_input and tool_type == "calculate":
                        # 计算器工具需要有效的输入
                        logger.warning(f"[步骤{step_id}] 计算器工具输入为空，降级到直接推理")
                        # 降级到直接推理
                        return await self._direct_reasoning(step, context)
                    
                    # 调用工具（带重试机制）
                    from ..utils.retry import retry_with_backoff
                    from ..utils.metrics import get_metrics
                    from ..config.config_loader import get_config
                    
                    config = get_config()
                    max_retries = (config.get_section("tools") or {}).get("max_retries", 2)
                    
                    async def _execute_tool():
                        return await tool.execute(tool_input)
                    
                    try:
                        tool_result = await retry_with_backoff(
                            _execute_tool,
                            max_retries=max_retries,
                            initial_delay=0.5,
                            max_delay=5.0,
                            retryable_exceptions=(Exception,),
                            on_retry=lambda attempt, error: logger.warning(
                                f"[步骤{step_id}] 工具执行失败，第{attempt}次重试: {error}"
                            )
                        )
                    except Exception as e:
                        logger.error(f"[步骤{step_id}] 工具执行重试{max_retries}次后仍然失败: {e}")
                        get_metrics().record_error(f"ToolExecutionFailed_{tool_type}", str(e))
                        # 降级到直接推理
                        return await self._direct_reasoning(step, context)
                    
                    # 工具返回值规范化：必须是 dict
                    if tool_result is None:
                        tool_result = {"success": False, "error": "工具返回None"}
                    elif not isinstance(tool_result, dict):
                        tool_result = {"success": True, "result": tool_result}

                    # 格式化工具结果供后续使用
                    formatted_result = self._format_tool_result(tool_result, tool_type)
                    
                    return {
                        "step_id": step.get("id"),
                        "success": tool_result.get("success", True),
                        "result": formatted_result,
                        "raw_result": tool_result,
                        "method": f"tool_{tool_type}",
                        "tool_input": tool_input
                    }
                except Exception as e:
                    logger.error(f"[步骤{step_id}] 工具调用失败: {e}")
                    logger.warning(f"[步骤{step_id}] 工具调用失败，降级到直接推理")
                    # 降级到直接推理
                    return await self._direct_reasoning(step, context)
            else:
                # 工具不存在，降级到直接推理
                logger.warning(f"[步骤{step_id}] 工具 {tool_type} 不存在，降级到直接推理")
                return await self._direct_reasoning(step, context)
        
        # 工具注册表不可用，降级到直接推理
        logger.warning(f"[步骤{step_id}] 工具注册表不可用，降级到直接推理")
        return await self._direct_reasoning(step, context)
    
    def _format_tool_result(self, tool_result: Dict[str, Any], tool_type: str) -> str:
        """
        格式化工具结果，并应用长度限制以控制token消耗。
        
        根据工具类型设置不同的最大长度：
        - 计算类: 100字符
        - 时间类: 200字符
        - 搜索类: 500字符（已优化，只取前3个结果）
        - 历史类: 1000字符
        - 其他: 500字符
        """
        # 定义工具类型的最大长度限制
        MAX_LENGTHS = {
            "calculate": 100,
            "get_time": 200,
            "search_web": 500,
            "advanced_web_search": 800,
            "get_conversation_history": 1000,
            "default": 500,
        }
        
        def _truncate(text: str, max_len: int) -> str:
            """智能截断文本，保留关键部分"""
            if len(text) <= max_len:
                return text
            # 尝试在句子边界截断
            truncated = text[:max_len - 10]
            last_period = truncated.rfind("。")
            last_newline = truncated.rfind("\n")
            cut_point = max(last_period, last_newline)
            if cut_point > max_len * 0.7:  # 如果截断点不太靠前
                truncated = text[:cut_point + 1]
            else:
                truncated = text[:max_len - 10]
            return truncated + "...（已截断）"
        
        result_text = ""
        max_len = MAX_LENGTHS.get(tool_type, MAX_LENGTHS["default"])
        
        if tool_type in ("search_web", "advanced_web_search"):
            results = tool_result.get("results", [])
            if results:
                formatted = []
                for r in results[:3]:  # 只取前3个结果
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")
                    formatted.append(f"{title}: {snippet}")
                result_text = "\n".join(formatted)
            else:
                result_text = "未找到相关信息"
        elif tool_type == "calculate":
            result_text = str(tool_result.get("result", ""))
        elif tool_type == "get_time":
            # 时间工具返回格式化的时间字符串
            result_text = tool_result.get("formatted", str(tool_result.get("current_time", "")))
        elif tool_type == "get_conversation_history":
            # 对话历史工具返回格式化的历史记录
            if "formatted" in tool_result:
                result_text = tool_result["formatted"]
            elif "content" in tool_result:
                result_text = tool_result["content"]
            elif "messages" in tool_result:
                messages = tool_result["messages"]
                formatted = []
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    formatted.append(f"[{role}]: {content}")
                result_text = "\n".join(formatted)
            else:
                result_text = str(tool_result)
        else:
            result_text = str(tool_result)
        
        # 应用长度限制
        return _truncate(result_text, max_len)
    
    def _prepare_tool_input(self, step: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """准备工具输入"""
        tool_type = step.get("tool_type", "")
        description = step.get("description", "")
        
        if not description:
            logger.warning("步骤描述为空，无法准备工具输入")
            return ""
        
        # 根据工具类型准备不同的输入
        if tool_type == "calculate":
            # 对于计算器，尝试从描述中提取数学表达式
            # 如果描述包含数字和运算符，尝试提取
            import re
            # 查找数学表达式模式（如 "2 + 3", "距离 / 时间" 等）
            math_pattern = r'[\d+\-*/().\s]+'
            matches = re.findall(math_pattern, description)
            if matches:
                # 取最长的匹配作为表达式
                expression = max(matches, key=len).strip()
                if len(expression) > 2:  # 至少包含一些内容
                    logger.info(f"从描述中提取数学表达式: {expression}")
                    return expression
            
            # 如果没有找到数学表达式，检查上下文是否有数值结果
            if context:
                step_results = context.get("step_results", [])
                for result in reversed(step_results):
                    if result.get("success"):
                        result_value = result.get("result", "")
                        result_str = str(result_value).strip()
                        # 排除时间格式（如 "2024-06-12T10:30:45Z"）
                        if not re.match(r'\d{4}-\d{2}-\d{2}', result_str):
                            # 检查是否是纯数学表达式
                            if re.match(r'^[\d+\-*/().\s]+$', result_str):
                                logger.info(f"使用上下文中的数值结果: {result_value}")
                                return result_str[:100]
            
            logger.warning(f"无法从描述中提取数学表达式: {description}")
            return ""  # 返回空字符串，让计算器工具处理错误
        
        elif tool_type in ("search_web", "advanced_web_search"):
            # 搜索类：从描述提取关键词，空则用上一步结果做二跳搜索
            import re
            keywords = re.sub(r"(搜索|查找|检索|search|query)\s*[：:]\s*", "", description, flags=re.I).strip()
            keywords = keywords.replace("搜索", "").replace("查找", "").replace("检索", "").replace("search", "").strip()
            if not keywords and context:
                step_results = context.get("step_results", [])
                for result in reversed(step_results):
                    if result.get("success"):
                        val = str(result.get("result", "")).strip()
                        if val and len(val) > 10:
                            keywords = val[:300]
                            logger.info(f"搜索输入使用上一步结果作为 query（前 300 字）")
                            break
            if not keywords:
                keywords = description
            if tool_type == "search_web":
                return keywords
            # advanced_web_search：返回 dict，便于传 fetch_content
            desc_lower = description.lower()
            fetch_content = any(
                k in desc_lower for k in [
                    "精确", "具体数字", "exact", "extract", "从文中", "从页面",
                    "according to the article", "in the paper", "from the page",
                ]
            )
            return {"query": keywords, "num_results": 5, "fetch_content": fetch_content}
        elif tool_type == "get_time":
            # 时间工具，传递描述作为查询
            return description
        elif tool_type == "get_conversation_history":
            # 对话历史工具，根据描述确定查询类型
            desc_lower = description.lower()
            if "最后" in desc_lower or "最近" in desc_lower or "上一条" in desc_lower:
                if "用户" in desc_lower or "user" in desc_lower:
                    return "last_user"
                else:
                    return "last"
            elif "全部" in desc_lower or "所有" in desc_lower or "all" in desc_lower:
                return "all"
            else:
                # 默认返回最近10条
                return "10"
        
        else:
            # 其他工具，使用描述或上下文结果
            if context:
                step_results = context.get("step_results", [])
                if step_results:
                    last_result = step_results[-1]
                    if last_result.get("success"):
                        result_value = last_result.get("result", "")
                        if result_value:
                            return str(result_value)[:200]
            
            return description


class VerificationAgent:
    """
    验证Agent - 负责验证信息准确性和一致性
    """
    
    def __init__(self, llm=None):
        self.llm = llm
        logger.info("VerificationAgent initialized")
    
    async def verify_result(self, result: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        验证结果
        
        Args:
            result: 待验证的结果
            context: 上下文信息（包含其他步骤的结果）
        
        Returns:
            验证结果（包含置信度、一致性检查等）
        """
        logger.info(f"VerificationAgent: 验证步骤 {result.get('step_id')} 的结果")
        
        verification = {
            "step_id": result.get("step_id"),
            "verified": False,
            "confidence": 0.0,
            "consistency_check": False,
            "cross_validation": False,
            "issues": []
        }
        
        # 1. 基本验证
        if result.get("success"):
            verification["verified"] = True
            verification["confidence"] = 0.7  # 基础置信度
        
        # 2. 一致性检查（如果有多个相关结果）
        if context and context.get("step_results"):
            consistency = self._check_consistency(result, context["step_results"])
            verification["consistency_check"] = consistency
            if consistency:
                verification["confidence"] += 0.1
        
        # 3. 交叉验证（如果可能）
        cross_validation = await self._cross_validate(result, context)
        verification["cross_validation"] = cross_validation
        if cross_validation:
            verification["confidence"] += 0.1
        
        # 4. 逻辑检查
        logic_check = self._check_logic(result, context)
        if logic_check:
            verification["confidence"] += 0.1
        else:
            verification["issues"].append("逻辑检查未通过")
        
        # 限制置信度在0-1之间
        verification["confidence"] = min(1.0, verification["confidence"])
        
        logger.info(f"VerificationAgent: 验证完成，置信度={verification['confidence']:.2f}")
        return verification
    
    def _check_consistency(self, result: Dict[str, Any], other_results: List[Dict[str, Any]]) -> bool:
        """检查与其他结果的一致性"""
        if not other_results:
            return True
        
        result_value = str(result.get("result", "")).strip().lower()
        
        # 检查是否与其他结果一致
        for other_result in other_results:
            if not other_result.get("success"):
                continue
            
            other_value = str(other_result.get("result", "")).strip().lower()
            
            # 简单的一致性检查：如果结果完全相同，认为一致
            if result_value == other_value:
                continue
            
            # 如果结果差异很大，可能不一致
            # 这里使用简单的字符串相似度（可以改进为更复杂的算法）
            similarity = self._string_similarity(result_value, other_value)
            if similarity < 0.5:  # 相似度低于50%，可能不一致
                logger.warning(f"结果一致性检查：相似度 {similarity:.2f} < 0.5")
                return False
        
        return True
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """计算字符串相似度（简单的Jaccard相似度）"""
        if not s1 or not s2:
            return 0.0
        
        set1 = set(s1.split())
        set2 = set(s2.split())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    async def _cross_validate(self, result: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """交叉验证"""
        # 如果结果来自工具，可以尝试从其他来源验证
        # 例如：如果结果来自搜索工具，可以尝试用LLM验证
        # 这里简化实现，返回True表示验证通过
        return True
    
    def _check_logic(self, result: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """逻辑检查"""
        result_value = str(result.get("result", "")).strip()
        
        # 检查数值合理性
        import re
        # 查找数字
        numbers = re.findall(r'-?\d+\.?\d*', result_value)
        for num_str in numbers:
            try:
                num = float(num_str)
                # 检查是否在合理范围内（例如：不是天文数字）
                if abs(num) > 1e15:
                    logger.warning(f"逻辑检查：发现异常大的数值 {num}")
                    return False
            except ValueError:
                pass
        
        # 检查时间格式合理性
        time_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 日期
            r'\d{1,2}:\d{2}(:\d{2})?',  # 时间
        ]
        for pattern in time_patterns:
            matches = re.findall(pattern, result_value)
            for match in matches:
                # 可以添加更详细的时间验证逻辑
                pass
        
        return True


class CoordinationAgent:
    """
    协调Agent - 负责协调多个Agent的工作，管理整体流程
    """
    
    def __init__(self, planning_agent: PlanningAgent, execution_agent: ExecutionAgent, 
                 verification_agent: VerificationAgent):
        self.planning_agent = planning_agent
        self.execution_agent = execution_agent
        self.verification_agent = verification_agent
        self.state: Optional[AgentState] = None
        logger.info("CoordinationAgent initialized")
    
    
    async def process_question(self, question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理用户问题的主入口
        
        Args:
            question: 用户问题
            context: 初始上下文
        
        Returns:
            最终答案和处理过程
        """
        # 验证输入
        if not question or not question.strip():
            logger.error("问题为空")
            return {
                "success": False,
                "error": "问题不能为空",
                "question": question
            }
        
        question = question.strip()
        logger.info(f"CoordinationAgent: 开始处理问题 - {question[:100]}...")
        
        # 初始化状态
        try:
            self.state = AgentState(
                question=question,
                conversation_history=[],
                task_plan=None,
                current_step=0,
                step_results=[],
                tool_calls=[],
                verification_results=[],
                final_answer=None,
                confidence=0.0,
                errors=[],
                metadata=context or {}
            )
        except Exception as e:
            logger.error(f"初始化状态失败: {e}")
            return {
                "success": False,
                "error": f"初始化失败: {str(e)}",
                "question": question
            }
        
        try:
            # 1. 任务规划
            if not self.planning_agent:
                raise Exception("规划Agent未初始化")
            
            plan = self.planning_agent.decompose_task(question, context)
            if not plan:
                raise Exception("任务规划失败，返回空计划")
            
            self.state["task_plan"] = plan
            
            # 2. 执行计划
            steps = plan.get("steps", [])
            if not steps:
                logger.warning("任务计划中没有步骤")
                # 即使没有步骤，也尝试生成答案
                final_answer = await self._synthesize_answer()
                return {
                    "success": True,
                    "answer": final_answer,
                    "confidence": 0.5,
                    "reasoning": "任务无需分解，直接生成答案",
                    "errors": []
                }
            
            for step in steps:
                # 检查依赖
                if not self._check_dependencies(step, self.state["step_results"]):
                    logger.warning(f"步骤 {step.get('id')} 的依赖未满足，跳过")
                    continue
                
                # 执行步骤
                step_result = await self.execution_agent.execute_step(
                    step, 
                    {"step_results": self.state["step_results"]}
                )
                self.state["step_results"].append(step_result)
                
                # 验证结果
                verification = await self.verification_agent.verify_result(
                    step_result,
                    {"step_results": self.state["step_results"]}
                )
                self.state["verification_results"].append(verification)
                
                # 如果验证失败，记录错误
                if not verification.get("verified") or verification.get("confidence", 0) < 0.5:
                    self.state["errors"].append(
                        f"步骤 {step.get('id')} 验证失败: {verification.get('issues', [])}"
                    )
            
            # 3. 合成最终答案
            final_answer = await self._synthesize_answer()
            self.state["final_answer"] = final_answer
            
            # 4. 计算整体置信度
            self.state["confidence"] = self._calculate_overall_confidence()
            
            logger.info(f"CoordinationAgent: 处理完成，置信度={self.state['confidence']:.2f}")
            
            return {
                "success": True,
                "answer": final_answer,
                "confidence": self.state["confidence"],
                "reasoning": self._format_reasoning(),
                "errors": self.state["errors"]
            }
        except Exception as e:
            logger.error(f"CoordinationAgent: 处理失败 - {e}")
            return {
                "success": False,
                "error": str(e),
                "question": question
            }
    
    def _check_dependencies(self, step: Dict[str, Any], completed_results: List[Dict[str, Any]]) -> bool:
        """检查步骤依赖是否满足"""
        dependencies = step.get("dependencies", [])
        if not dependencies:
            return True
        
        completed_ids = {r.get("step_id") for r in completed_results if r.get("success")}
        return all(dep_id in completed_ids for dep_id in dependencies)
    
    async def _synthesize_answer(self) -> str:
        """合成最终答案"""
        # 使用LLM整合所有步骤结果，生成最终答案
        step_results = self.state.get("step_results", [])
        
        if not step_results:
            logger.warning("没有步骤结果，无法生成答案")
            return "无法生成答案"
        
        # 检查是否有成功的步骤
        successful_results = [r for r in step_results if r.get("success")]
        if not successful_results:
            logger.warning("所有步骤都失败，尝试基于问题直接生成答案")
            # 即使所有步骤失败，也尝试直接回答用户问题
            question = self.state.get('question', '')
            if question and hasattr(self.planning_agent, 'llm') and self.planning_agent.llm:
                try:
                    try:
                        from ..prompts import get_prompt
                        prompt = get_prompt("synthesis_fallback_direct_answer", question=question)
                    except Exception:
                        prompt = f"请直接回答以下问题，给出简洁准确的答案：\n\n问题：{question}\n\n请直接给出答案，不要包含推理过程。"
                    if not prompt:
                        prompt = f"请直接回答以下问题：\n\n问题：{question}\n\n请直接给出答案，不要包含推理过程。"
                    if hasattr(self.planning_agent.llm, 'generate_async'):
                        answer = await self.planning_agent.llm.generate_async(prompt)
                    else:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if hasattr(asyncio, 'to_thread'):
                            answer = await asyncio.to_thread(self.planning_agent.llm.generate, prompt)
                        else:
                            answer = await loop.run_in_executor(None, lambda: self.planning_agent.llm.generate(prompt))
                    if answer and answer.strip():
                        return answer.strip()
                except Exception as e:
                    logger.error(f"直接回答问题失败: {e}")
            try:
                from ..prompts import get_prompt_raw
                fallback = get_prompt_raw("synthesis_fallback_no_answer").strip()
            except Exception:
                fallback = "抱歉，我无法回答这个问题。"
            return fallback or "抱歉，我无法回答这个问题。"
        
        # 如果有LLM，使用LLM合成
        if hasattr(self.planning_agent, 'llm') and self.planning_agent.llm:
            try:
                # 构建合成提示词
                context = "\n".join([
                    f"步骤{i+1}: {str(r.get('result', ''))[:200]}"  # 限制长度避免过长
                    for i, r in enumerate(successful_results)
                ])
                
                question = self.state.get('question', '') or "用户问题"
                try:
                    from ..prompts import get_prompt
                    prompt = get_prompt(
                        "synthesis_evidence_synthesis",
                        context=context,
                        question=question,
                    )
                except Exception:
                    prompt = f"基于以下步骤的结果，请生成一个简洁、准确的最终答案。\n\n步骤结果：\n{context}\n\n问题：{question}\n\n请直接给出最终答案，不要包含推理过程或多余解释。"
                if not prompt:
                    prompt = f"基于以下步骤的结果，请生成最终答案。\n\n步骤结果：\n{context}\n\n问题：{question}\n\n请直接给出最终答案。"
                
                # 使用异步方法（如果可用），否则在线程池中执行同步方法
                if hasattr(self.planning_agent.llm, 'generate_async'):
                    answer = await self.planning_agent.llm.generate_async(prompt)
                else:
                    # 在线程池中执行同步方法，避免阻塞事件循环
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if hasattr(asyncio, 'to_thread'):
                        answer = await asyncio.to_thread(self.planning_agent.llm.generate, prompt)
                    else:
                        answer = await loop.run_in_executor(None, lambda: self.planning_agent.llm.generate(prompt))
                
                if answer and answer.strip():
                    return answer.strip()
                else:
                    logger.warning("LLM合成的答案为空")
            except Exception as e:
                logger.exception(f"答案合成失败: {e}")  # 使用 exception 记录完整堆栈
        
        # 降级：使用最后一个成功步骤的结果
        for result in reversed(successful_results):
            result_value = result.get("result")
            if result_value:
                answer_str = str(result_value).strip()
                if answer_str:
                    return answer_str
        
        return "无法生成答案"
    
    def _calculate_overall_confidence(self) -> float:
        """计算整体置信度"""
        if not self.state["verification_results"]:
            return 0.0
        
        confidences = [v.get("confidence", 0.0) for v in self.state["verification_results"]]
        if confidences:
            return sum(confidences) / len(confidences)
        return 0.0
    
    def _format_reasoning(self) -> str:
        """格式化推理过程"""
        reasoning = []
        reasoning.append(f"问题: {self.state['question']}")
        
        if self.state["task_plan"]:
            reasoning.append(f"任务计划: {len(self.state['task_plan'].get('steps', []))} 个步骤")
        
        for i, result in enumerate(self.state["step_results"]):
            reasoning.append(f"步骤 {i+1}: {result.get('method', 'unknown')} - {result.get('result', 'N/A')}")
        
        return "\n".join(reasoning)


class MultiAgentSystem:
    """
    多Agent系统 - 主入口类
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 初始化LLM客户端（共享）- 添加超时保护
        llm = None
        try:
            from ..llm.llm_client import LLMClient
            # 从配置中获取模型配置
            model_config = self.config.get("model", {}) if self.config else {}
            logger.info("正在初始化LLM客户端...")
            llm = LLMClient(config=model_config)
            logger.info("LLM客户端初始化成功（延迟验证）")
        except Exception as e:
            # 严格模式：如果 LLM 配置不全，应当快速失败（避免“占位实现 + 看似能跑其实全错”）
            raise
        
        # 初始化各个Agent
        self.planning_agent = PlanningAgent(llm=llm)
        self.execution_agent = ExecutionAgent(llm=llm)
        self.verification_agent = VerificationAgent(llm=llm)
        self.coordination_agent = CoordinationAgent(
            self.planning_agent,
            self.execution_agent,
            self.verification_agent
        )
        
        logger.info("MultiAgentSystem initialized")

    def set_available_tools(self, tool_names: List[str]) -> None:
        """由编排器注入当前所有可用工具名称，供规划层构建提示词使用。"""
        try:
            self.planning_agent.set_available_tools(tool_names)
        except Exception as e:
            logger.debug(f"MultiAgentSystem.set_available_tools failed: {e}")
    
    async def process(self, question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理用户问题
        
        Args:
            question: 用户问题
            context: 上下文信息
        
        Returns:
            处理结果
        """
        return await self.coordination_agent.process_question(question, context)
    
    def get_state(self) -> Optional[AgentState]:
        """获取当前状态"""
        return self.coordination_agent.state
