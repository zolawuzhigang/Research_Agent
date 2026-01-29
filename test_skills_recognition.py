"""
Quick manual test for SKILL.md skills integration.

Run:
  python test_skills_recognition.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def main() -> None:
    from src.agent.orchestrator import AgentOrchestrator

    logger.info("Initializing AgentOrchestrator for skills test...")
    orchestrator = AgentOrchestrator(use_multi_agent=True)

    # 1) List tools seen by ToolHub
    hub = getattr(orchestrator, "tool_hub", None)
    if hub is None:
        print("ToolHub is not initialized.")
    else:
        print("\n=== ToolHub tools ===")
        for item in hub.list_tools():
            name = item.get("name")
            cands = item.get("candidates") or []
            sources = {c.get("source") for c in cands}
            print(f"- {name} (sources: {', '.join(sorted(sources))})")

    # 2) Try a few representative SKILL-based tools by name, if present
    candidate_skill_names = [
        "pdf",
        "docx",
        "pptx",
        "webapp-testing",
        "theme-factory",
        "algorithmic-art",
        "smalltalk",  # from python smalltalk_skill.py if exposed
    ]

    print("\n=== Skill invocation tests ===")
    for name in candidate_skill_names:
        if hub is None or not hub.has_tool(name):
            continue
        q = f"请使用工具 {name}，给我一个简单示例，说明你能帮我做什么，并给出一个具体的使用场景。"
        print(f"\n[Skill: {name}]\nQ: {q}")
        try:
            result = await orchestrator.process_task(q, context={"test": "skills"})
            print("success:", result.get("success"))
            print("answer preview:", str(result.get("answer"))[:200])
            if result.get("errors"):
                print("errors:", result.get("errors"))
        except Exception as e:
            print(f"ERROR when invoking skill {name}: {e}")


if __name__ == "__main__":
    asyncio.run(main())

