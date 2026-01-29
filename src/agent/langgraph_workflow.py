"""
LangGraph工作流编排 - 基于LangGraph的状态机工作流
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from loguru import logger

# 尝试导入 LangGraph（兼容 0.2x 与 1.x）：先确保 StateGraph/END 可用，再可选 add_messages
LANGGRAPH_AVAILABLE = False
add_messages = None
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
        add_messages = None  # 图可用但 add_messages 不可用时仍用图，状态用 List[Dict]
if not LANGGRAPH_AVAILABLE:
    logger.warning("LangGraph not available, using fallback implementation")

# 定义 WorkflowState（兼容 LangGraph 不可用或 add_messages 不可用）
if LANGGRAPH_AVAILABLE and add_messages is not None:
    try:
        class WorkflowState(TypedDict):
            """工作流状态（带 add_messages）"""
            question: str
            messages: Annotated[List[Dict], add_messages]
            task_plan: Optional[Dict[str, Any]]
            current_step: int
            step_results: List[Dict[str, Any]]
            final_answer: Optional[str]
            errors: List[str]
            metadata: Dict[str, Any]
    except Exception:
        LANGGRAPH_AVAILABLE = False
        add_messages = None

if LANGGRAPH_AVAILABLE and add_messages is None:
    class WorkflowState(TypedDict):
        """工作流状态（无 add_messages 时仍用图）"""
        question: str
        messages: List[Dict]
        task_plan: Optional[Dict[str, Any]]
        current_step: int
        step_results: List[Dict[str, Any]]
        final_answer: Optional[str]
        errors: List[str]
        metadata: Dict[str, Any]

if not LANGGRAPH_AVAILABLE:
    class WorkflowState(TypedDict):
        """工作流状态（简化版，LangGraph不可用时）"""
        question: str
        messages: List[Dict]
        task_plan: Optional[Dict[str, Any]]
        current_step: int
        step_results: List[Dict[str, Any]]
        final_answer: Optional[str]
        errors: List[str]
        metadata: Dict[str, Any]


class LangGraphWorkflow:
    """
    基于LangGraph的工作流编排器
    """
    
    def __init__(self, agents: Dict[str, Any] = None):
        self.agents = agents or {}
        self.graph = None
        
        if LANGGRAPH_AVAILABLE:
            self._build_graph()
        else:
            logger.warning("LangGraph不可用，使用简化工作流")
    
    def _build_graph(self):
        """构建LangGraph工作流图"""
        from langgraph.graph import StateGraph
        
        # 创建状态图
        workflow = StateGraph(WorkflowState)
        
        # 添加节点
        workflow.add_node("planning", self._planning_node)
        workflow.add_node("execution", self._execution_node)
        workflow.add_node("verification", self._verification_node)
        workflow.add_node("synthesis", self._synthesis_node)
        
        # 定义边
        workflow.set_entry_point("planning")
        workflow.add_edge("planning", "execution")
        workflow.add_conditional_edges(
            "execution",
            self._should_verify,
            {
                "verify": "verification",
                "continue": "execution",
                "synthesize": "synthesis"
            }
        )
        workflow.add_edge("verification", "execution")
        workflow.add_edge("synthesis", END)
        
        self.graph = workflow.compile()
    
    async def _planning_node(self, state: WorkflowState) -> WorkflowState:
        """规划节点"""
        logger.info("工作流: 进入规划节点")
        
        planning_agent = self.agents.get("planning")
        if planning_agent:
            plan = planning_agent.decompose_task(state["question"])
            state["task_plan"] = plan
            state["current_step"] = 0
        
        return state
    
    async def _execution_node(self, state: WorkflowState) -> WorkflowState:
        """执行节点"""
        logger.info(f"工作流: 进入执行节点，当前步骤 {state.get('current_step', 0)}")
        
        execution_agent = self.agents.get("execution")
        plan = state.get("task_plan")
        
        if execution_agent and plan:
            steps = plan.get("steps", [])
            current_step = state.get("current_step", 0)
            
            if current_step < len(steps):
                step = steps[current_step]
                result = await execution_agent.execute_step(
                    step,
                    {"step_results": state.get("step_results", [])}
                )
                state["step_results"].append(result)
                state["current_step"] = current_step + 1
        
        return state
    
    def _should_verify(self, state: WorkflowState) -> str:
        """判断是否应该验证"""
        plan = state.get("task_plan")
        current_step = state.get("current_step", 0)
        
        if not plan:
            return "synthesize"
        
        steps = plan.get("steps", [])
        
        # 如果所有步骤都执行完成，进入合成阶段
        if current_step >= len(steps):
            return "synthesize"
        
        # 否则验证当前步骤结果
        return "verify"
    
    async def _verification_node(self, state: WorkflowState) -> WorkflowState:
        """验证节点"""
        logger.info("工作流: 进入验证节点")
        
        verification_agent = self.agents.get("verification")
        step_results = state.get("step_results", [])
        
        if verification_agent and step_results:
            last_result = step_results[-1]
            verification = await verification_agent.verify_result(
                last_result,
                {"step_results": step_results}
            )
            
            # 如果验证失败，记录错误
            if not verification.get("verified"):
                errors = state.get("errors", [])
                errors.append(f"步骤验证失败: {verification.get('issues', [])}")
                state["errors"] = errors
        
        return state
    
    async def _synthesis_node(self, state: WorkflowState) -> WorkflowState:
        """合成节点"""
        logger.info("工作流: 进入合成节点")
        
        # 使用简单逻辑合成最终答案：
        # 优先选择「最近一个成功且有非空结果」的步骤，
        # 避免因为最后一步失败/为空而丢弃前面已经生成的高质量答案。
        step_results = state.get("step_results", [])
        if step_results:
            final_text = None
            # 从后往前找第一个 success=True 且 result 非空的步骤
            for res in reversed(step_results):
                if not res.get("success"):
                    continue
                val = str(res.get("result") or "").strip()
                if val:
                    final_text = val
                    break

            if not final_text:
                final_text = "无法生成答案"

            state["final_answer"] = final_text
        else:
            state["final_answer"] = "无法生成答案"
        
        return state
    
    async def run(self, question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行工作流
        
        Args:
            question: 用户问题
            context: 上下文信息
        
        Returns:
            处理结果
        """
        if not LANGGRAPH_AVAILABLE:
            # 使用简化工作流
            return await self._simple_workflow(question, context)
        
        # 初始化状态
        initial_state: WorkflowState = {
            "question": question,
            "messages": [],
            "task_plan": None,
            "current_step": 0,
            "step_results": [],
            "final_answer": None,
            "errors": [],
            "metadata": context or {}
        }
        
        # 运行图
        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            return {
                "success": True,
                "answer": final_state.get("final_answer"),
                "reasoning": self._format_reasoning(final_state),
                "errors": final_state.get("errors", [])
            }
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _simple_workflow(self, question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """简化工作流（当LangGraph不可用时）"""
        logger.info("使用简化工作流")
        
        # 顺序执行各个节点
        state = {
            "question": question,
            "task_plan": None,
            "current_step": 0,
            "step_results": [],
            "final_answer": None,
            "errors": [],
            "metadata": context or {}
        }
        
        # 规划
        state = await self._planning_node(state)
        
        # 执行所有步骤
        plan = state.get("task_plan")
        if plan:
            steps = plan.get("steps", [])
            for i, step in enumerate(steps):
                state["current_step"] = i
                state = await self._execution_node(state)
                
                # 验证
                if state.get("step_results"):
                    state = await self._verification_node(state)
        
        # 合成
        state = await self._synthesis_node(state)
        
        return {
            "success": True,
            "answer": state.get("final_answer"),
            "reasoning": self._format_reasoning(state),
            "errors": state.get("errors", [])
        }
    
    def _format_reasoning(self, state: Dict[str, Any]) -> str:
        """格式化推理过程"""
        reasoning = [f"问题: {state.get('question')}"]
        
        plan = state.get("task_plan")
        if plan:
            reasoning.append(f"计划: {len(plan.get('steps', []))} 个步骤")
        
        step_results = state.get("step_results", [])
        for i, result in enumerate(step_results):
            reasoning.append(f"步骤 {i+1}: {result.get('method', 'unknown')}")
        
        return "\n".join(reasoning)
