#!/usr/bin/env python3
"""
测试工具调用功能
"""

import asyncio
from src.agent.orchestrator import AgentOrchestrator

async def test_tool_call():
    """测试工具调用"""
    print("初始化Agent编排器...")
    orchestrator = AgentOrchestrator(use_multi_agent=True)
    
    print("\n注册的工具:")
    for tool_name, tool in orchestrator.tool_registry.tools.items():
        print(f"- {tool_name}: {tool.description}")
    
    print("\n测试时间工具...")
    # 测试时间工具
    try:
        time_tool = orchestrator.tool_registry.get_tool("get_time")
        result = await time_tool.execute({})
        print(f"时间工具结果: {result}")
    except Exception as e:
        print(f"时间工具测试失败: {e}")
    
    print("\n测试计算器工具...")
    # 测试计算器工具
    try:
        calc_tool = orchestrator.tool_registry.get_tool("calculate")
        result = await calc_tool.execute({"expression": "1 + 1"})
        print(f"计算器工具结果: {result}")
    except Exception as e:
        print(f"计算器工具测试失败: {e}")
    
    print("\n测试搜索工具...")
    # 测试搜索工具
    try:
        search_tool = orchestrator.tool_registry.get_tool("search_web")
        result = await search_tool.execute({"query": "阿里巴巴"})
        print(f"搜索工具结果: {result}")
    except Exception as e:
        print(f"搜索工具测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool_call())
