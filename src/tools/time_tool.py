"""
时间工具 - 获取当前时间、时区转换等
"""

from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from .tool_registry import BaseTool


class TimeTool(BaseTool):
    """时间工具 - 获取当前时间、时区转换等"""
    
    def __init__(self):
        super().__init__(
            name="get_time",
            description="获取当前时间、时区转换、时间计算等时间相关操作"
        )
    
    async def execute(self, query: str) -> Dict[str, Any]:
        """
        执行时间相关操作
        
        Args:
            query: 时间查询（如 "current_time", "timezone:Asia/Shanghai"）
        
        Returns:
            时间信息
        """
        logger.info(f"TimeTool: 处理时间查询 - {query}")
        
        try:
            query_lower = query.lower().strip()
            
            # 获取当前时间
            if "current" in query_lower or "现在" in query or "当前" in query:
                now = datetime.now()
                return {
                    "success": True,
                    "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": now.timestamp(),
                    "timezone": "local",
                    "formatted": f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}"
                }
            
            # UTC时间
            if "utc" in query_lower:
                now_utc = datetime.utcnow()
                return {
                    "success": True,
                    "utc_time": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "timestamp": now_utc.timestamp(),
                    "timezone": "UTC",
                    "formatted": f"UTC时间: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                }
            
            # 时区转换（简单实现）
            if "timezone" in query_lower or "时区" in query:
                # 提取时区信息
                now = datetime.now()
                # 中国时区（UTC+8）
                if "shanghai" in query_lower or "beijing" in query_lower or "北京" in query or "上海" in query:
                    return {
                        "success": True,
                        "timezone": "Asia/Shanghai",
                        "offset": "+08:00",
                        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "formatted": f"北京时间: {now.strftime('%Y年%m月%d日 %H:%M')}"
                    }
                else:
                    # 默认返回本地时间
                    return {
                        "success": True,
                        "timezone": "local",
                        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "formatted": f"当前时间: {now.strftime('%Y年%m月%d日 %H:%M')}"
                    }
            
            # 默认：返回当前时间
            now = datetime.now()
            return {
                "success": True,
                "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": now.timestamp(),
                "timezone": "local",
                "formatted": f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}"
            }
            
        except Exception as e:
            logger.error(f"时间工具执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
