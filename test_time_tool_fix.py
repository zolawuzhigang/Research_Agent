#!/usr/bin/env python3
"""
测试时间工具的修复
"""

from src.agent.orchestrator import AgentOrchestrator

async def test_time_tool_fix():
    """测试时间工具的修复"""
    print("测试时间工具的修复...")
    
    try:
        # 初始化Agent编排器
        orchestrator = AgentOrchestrator()
        print("AgentOrchestrator初始化成功")
        
        # 测试获取当前时间的任务
        test_task = "现在几点了？"
        print(f"\n测试任务: {test_task}")
        
        # 执行任务
        result = await orchestrator.process_task(test_task)
        print("\n任务执行结果:")
        print(f"成功: {result.get('success')}")
        print(f"答案: {result.get('answer')}")
        print(f"推理过程: {result.get('reasoning')}")
        print(f"错误: {result.get('error')}")
        
        # 测试另一个时间相关的任务
        test_task2 = "获取当前系统时间"
        print(f"\n测试任务2: {test_task2}")
        
        # 执行任务
        result2 = await orchestrator.process_task(test_task2)
        print("\n任务执行结果2:")
        print(f"成功: {result2.get('success')}")
        print(f"答案: {result2.get('answer')}")
        print(f"推理过程: {result2.get('reasoning')}")
        print(f"错误: {result2.get('error')}")
        
        print("\n测试完成！")
        return True
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_time_tool_fix())
