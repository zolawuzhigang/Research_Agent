"""
启动HTTP服务
"""

from src.utils.python_version import check_python_version
check_python_version()

import sys
import uvicorn
from loguru import logger

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("启动Research Agent HTTP服务...")
    logger.info("=" * 60)
    logger.info("提示：如果启动卡住，请使用 run_server_fast.py（延迟初始化）")
    logger.info("=" * 60)
    
    try:
        uvicorn.run(
            "src.api.http_server:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=True  # 开发模式，自动重载
        )
    except KeyboardInterrupt:
        logger.info("服务已停止")
        sys.exit(0)
    except Exception as e:
        logger.error(f"启动失败: {e}")
        logger.info("建议：使用 python run_server_fast.py 启动（延迟初始化）")
        sys.exit(1)
