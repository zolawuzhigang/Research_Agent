#!/usr/bin/env python3
"""
测试时间工具功能
"""

import asyncio
from src.agent.orchestrator import AgentOrchestrator

async def test_time_query():
    """测试时间查询功能"""
    print("=== 测试时间工具 ===")
    
    # 初始化编排器
    orchestrator = AgentOrchestrator()
    print("AgentOrchestrator 初始化成功")
    
    # 测试任务1: 现在几点了？
    print("\n测试任务1: 现在几点了？")
    result1 = await orchestrator.process_task('现在几点了？')
    print(f"结果1: {result1}")
    
    # 测试任务2: 获取当前系统时间
    print("\n测试任务2: 获取当前系统时间")
    result2 = await orchestrator.process_task('获取当前系统时间')
    print(f"结果2: {result2}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_time_query())
