"""
日志系统 - 统一日志配置和管理
"""

import os
from loguru import logger
from pathlib import Path
from typing import Optional


def init_logger(log_config: Optional[dict] = None):
    """
    初始化日志系统
    
    Args:
        log_config: 日志配置字典，包含level、file、rotation、retention等配置
    """
    # 默认配置
    default_config = {
        "level": "INFO",
        "file": "logs/agent.log",
        "rotation": "10 MB",
        "retention": "7 days"
    }
    
    # 合并配置
    config = {**default_config, **(log_config or {})}
    
    # 确保日志目录存在
    log_file = Path(config["file"])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 清除默认处理器
    logger.remove()
    
    # 添加文件处理器
    logger.add(
        config["file"],
        level=config["level"],
        rotation=config["rotation"],
        retention=config["retention"],
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )
    
    # 添加控制台处理器
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=config["level"],
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )
    
    logger.info(f"日志系统初始化完成: 级别={config['level']}, 文件={config['file']}")


def get_logger(name: Optional[str] = None):
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        loguru.Logger 实例
    """
    return logger.bind(name=name)


# 全局日志记录器
LOGGER = get_logger()
