"""
Smoke tests for common business/competition scenarios.

Run:
  python3.13 scripts/smoke_test.py  或  py -3.13 scripts/smoke_test.py
"""

import sys
from pathlib import Path

# Ensure project root on sys.path before importing src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.python_version import check_python_version
check_python_version()

import asyncio


async def main() -> None:
    from src.agent.langgraph_workflow import LANGGRAPH_AVAILABLE
    from src.agent.orchestrator import AgentOrchestrator

    # 工作流路径：优先 LangGraph 图，不可用时用简化工作流
    if LANGGRAPH_AVAILABLE:
        print("Workflow: LangGraph graph (primary)")
    else:
        print("Workflow: simplified workflow (fallback)")
    print()

    agent = AgentOrchestrator(use_multi_agent=True)

    tests = [
        ("Time question (should use tool)", "now time?"),
        ("Memory question (should reference previous)", "what did I ask just now?"),
        ("Chit-chat/compliment", "you are smart"),
        ("Repeat same question (cache candidate)", "you are smart"),
        ("Capability question (should use fast path & self-description)", "你都能干什么？"),
    ]

    for name, q in tests:
        try:
            result = await agent.process_task(q)
            answer = result.get("answer")
            success = result.get("success", False)
            print(f"\n[{name}]\nQ: {q}\nsuccess={success}\nA: {answer}\n")
        except Exception as e:
            print(f"\n[{name}] FAILED: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())

