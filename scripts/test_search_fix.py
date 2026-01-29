"""
搜索修复功能测试：
1. SearchTool 无 SERPAPI_KEY 时返回失败，不返回模拟结果
2. AdvancedWebSearchTool 已注册且可调用
3. Agent 处理搜索类问题时答案不含「模拟搜索结果」
"""

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


async def test_search_tool_no_mock():
    """无 key 时 SearchTool 应返回 success=False，不返回模拟文案"""
    from src.tools.search_tool import SearchTool

    # 确保没有 key
    key_bak = os.environ.pop("SERPAPI_KEY", None)
    try:
        tool = SearchTool()
        out = await tool.execute("test query")
        assert out.get("success") is False, "应返回 success=False"
        assert "SERPAPI" in str(out.get("error", "")), "应提示 SERPAPI 未配置"
        snippet = str(out.get("results", []))
        assert "模拟" not in snippet and "mock" not in snippet.lower(), "不得返回模拟结果"
        print("[PASS] SearchTool 无 key 时返回失败、无模拟结果")
    finally:
        if key_bak is not None:
            os.environ["SERPAPI_KEY"] = key_bak


async def test_advanced_search_registered_and_callable():
    """AdvancedWebSearchTool 已注册，且 execute 可被调用（不要求真实网络）"""
    from src.agent.orchestrator import AgentOrchestrator

    agent = AgentOrchestrator(use_multi_agent=True)
    hub = agent.tool_hub
    assert hub is not None
    names = [t["name"] for t in hub.list_tools()]
    assert "advanced_web_search" in names, "ToolHub 应包含 advanced_web_search"
    print("[PASS] advanced_web_search 已注册")

    from src.tools.advanced_web_search_tool import AdvancedWebSearchTool
    adv = AdvancedWebSearchTool()
    # 仅检查调用不抛错；无依赖时可能返回 all_engines_failed
    out = await adv.execute({"query": "Python programming", "num_results": 1})
    assert isinstance(out, dict)
    assert "success" in out and "results" in out
    print("[PASS] AdvancedWebSearchTool.execute 可调用，返回结构正确")


async def test_agent_search_answer_no_mock():
    """Agent 处理一道需搜索的题时，答案中不得出现模拟搜索文案"""
    from src.agent.orchestrator import AgentOrchestrator

    agent = AgentOrchestrator(use_multi_agent=True)
    # 用一道明显需要搜索的英文题
    result = await agent.process_task("What is the capital of France? One word.")
    answer = (result.get("answer") or "").strip()
    success = result.get("success", False)

    mock_phrase = "这是关于"
    if mock_phrase in answer and "的模拟搜索结果" in answer:
        print("[FAIL] 答案中仍包含模拟搜索结果文案")
        return False
    if "你好，我是为科研辅助" in answer and "capital" in "What is the capital of France?".lower():
        print("[WARN] 答案为自我介绍，可能搜索未生效或走了快速路径，需检查配置/依赖")
    else:
        print("[PASS] 答案中未出现模拟搜索文案")
    return True


async def main():
    print("=== 搜索修复功能测试 ===\n")
    await test_search_tool_no_mock()
    await test_advanced_search_registered_and_callable()
    await test_agent_search_answer_no_mock()
    print("\n=== 测试结束 ===")


if __name__ == "__main__":
    asyncio.run(main())
