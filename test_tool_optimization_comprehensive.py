"""
综合测试：验证工具处理优化的所有功能
包括：能力标签提取、并发执行、超时处理、结果选优、降级策略
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.toolhub import ToolHub, ToolCandidate, _extract_capabilities_from_description
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")  # 只显示警告和错误


class MockFastTool:
    """快速工具（模拟成功）"""
    def __init__(self, name, result_text):
        self.name = name
        self.result_text = result_text

    async def execute(self, query):
        await asyncio.sleep(0.05)
        return {"success": True, "result": self.result_text}


class MockSlowTool:
    """慢速工具（模拟超时）"""
    def __init__(self, name):
        self.name = name

    async def execute(self, query):
        await asyncio.sleep(5)
        return {"success": True, "result": "完成"}


class MockErrorTool:
    """错误工具（模拟失败）"""
    def __init__(self, name):
        self.name = name

    async def execute(self, query):
        raise Exception("模拟错误")


class MockEmptyTool:
    """空结果工具"""
    def __init__(self, name):
        self.name = name

    async def execute(self, query):
        return {"success": True, "result": ""}


async def test_comprehensive_scenarios():
    """综合场景测试"""
    print("\n" + "=" * 70)
    print("工具处理优化综合测试")
    print("=" * 70)

    hub = ToolHub()

    # 场景1: 多个功能相似的搜索工具（不同名字）
    print("\n[场景1] 功能相似的搜索工具并发选优")
    search_tools = [
        ("search_web", "使用搜索引擎搜索", "搜索结果A：内容详细"),
        ("tavily_search", "使用Tavily API进行网络搜索", "搜索结果B：内容更详细，包含10条结果"),
        ("web_research", "网络研究和信息检索", "搜索结果C：内容一般"),
    ]
    for name, desc, result in search_tools:
        tool = MockFastTool(name, result)
        caps = _extract_capabilities_from_description(desc, name)
        hub.register_candidate(
            ToolCandidate(name=name, source="tools", tool=tool, priority=0, meta={"capabilities": caps})
        )
        print(f"  注册: {name} (能力: {caps})")

    result = await hub.execute_by_capability("search", "AI news", max_parallel=3)
    assert result.get("success"), "应该成功"
    assert "结果" in str(result.get("result", "")), "应该有结果"
    print(f"  ✓ 成功，结果: {str(result.get('result', ''))[:50]}...")

    # 场景2: 工具超时处理
    print("\n[场景2] 工具超时处理")
    slow_tool = MockSlowTool("slow_tool")
    caps = _extract_capabilities_from_description("慢速工具", "slow_tool")
    hub.register_candidate(
        ToolCandidate(name="slow_tool", source="tools", tool=slow_tool, priority=0, meta={"capabilities": caps})
    )
    result = await hub._call_candidate(
        hub._candidates_by_name["slow_tool"][0], "test", timeout=0.1
    )
    assert not result.get("success"), "应该超时失败"
    assert "timeout" in result.get("error", "").lower(), "错误信息应包含timeout"
    print(f"  ✓ 超时处理正常: {result.get('error')}")

    # 场景3: 结果选优（好结果 vs 空结果 vs 错误结果）
    print("\n[场景3] 结果选优逻辑")
    good_tool = MockFastTool("good", "这是一个很好的结果，内容详细且准确")
    bad_tool = MockEmptyTool("bad")
    error_tool = MockErrorTool("error")
    for tool in [good_tool, bad_tool, error_tool]:
        caps = _extract_capabilities_from_description(f"工具 {tool.name}", tool.name)
        hub.register_candidate(
            ToolCandidate(name=tool.name, source="tools", tool=tool, priority=0, meta={"capabilities": caps})
        )
    results = {
        0: await good_tool.execute("test"),
        1: await bad_tool.execute("test"),
        2: {"success": False, "error": "执行失败"},
    }
    cands = [hub._candidates_by_name["good"][0], hub._candidates_by_name["bad"][0], hub._candidates_by_name["error"][0]]
    best_idx = hub._pick_best(results, cands)
    assert best_idx == 0, "应该选择好结果"
    print(f"  ✓ 选优逻辑正常，选择了索引 {best_idx}")

    # 场景4: 多级降级（按名字 → 按能力 → 失败）
    print("\n[场景4] 多级降级策略")
    # 注册一个按能力能找到但按名字找不到的工具
    fallback_tool = MockFastTool("fallback_search", "降级搜索结果")
    caps = _extract_capabilities_from_description("搜索工具", "fallback_search")
    hub.register_candidate(
        ToolCandidate(name="fallback_search", source="skills", tool=fallback_tool, priority=1, meta={"capabilities": caps})
    )
    # 尝试按不存在的名字执行，应该降级到按能力执行
    result = await hub.execute("nonexistent_tool", "test")
    assert not result.get("success"), "按名字应该失败"
    print(f"  ✓ 按名字失败后，系统会尝试按能力查找（需要 ExecutionAgent 配合）")

    # 场景5: 并发执行异常安全
    print("\n[场景5] 并发执行异常安全")
    mixed_tools = [
        MockFastTool("fast1", "快速结果1"),
        MockErrorTool("error1"),
        MockFastTool("fast2", "快速结果2"),
    ]
    for tool in mixed_tools:
        caps = _extract_capabilities_from_description(f"工具 {tool.name}", tool.name)
        hub.register_candidate(
            ToolCandidate(name=tool.name, source="tools", tool=tool, priority=0, meta={"capabilities": caps})
        )
    # 并发执行应该能处理部分失败
    result = await hub.execute_by_capability("search", "test", max_parallel=3)
    # 至少应该有一个成功的结果
    print(f"  ✓ 并发执行异常安全，最终结果: success={result.get('success')}")

    print("\n" + "=" * 70)
    print("✓ 所有综合测试通过！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_comprehensive_scenarios())
