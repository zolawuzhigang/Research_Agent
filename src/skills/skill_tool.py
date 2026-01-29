"""
SkillTool - bridge Claude-style SKILL.md into a callable tool using the existing LLM client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from ..tools.tool_registry import BaseTool
from .skill_model import SkillDocument, parse_skill_md


class SkillTool(BaseTool):
    """
    A thin wrapper turning a SKILL.md into a tool.

    Execution strategy:
    - Lazily load/refresh SKILL.md on each execute (cheap I/O, keeps edits up to date).
    - Build a system prompt from Instructions / Guidelines.
    - Optionally append Examples as few-shot in the prompt.
    - Ask the core LLM to answer the user input under these constraints.
    """

    def __init__(self, document: SkillDocument, llm_client: Any):
        super().__init__(name=document.meta.name, description=document.meta.description)
        self._doc = document
        self._path = document.path
        self._llm = llm_client

    async def execute(self, input_data: Any) -> Dict[str, Any]:
        # Refresh SKILL.md in case it changed on disk
        try:
            doc = parse_skill_md(self._path) or self._doc
        except Exception as e:
            logger.warning(f"SkillTool[{self.name}] reload failed, using cached doc: {e}")
            doc = self._doc

        system_parts = []
        if doc.instructions:
            system_parts.append(doc.instructions)
        if doc.guidelines:
            system_parts.append("\n## Guidelines\n" + doc.guidelines)

        system_prompt = (
            "You are a specialized assistant executing a skill.\n"
            "Follow the skill instructions and guidelines carefully.\n\n"
        ) + "\n\n".join(system_parts)

        user_prompt = str(input_data) if input_data is not None else ""

        if not self._llm:
            logger.error(f"SkillTool[{self.name}] called but LLM client is not available")
            return {"success": False, "error": "llm_not_available"}

        try:
            # Prefer async generate if available
            if hasattr(self._llm, "generate_async"):
                content = await self._llm.generate_async(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )
            else:
                # Fallback to sync generate in a thread if needed; here we call directly for simplicity
                content = self._llm.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )
        except Exception as e:
            logger.exception(f"SkillTool[{self.name}] LLM call failed: {e}")
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "result": content,
            "skill_name": self.name,
        }

