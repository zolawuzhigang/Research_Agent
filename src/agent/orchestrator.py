"""
Agent编排器 - 核心控制器（支持多Agent系统）
"""

import re
from typing import Dict, Any, Optional
from loguru import logger

# 导入多Agent系统
from .multi_agent_system import MultiAgentSystem
from .langgraph_workflow import LangGraphWorkflow
from .memory import MemoryManager
from ..tools import ToolRegistry, SearchTool, CalculatorTool, WorkspaceFilesTool
from ..tools.time_tool import TimeTool
from ..config.config_loader import get_config
from ..toolhub import ToolHub, ToolCandidate
from pathlib import Path


class AgentOrchestrator:
    """
    Agent主控制器，负责协调各个模块
    支持单Agent和多Agent两种模式
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, use_multi_agent: bool = True):
        """
        初始化Agent编排器
        
        Args:
            config: 配置字典（可选，如果不提供则从配置文件加载）
            use_multi_agent: 是否使用多Agent系统（默认True）
        """
        # 加载配置
        if config is None:
            config_loader = get_config()
            self.config = config_loader.config
        else:
            self.config = config
        
        self.use_multi_agent = use_multi_agent
        self.state = {}
        self.tool_hub: Optional[ToolHub] = None
        
        # 初始化记忆管理器
        memory_config = self.config.get("memory", {})
        self.memory = MemoryManager(
            short_term_size=memory_config.get("short_term_size", 100)
        )
        
        if use_multi_agent:
            # 初始化多Agent系统
            # 注意：这里必须传入“已解析后的 self.config”，否则会把 None 传下去，
            # LLMClient 会回退到 config_loader 的默认配置（newapi/qwen），导致连接超时。
            self.multi_agent = MultiAgentSystem(self.config)
            
            # 初始化工具注册表
            self.tool_registry = ToolRegistry()
            self._register_default_tools()
            
            # 初始化LangGraph工作流
            self.workflow = LangGraphWorkflow(agents={
                "planning": self.multi_agent.planning_agent,
                "execution": self.multi_agent.execution_agent,
                "verification": self.multi_agent.verification_agent
            })
            
            logger.info("AgentOrchestrator initialized (Multi-Agent mode)")
        else:
            self.multi_agent = None
            self.workflow = None
            logger.info("AgentOrchestrator initialized (Single-Agent mode)")
    
    def _register_default_tools(self):
        """注册默认工具"""
        from ..tools import ConversationHistoryTool, AdvancedWebSearchTool
        
        # 注册搜索工具
        search_tool = SearchTool()
        self.tool_registry.register(search_tool)

        # 注册高级搜索工具（多引擎 + 正文抓取），用于复杂检索与信息抽取
        try:
            adv_search_tool = AdvancedWebSearchTool()
            self.tool_registry.register(adv_search_tool)
        except Exception as e:
            logger.warning(f"AdvancedWebSearchTool 初始化失败，跳过: {e}")
        
        # 注册计算工具
        calc_tool = CalculatorTool()
        self.tool_registry.register(calc_tool)
        
        # 注册时间工具
        time_tool = TimeTool()
        self.tool_registry.register(time_tool)
        
        # 注册对话历史工具
        history_tool = ConversationHistoryTool(memory_manager=self.memory)
        self.tool_registry.register(history_tool)

        # 注册工作区文件列表工具（用于回答“当前目录/根目录下有哪些文件”）
        try:
            project_root = Path(__file__).resolve().parents[2]
            fs_tool = WorkspaceFilesTool(workspace_root=project_root)
            self.tool_registry.register(fs_tool)
        except Exception as e:
            logger.warning(f"WorkspaceFilesTool 初始化失败: {e}")
        
        # 将工具注册表传递给执行Agent
        if self.multi_agent:
            self.multi_agent.execution_agent.tool_registry = self.tool_registry

            # Build ToolHub: tools > skills > mcps
            hub = ToolHub()
            # native tools
            for tname, tool in self.tool_registry.tools.items():
                desc = getattr(tool, "description", "") or ""
                # 自动提取能力标签
                from ..toolhub import _extract_capabilities_from_description
                caps = _extract_capabilities_from_description(desc, tname)
                hub.register_candidate(
                    ToolCandidate(
                        name=tname,
                        source="tools",
                        tool=tool,
                        priority=0,
                        meta={"capabilities": caps, "description": desc},
                    )
                )

            # skills tools (scan src/skills)
            try:
                from ..skills.loader import load_skill_tools, load_skills_from_skillmd
                from ..skills.skill_tool import SkillTool
                skills_cfg = (get_config().get_section("skills") or {})
                skills_enabled = bool(skills_cfg.get("enabled", True))
                skills_dir_cfg = skills_cfg.get("directory") or "src/skills"

                # 支持绝对路径或相对项目根目录的路径（例如 "src/skills"）
                cfg_path = Path(skills_dir_cfg)
                if cfg_path.is_absolute():
                    skills_dir = cfg_path
                else:
                    project_root = Path(__file__).resolve().parents[2]
                    skills_dir = project_root / cfg_path

                if skills_enabled:
                    # legacy python-based skills
                    for st in load_skill_tools(skills_dir):
                        n = getattr(st, "name", None)
                        if n:
                            desc = getattr(st, "description", "") or ""
                            from ..toolhub import _extract_capabilities_from_description
                            caps = _extract_capabilities_from_description(desc, n)
                            hub.register_candidate(
                                ToolCandidate(
                                    name=n,
                                    source="skills",
                                    tool=st,
                                    priority=1,
                                    meta={"kind": "python", "capabilities": caps, "description": desc},
                                )
                            )

                    # Claude-style SKILL.md skills
                    for doc in load_skills_from_skillmd(skills_dir):
                        st = SkillTool(document=doc, llm_client=self.multi_agent.execution_agent.llm)
                        desc = doc.meta.description or ""
                        from ..toolhub import _extract_capabilities_from_description
                        caps = _extract_capabilities_from_description(desc, doc.meta.name)
                        hub.register_candidate(
                            ToolCandidate(
                                name=doc.meta.name,
                                source="skills",
                                tool=st,
                                priority=1,
                                meta={"kind": "skillmd", "description": desc, "capabilities": caps},
                            )
                        )
            except Exception as e:
                logger.warning(f"Skill loading skipped: {e}")

            # mcp tools (config-driven)
            try:
                from ..mcps.loader import load_mcp_tools
                mcp_cfg = (get_config().get_section("mcps") or {})
                for mt in load_mcp_tools(mcp_cfg):
                    n = getattr(mt, "name", None)
                    if n:
                        desc = getattr(mt, "description", "") or ""
                        from ..toolhub import _extract_capabilities_from_description
                        caps = _extract_capabilities_from_description(desc, n)
                        hub.register_candidate(
                            ToolCandidate(
                                name=n,
                                source="mcps",
                                tool=mt,
                                priority=2,
                                meta={"type": "mcp", "capabilities": caps, "description": desc},
                            )
                        )
            except Exception as e:
                logger.warning(f"MCP loading skipped: {e}")

            # 保存 ToolHub 引用，便于其他模块（如快速路径、自描述）使用
            self.tool_hub = hub
            self.multi_agent.execution_agent.tool_hub = hub

            # let PlanningAgent know all available tool names (native + skills + mcps)
            try:
                tool_names = [item["name"] for item in hub.list_tools()]
                if hasattr(self.multi_agent, "set_available_tools"):
                    self.multi_agent.set_available_tools(tool_names)
                elif hasattr(self.multi_agent.planning_agent, "set_available_tools"):
                    self.multi_agent.planning_agent.set_available_tools(tool_names)
            except Exception as e:
                logger.debug(f"Failed to propagate available tools to PlanningAgent: {e}")
    
    async def process_task(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        处理任务的主入口
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            处理结果
        """
        logger.info(f"Processing task: {task}")

        # 轻量级问题快速路径（闲聊/自我介绍/能力说明等）
        fast_result = self._maybe_fast_path(task, context)
        if fast_result is not None:
            logger.info("使用快速路径直接返回结果")
            # 写入对话历史（不使用 snapshot）
            self.memory.add_conversation("user", task, context)
            if fast_result.get("answer"):
                self.memory.add_conversation("assistant", fast_result["answer"], {
                    "confidence": fast_result.get("confidence", 0.0),
                    "reasoning": fast_result.get("reasoning", "")
                })
            return fast_result

        # 创建历史快照（处理前历史），用于处理涉及"之前"、"刚刚"等时间语义的查询
        self.memory.create_snapshot()
        
        # 添加到对话历史
        self.memory.add_conversation("user", task, context)

        # 请求级缓存（适用于“同问题重复问”的业务/压测场景）
        try:
            from ..config.config_loader import get_config
            from ..utils.cache import get_cache

            cfg = get_config()
            perf = cfg.get_section("performance") or {}
            cache_enabled = bool(perf.get("cache_enabled", True))
            cache_ttl = int(perf.get("cache_ttl", 3600))

            # 这些问题强依赖“当前时刻/对话历史”，缓存会引入错误，直接跳过
            task_lower = (task or "").lower()
            skip_cache_keywords = [
                "几点", "现在时间", "当前时间", "utc", "timezone", "时区", "日期", "今天", "明天", "昨天",
                "刚刚", "刚才", "之前", "上一个", "上一条", "对话历史", "你刚刚", "我刚刚", "我们刚才",
                "what time", "current time", "now", "previous", "last message", "conversation history",
                "what did i ask", "last question", "previous question",
            ]
            skip_cache = any(k in task_lower for k in skip_cache_keywords)

            if cache_enabled and not skip_cache:
                cache = get_cache()
                cache_key = cache._generate_key("process_task", task)
                cached_result = cache.get(cache_key)
                if isinstance(cached_result, dict) and cached_result.get("answer"):
                    logger.info("命中请求级缓存，直接返回缓存答案")
                    # 添加助手回复到对话历史
                    self.memory.add_conversation("assistant", cached_result["answer"], {
                        "confidence": cached_result.get("confidence", 0.0),
                        "reasoning": cached_result.get("reasoning", "")
                    })
                    # 清除历史快照
                    self.memory.clear_snapshot()
                    return cached_result
        except Exception as e:
            # 缓存不可用不影响主流程
            logger.debug(f"请求级缓存检查失败，继续主流程: {e}")

        # 可观测性：创建 TraceContext 并注入 context，供工作流/执行层记录工具调用、推理、证据整合等
        run_context = dict(context) if context else {}
        trace_ctx = None
        try:
            from ..config.config_loader import get_config
            from ..observability import TraceContext, NullTraceContext
            cfg = get_config()
            obs = (cfg.get_section("observability") or {}) if cfg else {}
            if obs.get("enabled"):
                trace_ctx = TraceContext(
                    max_events=int(obs.get("max_events", 200)),
                    max_preview=int(obs.get("max_preview", 500)),
                )
                run_context["_trace"] = trace_ctx
            else:
                run_context["_trace"] = NullTraceContext()
        except Exception as e:
            logger.debug(f"可观测性初始化失败（忽略）: {e}")
            run_context["_trace"] = None

        try:
            if self.use_multi_agent and self.workflow:
                # 使用多Agent系统 + LangGraph工作流
                result = await self.workflow.run(task, run_context)
            elif self.use_multi_agent and self.multi_agent:
                # 使用多Agent系统（简化模式）
                result = await self.multi_agent.process(task, run_context)
            else:
                # 使用单Agent模式（向后兼容）
                result = await self._process_single_agent(task, run_context)

            # 可观测性：将 trace 附带进返回结果，便于调试
            if trace_ctx is not None and hasattr(trace_ctx, "to_dict"):
                try:
                    from ..config.config_loader import get_config
                    obs_cfg = (get_config().get_section("observability") or {}) if get_config() else {}
                    if obs_cfg.get("include_in_response", True):
                        result = dict(result) if result else {}
                        result["trace"] = trace_ctx.to_dict()
                except Exception:
                    pass
            
            # 添加助手回复到对话历史
            if result.get("success") and result.get("answer"):
                self.memory.add_conversation("assistant", result["answer"], {
                    "confidence": result.get("confidence", 0.0),
                    "reasoning": result.get("reasoning", "")
                })

                # 写入请求级缓存（仅缓存“确定性较强/不依赖时刻与历史”的结果）
                try:
                    from ..config.config_loader import get_config
                    from ..utils.cache import get_cache
                    cfg = get_config()
                    perf = cfg.get_section("performance") or {}
                    cache_enabled = bool(perf.get("cache_enabled", True))
                    cache_ttl = int(perf.get("cache_ttl", 3600))

                    task_lower = (task or "").lower()
                    skip_cache_keywords = [
                        "几点", "现在时间", "当前时间", "utc", "timezone", "时区", "日期", "今天", "明天", "昨天",
                        "刚刚", "刚才", "之前", "上一个", "上一条", "对话历史", "你刚刚", "我刚刚", "我们刚才",
                        "what time", "current time", "now", "previous", "last message", "conversation history",
                    ]
                    skip_cache = any(k in task_lower for k in skip_cache_keywords)
                    if cache_enabled and not skip_cache:
                        cache = get_cache()
                        cache_key = cache._generate_key("process_task", task)
                        cache.set(cache_key, result, ttl=cache_ttl)
                except Exception as e:
                    logger.debug(f"写入请求级缓存失败（忽略）: {e}")
            
            # 清除历史快照
            self.memory.clear_snapshot()
            
            logger.info("Task processed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            # 即使出错也要清除快照
            self.memory.clear_snapshot()
            return {
                "success": False,
                "error": str(e),
                "task": task
            }
    
    async def _process_single_agent(self, task: str, context: Optional[Dict]) -> Dict[str, Any]:
        """
        单Agent模式处理（向后兼容）
        
        TODO: 实现单Agent逻辑
        """
        # 占位实现
        return {
            "success": True,
            "answer": "单Agent模式（待实现）",
            "task": task
        }
    
    def get_conversation_history(self, n: int = 10) -> list:
        """获取对话历史"""
        return self.memory.get_conversation_context(n)
    
    def clear_memory(self):
        """清空记忆"""
        self.memory.short_term.clear_context()
        logger.info("Memory cleared")

    # ---------------- 快速路径 & 自我描述 ----------------
    def _maybe_fast_path(self, task: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        检测是否可以走快速路径：
        - 闲聊问候（如“你好”“hi”）
        - 能力/自我介绍类问题（如“你都能干什么”“你会什么”“what can you do”）
        命中时直接生成答案，不走多Agent规划+执行链路，降低时延与token消耗。
        """
        text = (task or "").strip()
        if not text:
            return None

        lower = text.lower()

        # 简单问候：仅当文本较短且命中“整词”问候时走快速路径，避免 "hi" 命中 "this"、"history" 等
        def _is_simple_greeting(t: str) -> bool:
            if len(t) > 80:  # 长文本一律不当成简单问候
                return False
            # 中文问候：子串即可
            cn_greet = ["你好", "嗨", "早上好", "下午好", "晚上好"]
            if any(k in t for k in cn_greet):
                return True
            # 英文问候：整词匹配，避免 "hi" in "this", "hello" in "Othello"
            if re.search(r"\bhi\b", t, re.I):
                return True
            if re.search(r"\bhello\b", t, re.I):
                return True
            return False

        if _is_simple_greeting(lower):
            answer = (
                "你好，我是为科研辅助和商业调研场景设计的多智能体 Research Agent，"
                "可以帮你分解复杂问题、调用搜索/计算/时间/会话历史等工具，"
                "并生成结构化的分析和报告。你可以直接用自然语言告诉我你的需求。"
            )
            return {
                "success": True,
                "answer": answer,
                "confidence": 0.9,
                "reasoning": "快速路径：问候场景，直接用系统自我介绍回复。"
            }

        # 能力/自我介绍类问题
        capability_keywords = [
            "你都能干什么",
            "你会什么",
            "你能做什么",
            "你有什么能力",
            "what can you do",
            "what are you capable of",
            "what are your capabilities",
        ]
        if any(k in text for k in capability_keywords) or "能力" in text and "你" in text:
            answer = self._build_capability_answer()
            return {
                "success": True,
                "answer": answer,
                "confidence": 0.95,
                "reasoning": "快速路径：能力/自我介绍问题，基于真实工具与架构生成自描述。"
            }

        # 对话历史元问题（上一个问题 / 刚才问了什么 / 英文 what did I ask 等）快速路径
        history_keywords_cn = [
            "上一个问题",
            "上一个问",
            "刚刚问了你什么",
            "刚才问了你什么",
            "刚才一共问了你几个问题",
            "一共问了你几个问题",
            "都问了你什么问题",
            "都问了你什么",
        ]
        history_keywords_en = [
            "what did i ask",
            "what did i say",
            "last question",
            "my last question",
            "previous question",
            "what i asked",
            "what i just asked",
        ]
        if any(k in text for k in history_keywords_cn) or any(k in lower for k in history_keywords_en):
            answer = self._build_history_meta_answer(text)
            return {
                "success": True,
                "answer": answer,
                "confidence": 0.95,
                "reasoning": "快速路径：对话历史元问题，直接基于对话记录计算，避免LLM幻觉。"
            }

        return None

    def _build_capability_answer(self) -> str:
        """
        基于当前系统实际能力（ToolHub + 多Agent架构）构造自描述，
        避免LLM按“裸模型”错误描述自己。
        """
        parts = []
        parts.append("我是一个面向科研辅助、深度学习与商业调研场景的多智能体（Multi-Agent）系统。")
        parts.append("内部包含规划Agent、执行Agent、验证Agent和协调Agent，可以对复杂问题进行分解、执行和结果校验。")

        # 工具与技能
        tool_lines = []
        try:
            # 优先从 ToolHub 读取；若不存在则退回 ToolRegistry
            if self.tool_hub is not None:
                for item in self.tool_hub.list_tools():
                    name = item.get("name")
                    cands = item.get("candidates") or []
                    sources = sorted({c.get("source") for c in cands})
                    src_label = ",".join(sources)
                    tool_lines.append(f"- `{name}`（来源: {src_label}）")
            elif hasattr(self, "tool_registry"):
                for name, tool in self.tool_registry.tools.items():
                    desc = getattr(tool, "description", "") or ""
                    tool_lines.append(f"- `{name}`：{desc}")
        except Exception:
            # 工具列举失败不影响主描述
            pass

        if tool_lines:
            parts.append("目前已接入的代表性工具/技能包括：")
            parts.extend(tool_lines)
            parts.append(
                "其中 `search_web` 用于信息检索，`calculate` 用于数学计算，"
                "`get_time` 获取当前时间，`get_conversation_history` 用于查看对话历史，"
                "skills/mcps 则以 Skill 目录和配置化方式扩展更多专业能力（如 PDF 处理、Web 测试等）。"
            )

        parts.append(
            "在对话层面，我支持多轮对话记忆，可以理解上下文、执行多跳推理，"
            "并在工具调用失败或被限流时进行友好降级，尽量给出可用的参考答案。"
        )

        parts.append(
            "你可以让我：例如“帮我调研某个技术的发展趋势并给出报告”、"
            "“分析一段代码的Bug并给修复建议”、“比较两篇论文的核心贡献”等，我会自动规划步骤并调用合适的工具。"
        )

        return "\n".join(parts)

    def _build_history_meta_answer(self, query: str) -> str:
        """
        针对类似：
        - “我刚刚问了你什么问题？”
        - “我问你的上一个问题是什么？”
        - “我刚才一共问了你几个问题，我刚才都问了你什么问题？”
        这类对话历史元问题，直接从记忆中计算答案，避免完全依赖LLM推理带来的幻觉。
        """
        # 取当前已记录的对话（不包含本次提问）
        history = self.memory.get_conversation_context(n=50)
        user_msgs = [m for m in history if m.get("role") == "user"]

        # 过滤掉纯问候类消息（例如“你好”），更贴近“你之前真正问过的问题”
        greet_keywords = ["你好", "hi", "hello", "嗨", "早上好", "下午好", "晚上好"]

        def is_greeting(text: str) -> bool:
            t = (text or "").strip()
            if not t:
                return False
            lower = t.lower()
            return any(k in t for k in greet_keywords) or any(k in lower for k in ["hi", "hello"])

        question_msgs = [m for m in user_msgs if not is_greeting(str(m.get("content", "")))]

        # 提取问题文本
        questions = [str(m.get("content", "")).strip() for m in question_msgs if str(m.get("content", "")).strip()]

        if not questions:
            # 英文/中文统一：无历史问题时
            en_trigger = ["what did i ask", "last question", "previous question", "what i asked"]
            if any(k in (query or "").lower() for k in en_trigger):
                return "There are no previous questions in this conversation yet."
            return "目前对话中还没有检测到你之前明确提出的问题。"

        last_question = questions[-1]
        total = len(questions)

        text = (query or "").strip()
        text_lower = text.lower()
        parts = []

        # 英文“上一个问题”类
        en_last = ["what did i ask", "what did i say", "last question", "previous question", "what i asked", "what i just asked"]
        is_english_query = any(k in text_lower for k in en_last) or ("how many" in text_lower and "question" in text_lower)

        # 是否问“上一个问题”（中/英）
        if any(k in text for k in ["上一个问题", "刚刚问了你什么", "刚才问了你什么"]) or any(k in text_lower for k in en_last):
            if is_english_query:
                parts.append(f"Your last question was: {last_question}")
            else:
                parts.append(f"你上一个问题是：{last_question}")

        # 是否问“问了几个问题”（中/英）
        if "一共问了你几个问题" in text or "几 个问题" in text or "几個問題" in text or "几个问题" in text or ("how many" in text_lower and "question" in text_lower):
            if is_english_query:
                parts.append(f"You have asked {total} question(s) so far (excluding simple greetings).")
            else:
                parts.append(f"你刚才一共问了 {total} 个问题（不含简单问候）。")

        # 是否问“都问了你什么问题”（中/英）
        if "都问了你什么问题" in text or "都问了你什么" in text or "都问了你哪些" in text or ("what" in text_lower and "question" in text_lower and "ask" in text_lower):
            if is_english_query:
                parts.append("Your previous questions:")
            else:
                parts.append("你之前的问题如下：")
            for idx, q in enumerate(questions, start=1):
                parts.append(f"{idx}. {q}")

        # 如果用户没有明确拆分子问题，就给一个综合回答
        if not parts:
            if is_english_query:
                parts.append(f"Your last question was: {last_question}")
                parts.append(f"You have asked {total} question(s) so far (excluding simple greetings).")
                parts.append("Questions:")
            else:
                parts.append(f"你上一个问题是：{last_question}")
                parts.append(f"你之前一共问了 {total} 个问题（不含简单问候）。")
                parts.append("问题列表：")
            for idx, q in enumerate(questions, start=1):
                parts.append(f"{idx}. {q}")

        return "\n".join(parts)
