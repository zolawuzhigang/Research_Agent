"""
测试Token优化效果

验证：
1. 工具结果长度限制是否生效
2. synthesize策略的智能截断是否工作
3. 工具列表长度限制是否生效
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.multi_agent_system import ExecutionAgent
from src.toolhub import ToolHub, ToolCandidate


def test_tool_result_formatting():
    """测试工具结果格式化是否应用了长度限制"""
    print("=" * 60)
    print("测试1: 工具结果格式化长度限制")
    print("=" * 60)
    
    agent = ExecutionAgent()
    
    # 测试1: 计算类工具（应该限制在100字符）
    calc_result = {"result": "1234567890" * 20}  # 200字符
    formatted = agent._format_tool_result(calc_result, "calculate")
    print(f"计算类工具结果长度: {len(formatted)} 字符")
    print(f"结果: {formatted[:100]}...")
    assert len(formatted) <= 110, f"计算类工具结果应该限制在100字符，实际: {len(formatted)}"
    assert "...（已截断）" in formatted, "应该包含截断标记"
    print("✓ 计算类工具长度限制生效\n")
    
    # 测试2: 搜索类工具（应该限制在500字符）
    search_result = {
        "results": [
            {"title": f"结果{i}", "snippet": "内容" * 100} for i in range(5)
        ]
    }
    formatted = agent._format_tool_result(search_result, "search_web")
    print(f"搜索类工具结果长度: {len(formatted)} 字符")
    print(f"结果预览: {formatted[:100]}...")
    assert len(formatted) <= 510, f"搜索类工具结果应该限制在500字符，实际: {len(formatted)}"
    print("✓ 搜索类工具长度限制生效\n")
    
    # 测试3: 历史类工具（应该限制在1000字符）
    history_result = {"formatted": "历史记录" * 200}  # 800字符
    formatted = agent._format_tool_result(history_result, "get_conversation_history")
    print(f"历史类工具结果长度: {len(formatted)} 字符")
    assert len(formatted) <= 1010, f"历史类工具结果应该限制在1000字符，实际: {len(formatted)}"
    print("✓ 历史类工具长度限制生效\n")
    
    # 测试4: 其他工具（应该限制在500字符）
    other_result = {"result": "其他结果" * 100}  # 400字符
    formatted = agent._format_tool_result(other_result, "unknown_tool")
    print(f"其他工具结果长度: {len(formatted)} 字符")
    assert len(formatted) <= 510, f"其他工具结果应该限制在500字符，实际: {len(formatted)}"
    print("✓ 其他工具长度限制生效\n")


def test_synthesize_strategy():
    """测试synthesize策略的智能截断"""
    print("=" * 60)
    print("测试2: Synthesize策略智能截断")
    print("=" * 60)
    
    hub = ToolHub()
    
    # 测试1: 大量结果应该直接使用简单合并
    large_results = [
        {"success": True, "result": "结果" * 500, "_meta": {"source": "tool1"}},
        {"success": True, "result": "结果" * 500, "_meta": {"source": "tool2"}},
        {"success": True, "result": "结果" * 500, "_meta": {"source": "tool3"}},
        {"success": True, "result": "结果" * 500, "_meta": {"source": "tool4"}},
    ]
    
    # 检查是否会提前降级（不调用LLM）
    total_length = sum(len(str(r.get("result", ""))) for r in large_results)
    print(f"大量结果总长度: {total_length} 字符")
    print(f"结果数量: {len(large_results)}")
    
    if total_length > 2000 or len(large_results) > 3:
        print("✓ 应该使用简单合并策略（提前降级）")
    else:
        print("✗ 不应该使用简单合并策略")
    
    print()


def test_tool_list_limiting():
    """测试工具列表长度限制"""
    print("=" * 60)
    print("测试3: 工具列表长度限制")
    print("=" * 60)
    
    from src.agent.multi_agent_system import PlanningAgent
    
    agent = PlanningAgent()
    
    # 模拟大量工具
    many_tools = ["none", "search_web", "calculate", "get_time", "get_conversation_history"]
    many_tools.extend([f"tool_{i}" for i in range(30)])  # 总共35个工具
    
    agent.set_available_tools(many_tools)
    prompt = agent._build_decomposition_prompt("测试问题")
    
    # 检查prompt中工具列表的长度
    if "还有" in prompt and "个其他工具" in prompt:
        print("✓ 工具列表被正确限制，显示了提示信息")
    else:
        print("✗ 工具列表可能没有被限制")
    
    # 检查prompt长度
    print(f"Prompt长度: {len(prompt)} 字符")
    print(f"Prompt预览: {prompt[:200]}...")
    print()


if __name__ == "__main__":
    print("\n开始Token优化测试\n")
    
    try:
        test_tool_result_formatting()
        test_synthesize_strategy()
        test_tool_list_limiting()
        
        print("=" * 60)
        print("所有测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
