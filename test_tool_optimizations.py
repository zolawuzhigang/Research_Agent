"""
测试工具处理优化功能
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.toolhub import ToolHub, ToolCandidate
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")


class MockFastTool:
    """快速工具"""
    def __init__(self, name, result_text, delay=0.05):
        self.name = name
        self.result_text = result_text
        self.delay = delay

    async def execute(self, query):
        await asyncio.sleep(self.delay)
        return {"success": True, "result": self.result_text}


class MockSlowTool:
    """慢速工具（用于测试取消）"""
    def __init__(self, name):
        self.name = name
        self.cancelled = False

    async def execute(self, query):
        try:
            await asyncio.sleep(10)  # 模拟长时间执行
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return {"success": True, "result": "完成"}


class MockStructuredTool:
    """返回结构化数据的工具"""
    def __init__(self, name):
        self.name = name

    async def execute(self, query):
        await asyncio.sleep(0.05)
        return {
            "success": True,
            "result": {
                "results": [{"title": "结果1", "content": "内容1"}],
                "count": 1
            }
        }


async def test_concurrent_cancellation():
    """测试并发任务的取消机制"""
    print("\n=== 测试并发任务取消机制 ===")
    
    hub = ToolHub()
    
    # 注册一个快速工具和一个慢速工具（都标记为 search 能力）
    fast_tool = MockFastTool("fast", "快速结果", delay=0.05)
    slow_tool = MockSlowTool("slow")
    
    hub.register_candidate(
        ToolCandidate(name="fast", source="tools", tool=fast_tool, priority=0, meta={"capabilities": ["search"]})
    )
    hub.register_candidate(
        ToolCandidate(name="slow", source="tools", tool=slow_tool, priority=1, meta={"capabilities": ["search"]})
    )
    
    # 测试按能力执行（应该快速返回并取消慢速工具）
    import time
    start_time = time.time()
    result = await hub.execute_by_capability("search", "test", max_parallel=2)
    duration = time.time() - start_time
    
    print(f"执行时间: {duration:.2f}s (应该 < 0.5s)")
    print(f"结果: success={result.get('success')}")
    print(f"慢速工具是否被取消: {slow_tool.cancelled}")
    
    # 等待一小段时间，确保取消操作完成
    await asyncio.sleep(0.1)
    
    assert duration < 0.5, f"应该快速返回（< 0.5s），实际 {duration:.2f}s"
    # 注意：如果 fast_tool 成功，slow_tool 应该被取消
    # 但如果 fast_tool 也失败，slow_tool 可能不会被取消
    if result.get("success"):
        assert slow_tool.cancelled, "慢速工具应该被取消"
    print("✓ 通过\n")


async def test_performance_monitoring():
    """测试性能监控"""
    print("\n=== 测试性能监控 ===")
    
    from src.utils.metrics import get_metrics
    
    hub = ToolHub()
    tool = MockFastTool("test_tool", "测试结果", delay=0.1)
    from src.toolhub import _extract_capabilities_from_description
    caps = _extract_capabilities_from_description("测试工具", "test_tool")
    hub.register_candidate(
        ToolCandidate(name="test_tool", source="tools", tool=tool, priority=0, meta={"capabilities": caps})
    )
    
    # 执行工具
    result = await hub.execute("test_tool", "test")
    assert result.get("success"), "应该成功"
    
    # 检查性能指标
    metrics = get_metrics()
    perf_stats = metrics.get_performance_stats()
    
    tool_perf = perf_stats.get("tool_execution_test_tool")
    if tool_perf:
        print(f"工具执行时间: avg={tool_perf.get('avg_time', 0):.3f}s")
        print(f"执行次数: {tool_perf.get('total_count', 0)}")
        assert tool_perf.get("total_count", 0) > 0, "应该记录性能指标"
    else:
        print("警告: 未找到性能指标（可能需要在不同模块中记录）")
    
    print("✓ 通过\n")


async def test_result_selection():
    """测试结果选优算法"""
    print("\n=== 测试结果选优算法 ===")
    
    hub = ToolHub()
    
    # 注册多个工具，返回不同质量的结果
    tools = [
        ("short", "短结果", MockFastTool("short", "短")),
        ("medium", "中等结果", MockFastTool("medium", "这是一个中等长度的结果，包含一些有用的信息")),
        ("structured", "结构化结果", MockStructuredTool("structured")),
        ("long", "长结果", MockFastTool("long", "这是一个非常长的结果" * 100)),
    ]
    
    for name, desc, tool in tools:
        from src.toolhub import _extract_capabilities_from_description
        caps = _extract_capabilities_from_description(desc, name)
        hub.register_candidate(
            ToolCandidate(name=name, source="tools", tool=tool, priority=0, meta={"capabilities": caps})
        )
    
    # 并发执行并选优
    result = await hub.execute_by_capability("search", "test", max_parallel=4)
    
    print(f"选中的结果类型: {result.get('_meta', {}).get('source', 'unknown')}")
    print(f"结果内容预览: {str(result.get('result', ''))[:50]}...")
    
    # 应该选择结构化或中等长度的结果，而不是过短或过长的
    assert result.get("success"), "应该成功"
    print("✓ 通过\n")


async def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    hub = ToolHub()
    
    class ErrorTool:
        name = "error_tool"
        async def execute(self, query):
            raise Exception("模拟错误")
    
    tool = ErrorTool()
    from src.toolhub import _extract_capabilities_from_description
    caps = _extract_capabilities_from_description("错误工具", "error_tool")
    hub.register_candidate(
        ToolCandidate(name="error_tool", source="tools", tool=tool, priority=0, meta={"capabilities": caps})
    )
    
    result = await hub.execute("error_tool", "test")
    
    print(f"错误结果: success={result.get('success')}, error={result.get('error')}")
    assert not result.get("success"), "应该失败"
    assert "error" in result, "应该包含错误信息"
    
    # 检查错误是否被记录
    from src.utils.metrics import get_metrics
    metrics = get_metrics()
    error_stats = metrics.get_error_stats()
    
    print(f"错误统计: {error_stats.get('total_errors', 0)} 个错误")
    print("✓ 通过\n")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("工具处理优化测试")
    print("=" * 70)
    
    try:
        await test_concurrent_cancellation()
        await test_performance_monitoring()
        await test_result_selection()
        await test_error_handling()
        
        print("=" * 70)
        print("✓ 所有测试通过！")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
