"""
Lightweight regression-style smoke tests for skills & MCP integration.

Run:
  python -m scripts.skill_mcp_smoke_test
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def main() -> None:
    from src.agent.orchestrator import AgentOrchestrator

    logger.info("Starting skill/MCP smoke tests...")
    orchestrator = AgentOrchestrator()

    # Basic chat
    res_chat = await orchestrator.process_task("随便跟我聊两句，夸夸我。", {})
    logger.info(f"Chat result: success={res_chat.get('success')}, answer_preview={str(res_chat.get('answer'))[:80]}")

    # Time & memory regression (reuse existing behavior)
    _ = await orchestrator.process_task("现在几点了？", {})
    res_hist = await orchestrator.process_task("我刚刚问了你什么问题？", {})
    logger.info(f"History result: {res_hist.get('answer')}")

    # Skill presence (if any SKILL.md under src/skills)
    from src.skills.loader import load_skills_from_skillmd

    skills_dir = PROJECT_ROOT / "src" / "skills"
    docs = load_skills_from_skillmd(skills_dir)
    if docs:
        logger.info(f"Detected {len(docs)} SKILL.md skills: {[d.meta.name for d in docs]}")
        # Ask the first skill explicitly if possible
        first = docs[0].meta.name
        res_skill = await orchestrator.process_task(f"请使用工具 {first} 帮我完成一个简单示例。", {})
        logger.info(f"Skill[{first}] result: success={res_skill.get('success')}, answer_preview={str(res_skill.get('answer'))[:80]}")
    else:
        logger.info("No SKILL.md skills detected under src/skills, skip skill invocation test.")

    logger.info("Skill/MCP smoke tests finished.")


if __name__ == "__main__":
    asyncio.run(main())

