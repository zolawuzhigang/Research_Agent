"""
测试基于功能相似的工具并发选优功能
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.toolhub import ToolHub, ToolCandidate, _extract_capabilities_from_description
from src.tools.search_tool import SearchTool
from src.tools.calculator_tool import CalculatorTool
from src.tools.time_tool import TimeTool
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")


class MockSearchTool1:
    """模拟搜索工具1"""
    name = "search_web"
    description = "使用搜索引擎搜索网络信息"

    async def execute(self, query: str):
        await asyncio.sleep(0.1)  # 模拟网络延迟
        return {
            "success": True,
            "result": f"搜索结果1: {query}",
            "count": 5
        }


class MockSearchTool2:
    """模拟搜索工具2（功能相似但名字不同）"""
    name = "tavily_search"
    description = "使用Tavily API进行网络搜索和研究"

    async def execute(self, query: str):
        await asyncio.sleep(0.15)
        return {
            "success": True,
            "result": f"搜索结果2: {query}",
            "count": 10
        }


class MockSearchTool3:
    """模拟搜索工具3（功能相似但名字不同）"""
    name = "web_research"
    description = "网络研究和信息检索工具"

    async def execute(self, query: str):
        await asyncio.sleep(0.12)
        return {
            "success": True,
            "result": f"搜索结果3: {query}",
            "count": 8
        }


async def test_capability_extraction():
    """测试能力标签提取"""
    print("\n=== 测试能力标签提取 ===")
    
    test_cases = [
        ("使用搜索引擎搜索网络信息", "search_web", ["search", "web", "research"]),
        ("执行数学计算，支持基本四则运算", "calculate", ["calculate"]),
        ("获取当前时间、时区转换", "get_time", ["time"]),
    ]
    
    for desc, name, expected_caps in test_cases:
        caps = _extract_capabilities_from_description(desc, name)
        print(f"描述: {desc}")
        print(f"名称: {name}")
        print(f"提取的能力: {caps}")
        print(f"期望包含: {expected_caps}")
        assert any(exp in caps for exp in expected_caps), f"能力提取失败: {caps}"
        print("✓ 通过\n")


async def test_capability_based_execution():
    """测试基于能力的工具执行"""
    print("\n=== 测试基于能力的工具执行 ===")
    
    hub = ToolHub()
    
    # 注册多个功能相似的搜索工具（名字不同但能力相同）
    tool1 = MockSearchTool1()
    desc1 = tool1.description
    caps1 = _extract_capabilities_from_description(desc1, tool1.name)
    hub.register_candidate(
        ToolCandidate(
            name=tool1.name,
            source="tools",
            tool=tool1,
            priority=0,
            meta={"capabilities": caps1, "description": desc1}
        )
    )
    
    tool2 = MockSearchTool2()
    desc2 = tool2.description
    caps2 = _extract_capabilities_from_description(desc2, tool2.name)
    hub.register_candidate(
        ToolCandidate(
            name=tool2.name,
            source="skills",
            tool=tool2,
            priority=1,
            meta={"capabilities": caps2, "description": desc2}
        )
    )
    
    tool3 = MockSearchTool3()
    desc3 = tool3.description
    caps3 = _extract_capabilities_from_description(desc3, tool3.name)
    hub.register_candidate(
        ToolCandidate(
            name=tool3.name,
            source="mcps",
            tool=tool3,
            priority=2,
            meta={"capabilities": caps3, "description": desc3}
        )
    )
    
    print(f"注册的工具: {[t.name for t in [tool1, tool2, tool3]]}")
    print(f"工具1能力: {caps1}")
    print(f"工具2能力: {caps2}")
    print(f"工具3能力: {caps3}")
    
    # 测试按能力查找
    search_tools = hub.find_by_capability("search")
    print(f"\n按能力'search'找到的工具: {[t.name for t in search_tools]}")
    assert len(search_tools) >= 3, f"应该找到至少3个搜索工具，实际找到{len(search_tools)}"
    
    # 测试按能力并发执行
    print("\n按能力'search'并发执行...")
    result = await hub.execute_by_capability("search", "AI news", max_parallel=3)
    print(f"执行结果: success={result.get('success')}, result={result.get('result', 'N/A')[:100]}")
    assert result.get("success"), "按能力执行应该成功"
    assert "结果" in str(result.get("result", "")), "结果应该包含搜索内容"
    print("✓ 通过\n")


async def test_tool_timeout():
    """测试工具超时处理"""
    print("\n=== 测试工具超时处理 ===")
    
    class SlowTool:
        name = "slow_tool"
        description = "慢速工具"

        async def execute(self, query: str):
            await asyncio.sleep(5)  # 模拟长时间执行
            return {"success": True, "result": "完成"}

    hub = ToolHub()
    tool = SlowTool()
    desc = tool.description
    caps = _extract_capabilities_from_description(desc, tool.name)
    hub.register_candidate(
        ToolCandidate(
            name=tool.name,
            source="tools",
            tool=tool,
            priority=0,
            meta={"capabilities": caps, "description": desc}
        )
    )
    
    # 使用短超时测试
    result = await hub._call_candidate(
        hub._candidates_by_name[tool.name][0],
        "test",
        timeout=0.5  # 0.5秒超时
    )
    print(f"超时结果: success={result.get('success')}, error={result.get('error')}")
    assert not result.get("success"), "应该超时失败"
    assert "timeout" in result.get("error", "").lower(), "错误信息应该包含timeout"
    print("✓ 通过\n")


async def test_result_validation():
    """测试结果验证和选优"""
    print("\n=== 测试结果验证和选优 ===")
    
    class GoodTool:
        name = "good_tool"
        async def execute(self, query: str):
            return {"success": True, "result": "这是一个很好的结果，内容详细且准确"}

    class BadTool:
        name = "bad_tool"
        async def execute(self, query: str):
            return {"success": True, "result": ""}  # 空结果

    class ErrorTool:
        name = "error_tool"
        async def execute(self, query: str):
            return {"success": False, "error": "执行失败"}

    hub = ToolHub()
    for tool in [GoodTool(), BadTool(), ErrorTool()]:
        desc = f"工具 {tool.name}"
        caps = _extract_capabilities_from_description(desc, tool.name)
        hub.register_candidate(
            ToolCandidate(
                name=tool.name,
                source="tools",
                tool=tool,
                priority=0,
                meta={"capabilities": caps, "description": desc}
            )
        )
    
    # 测试选优逻辑
    results = {
        0: {"success": True, "result": "好结果"},
        1: {"success": True, "result": ""},  # 空结果
        2: {"success": False, "error": "失败"},
    }
    cands = hub._candidates_by_name["good_tool"] + hub._candidates_by_name["bad_tool"] + hub._candidates_by_name["error_tool"]
    best_idx = hub._pick_best(results, cands)
    print(f"选优结果: best_idx={best_idx}")
    assert best_idx == 0, "应该选择第一个好结果"
    print("✓ 通过\n")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("基于功能相似的工具并发选优功能测试")
    print("=" * 60)
    
    try:
        await test_capability_extraction()
        await test_capability_based_execution()
        await test_tool_timeout()
        await test_result_validation()
        
        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
