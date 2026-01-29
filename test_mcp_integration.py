"""
MCP integration detection test.

Checks that:
- mcps.enabled is true
- config_file is readable
- load_mcp_tools() creates tools from that config
- ToolHub registers those tools and can execute them

Run:
  python test_mcp_integration.py
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

    logger.info("Initializing AgentOrchestrator for MCP integration test...")
    orchestrator = AgentOrchestrator(use_multi_agent=True)

    hub = getattr(orchestrator, "tool_hub", None)
    if hub is None:
        print("ToolHub is not initialized.")
        return

    # List MCP tools
    print("\n=== MCP tools in ToolHub ===")
    mcp_tool_names = []
    for item in hub.list_tools():
        name = item.get("name")
        cands = item.get("candidates") or []
        sources = {c.get("source") for c in cands}
        if "mcps" in sources:
            mcp_tool_names.append(name)
            print(f"- {name} (sources: {', '.join(sorted(sources))})")

    if not mcp_tool_names:
        print("No MCP tools detected. Check mcps.enabled and mcps.config_file in config.")
        return

    # Try invoking each MCP tool once
    print("\n=== MCP tool invocation tests ===")
    for name in mcp_tool_names:
        q = f"测试调用 MCP 工具 {name}，请回显配置和输入。"
        print(f"\n[Tool: {name}]\nQ: {q}")
        try:
            result = await orchestrator.process_task(q, context={"test": "mcp"})
            print("success:", result.get("success"))
            print("answer preview:", str(result.get("answer"))[:200])
            if result.get("errors"):
                print("errors:", result.get("errors"))
        except Exception as e:
            print(f"ERROR when invoking MCP tool {name}: {e}")


if __name__ == "__main__":
    asyncio.run(main())

