"""
Example skill tool: smalltalk (for business UX / contest robustness).
"""

from typing import Any, Dict
from src.tools.tool_registry import BaseTool


class SmallTalkTool(BaseTool):
    def __init__(self):
        super().__init__(name="smalltalk", description="处理闲聊/夸赞/寒暄等轻量对话（无需调用LLM）")

    async def execute(self, input_data: Any) -> Dict[str, Any]:
        text = str(input_data or "").strip().lower()
        if not text:
            return {"success": True, "result": "你好！有什么我可以帮你的吗？"}
        if "smart" in text or "genius" in text:
            return {"success": True, "result": "谢谢夸奖！你想让我接下来帮你做什么？"}
        return {"success": True, "result": "收到～如果你有具体任务（检索/计算/总结），直接告诉我就行。"}


TOOL = SmallTalkTool()

