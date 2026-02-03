#!/usr/bin/env python3
"""
测试对话历史元问题处理
"""

import asyncio
from src.agent.orchestrator import AgentOrchestrator

async def test_history_question():
    """测试对话历史元问题处理"""
    print("=== 测试对话历史元问题处理 ===")
    
    # 初始化编排器
    orchestrator = AgentOrchestrator()
    print("AgentOrchestrator 初始化成功")
    
    # 模拟之前的对话
    print("\n模拟之前的对话...")
    await orchestrator.process_task('现在几点了？')
    await orchestrator.process_task('获取当前系统时间')
    await orchestrator.process_task('我刚刚一共问了你几个问题，都是什么问题？')
    
    # 测试问题：都是哪些问题？
    print("\n测试问题：都是哪些问题？")
    result = await orchestrator.process_task('都是哪些问题？')
    print(f"结果: {result}")
    print(f"答案: {result.get('answer')}")
    print(f"推理: {result.get('reasoning')}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_history_question())
