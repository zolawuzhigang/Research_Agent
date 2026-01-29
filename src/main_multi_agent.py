"""
多Agent系统主入口
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
    主函数 - 演示多Agent系统
    """
    logger.info("Starting Multi-Agent System...")
    
    # 初始化Agent（使用多Agent模式）
    agent = AgentOrchestrator(use_multi_agent=True)
    
    # 示例问题
    questions = [
        "法国首都在哪里？",
        "请分析最近三年人工智能在医疗影像诊断方面的研究进展",
        "计算 2 + 3 * 4 的结果"
    ]
    
    for question in questions:
        logger.info(f"\n{'='*50}")
        logger.info(f"问题: {question}")
        logger.info(f"{'='*50}")
        
        # 处理问题
        result = await agent.process_task(question)
        
        # 输出结果
        if result.get("success"):
            logger.info(f"答案: {result.get('answer')}")
            logger.info(f"置信度: {result.get('confidence', 0.0):.2f}")
            if result.get("reasoning"):
                logger.info(f"推理过程:\n{result.get('reasoning')}")
        else:
            logger.error(f"处理失败: {result.get('error')}")
        
        # 显示对话历史
        history = agent.get_conversation_history(3)
        logger.info(f"对话历史: {len(history)} 条消息")
    
    logger.info("\nMulti-Agent System demo completed!")


if __name__ == "__main__":
    asyncio.run(main())
