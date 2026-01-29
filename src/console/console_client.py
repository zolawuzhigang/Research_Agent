"""
控制台客户端 - 交互式问答
"""

import asyncio
from typing import Optional
from loguru import logger
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agent import AgentOrchestrator


class ConsoleClient:
    """控制台交互客户端"""
    
    def __init__(self):
        logger.info("初始化Console Client...")
        self.agent = AgentOrchestrator(use_multi_agent=True)
        logger.info("Console Client初始化完成")
    
    async def run(self):
        """运行交互式控制台"""
        print("=" * 60)
        print("Research Agent - 控制台交互模式")
        print("=" * 60)
        print("输入 'quit' 或 'exit' 退出")
        print("输入 'clear' 清空对话历史")
        print("=" * 60)
        print()
        
        while True:
            try:
                # 获取用户输入
                question = input("\n你: ").strip()
                
                if not question:
                    continue
                
                # 退出命令
                if question.lower() in ['quit', 'exit', 'q']:
                    print("再见！")
                    break
                
                # 清空历史
                if question.lower() == 'clear':
                    self.agent.clear_memory()
                    print("对话历史已清空")
                    continue
                
                # 处理问题
                print("\n思考中...")
                result = await self.agent.process_task(question)
                
                # 显示结果
                if result.get("success"):
                    print(f"\nAgent: {result.get('answer', '')}")
                    
                    # 显示详细信息（可选）
                    if result.get("confidence"):
                        print(f"[置信度: {result.get('confidence', 0.0):.2f}]")
                    
                    if result.get("errors"):
                        err_list = result.get("errors", [])
                        print(f"[警告: {len(err_list)} 个错误]")
                        # 若有错误，提示可能因搜索依赖未安装；安装后可启用真实网络搜索
                        print("[提示: 若为搜索步骤失败，可运行: pip install duckduckgo-search beautifulsoup4]")
                else:
                    print(f"\n错误: {result.get('error', '处理失败')}")
            
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                logger.error(f"处理错误: {e}")
                print(f"\n错误: {str(e)}")


async def main():
    """主函数"""
    client = ConsoleClient()
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
