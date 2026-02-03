#!/usr/bin/env python3
"""
测试多跳推理的终止条件
"""

from src.agent.orchestrator import AgentOrchestrator

async def test_hop_termination():
    """测试多跳推理的终止条件"""
    print("测试多跳推理的终止条件...")
    
    try:
        # 初始化Agent编排器
        orchestrator = AgentOrchestrator()
        print("AgentOrchestrator初始化成功")
        
        # 测试获取当前时间的任务
        test_task = "获取当前系统时间"
        print(f"\n测试任务: {test_task}")
        
        # 执行任务
        result = await orchestrator.process_task(test_task)
        print("\n任务执行结果:")
        print(result)
        
        print("\n测试完成！")
        return True
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_hop_termination())
