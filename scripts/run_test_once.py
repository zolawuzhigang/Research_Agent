"""单次运行测试：初始化编排器并执行一个问题，用于发现启动/运行错误。"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

async def main():
    from src.agent import AgentOrchestrator
    print("初始化 AgentOrchestrator (use_multi_agent=True)...")
    orch = AgentOrchestrator(use_multi_agent=True)
    print("执行 process_task('1+1等于几')...")
    result = await orch.process_task("1+1等于几")
    print("Result:", result)
    return result

if __name__ == "__main__":
    asyncio.run(main())
