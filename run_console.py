"""
启动控制台交互
"""

from src.utils.python_version import check_python_version
check_python_version()

import asyncio
from src.console.console_client import ConsoleClient

if __name__ == "__main__":
    asyncio.run(ConsoleClient().run())
