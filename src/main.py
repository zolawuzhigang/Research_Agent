"""
主入口文件
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent import AgentOrchestrator
from loguru import logger


async def main():
    """
    主函数
    """
    logger.info("Starting Agent...")
    
    # 初始化Agent
    agent = AgentOrchestrator()
    
    # 示例任务
    task = "请分析并处理给定的任务"
    
    # 处理任务
    result = await agent.process_task(task)
    
    # 输出结果
    logger.info(f"Result: {result}")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
