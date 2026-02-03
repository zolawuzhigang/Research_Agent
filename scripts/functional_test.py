"""
功能测试脚本（不依赖 pytest）：归一化、工具、WebSearchCrawlTool、Agent 流程。
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def test_normalize():
    """测试答案归一化"""
    from src.utils.normalize import normalize_answer
    assert normalize_answer("Answer: 巴黎") == "巴黎"
    assert normalize_answer("  140  ") == "140"
    assert normalize_answer("") == ""
    assert normalize_answer(None) == ""
    print("  [OK] normalize")


def test_calculator_tool():
    """测试计算工具"""
    async def _run():
        from src.tools import CalculatorTool
        tool = CalculatorTool()
        r = await tool.execute("2 + 3 * 4")
        assert r["success"] is True and r["result"] == 14.0
        r = await tool.execute("abc")
        assert r["success"] is False
    asyncio.run(_run())
    print("  [OK] CalculatorTool")


def test_web_search_crawl_tool():
    """测试 WebSearchCrawlTool：空 query、结构、max_depth=1 执行"""
    async def _run():
        from src.tools import WebSearchCrawlTool
        tool = WebSearchCrawlTool()
        # 空 query
        r = await tool.execute("")
        assert r["success"] is False and "query" in r and r.get("count", 0) == 0
        # dict 输入
        r = await tool.execute({"query": "test", "max_depth": 1})
        assert "success" in r and "results" in r and "count" in r
        assert isinstance(r["results"], list)
        if r["success"]:
            assert "query" in r and (r.get("direct_answer") is None or isinstance(r["direct_answer"], str))
        print("  [OK] WebSearchCrawlTool (structure + empty query)")
    asyncio.run(_run())


def test_orchestrator_and_tools_registered():
    """测试编排器初始化及 web_search_crawl 已注册"""
    from src.agent import AgentOrchestrator
    orch = AgentOrchestrator(use_multi_agent=True)
    names = list(orch.tool_registry.tools.keys())
    assert "web_search_crawl" in names, f"web_search_crawl not in {names}"
    print("  [OK] Orchestrator + web_search_crawl registered")


def test_process_task_once():
    """测试 process_task 单次执行（需网络，LLM）"""
    async def _run():
        from src.agent import AgentOrchestrator
        orch = AgentOrchestrator(use_multi_agent=True)
        result = await orch.process_task("1+1等于几")
        assert "success" in result and "answer" in result or "error" in result
        print("  [OK] process_task returned")
    asyncio.run(_run())


def main():
    print("=== 功能测试 ===\n")
    failed = []
    tests = [
        ("normalize", test_normalize),
        ("CalculatorTool", test_calculator_tool),
        ("WebSearchCrawlTool", test_web_search_crawl_tool),
        ("Orchestrator + tools", test_orchestrator_and_tools_registered),
        ("process_task", test_process_task_once),
    ]
    for name, fn in tests:
        try:
            print(f"[{name}]")
            fn()
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed.append((name, e))
    print()
    if failed:
        print(f"失败: {len(failed)}/{len(tests)}")
        for name, e in failed:
            print(f"  - {name}: {e}")
        sys.exit(1)
    print("全部通过.")
    sys.exit(0)


if __name__ == "__main__":
    main()
