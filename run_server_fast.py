"""
启动HTTP服务 - 快速启动版本（延迟初始化）
"""

from src.utils.python_version import check_python_version
check_python_version()

import uvicorn
from loguru import logger

if __name__ == "__main__":
    logger.info("启动Research Agent HTTP服务（快速启动模式）...")
    logger.info("注意：Agent将在第一次请求时初始化，避免启动时卡住")
    uvicorn.run(
        "src.api.http_server_fast:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )
