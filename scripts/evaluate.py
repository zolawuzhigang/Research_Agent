"""
评估脚本 - 用于测试和评估Agent性能
"""

import asyncio
import json
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent import AgentOrchestrator
from loguru import logger


async def evaluate_agent(test_cases: list):
    """
    评估Agent性能
    
    Args:
        test_cases: 测试用例列表
    """
    agent = AgentOrchestrator()
    
    results = []
    for i, test_case in enumerate(test_cases):
        logger.info(f"Running test case {i+1}/{len(test_cases)}")
        
        task = test_case.get("task", "")
        expected = test_case.get("expected", None)
        
        result = await agent.process_task(task)
        
        # 评估结果
        evaluation = {
            "test_case": i + 1,
            "task": task,
            "result": result,
            "expected": expected,
            "match": evaluate_result(result, expected)
        }
        
        results.append(evaluation)
    
    # 输出评估报告
    print_evaluation_report(results)
    
    return results


def evaluate_result(result: dict, expected: dict) -> bool:
    """
    评估结果是否符合预期
    
    TODO: 实现具体的评估逻辑
    """
    # 占位实现
    return result.get("success", False)


def print_evaluation_report(results: list):
    """
    打印评估报告
    """
    total = len(results)
    passed = sum(1 for r in results if r["match"])
    
    print("\n" + "="*50)
    print("评估报告")
    print("="*50)
    print(f"总测试数: {total}")
    print(f"通过数: {passed}")
    print(f"失败数: {total - passed}")
    print(f"通过率: {passed/total*100:.2f}%")
    print("="*50)


if __name__ == "__main__":
    # 示例测试用例
    test_cases = [
        {
            "task": "测试任务1",
            "expected": {"success": True}
        },
        {
            "task": "测试任务2",
            "expected": {"success": True}
        }
    ]
    
    asyncio.run(evaluate_agent(test_cases))
