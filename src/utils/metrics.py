"""
指标统计 - 错误分类和性能统计
"""

from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from loguru import logger
import time


@dataclass
class ErrorMetric:
    """错误指标"""
    error_type: str
    count: int = 0
    last_occurred: Optional[datetime] = None
    examples: List[str] = field(default_factory=list)
    max_examples: int = 5


@dataclass
class PerformanceMetric:
    """性能指标"""
    operation: str
    total_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.errors: Dict[str, ErrorMetric] = {}
        self.performance: Dict[str, PerformanceMetric] = {}
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.start_time = datetime.now()
        logger.info("MetricsCollector initialized")
    
    def record_error(self, error_type: str, error_msg: str = ""):
        """
        记录错误
        
        Args:
            error_type: 错误类型（如 "TimeoutError", "ConnectionError"）
            error_msg: 错误消息
        """
        if error_type not in self.errors:
            self.errors[error_type] = ErrorMetric(error_type=error_type)
        
        metric = self.errors[error_type]
        metric.count += 1
        metric.last_occurred = datetime.now()
        
        # 保存错误示例
        if len(metric.examples) < metric.max_examples and error_msg:
            metric.examples.append(error_msg[:200])  # 限制长度
        
        logger.debug(f"记录错误: {error_type} (总数: {metric.count})")
    
    def record_performance(self, operation: str, duration: float):
        """
        记录性能指标
        
        Args:
            operation: 操作名称（如 "llm_call", "tool_execution"）
            duration: 耗时（秒）
        """
        if operation not in self.performance:
            self.performance[operation] = PerformanceMetric(operation=operation)
        
        metric = self.performance[operation]
        metric.total_count += 1
        metric.total_time += duration
        metric.min_time = min(metric.min_time, duration)
        metric.max_time = max(metric.max_time, duration)
        metric.recent_times.append(duration)
        
        logger.debug(f"记录性能: {operation} = {duration:.3f}s")
    
    def record_request(self, success: bool):
        """记录请求"""
        self.request_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        total_errors = sum(m.count for m in self.errors.values())
        
        return {
            "total_errors": total_errors,
            "error_types": {
                error_type: {
                    "count": metric.count,
                    "last_occurred": metric.last_occurred.isoformat() if metric.last_occurred else None,
                    "examples": metric.examples
                }
                for error_type, metric in self.errors.items()
            },
            "top_errors": sorted(
                self.errors.items(),
                key=lambda x: x[1].count,
                reverse=True
            )[:5]
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = {}
        for operation, metric in self.performance.items():
            avg_time = metric.total_time / metric.total_count if metric.total_count > 0 else 0.0
            
            # 计算最近的平均时间
            recent_avg = 0.0
            if metric.recent_times:
                recent_avg = sum(metric.recent_times) / len(metric.recent_times)
            
            stats[operation] = {
                "total_count": metric.total_count,
                "avg_time": avg_time,
                "min_time": metric.min_time if metric.min_time != float('inf') else 0.0,
                "max_time": metric.max_time,
                "recent_avg_time": recent_avg
            }
        
        return stats
    
    def get_summary(self) -> Dict[str, Any]:
        """获取汇总统计"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0.0
        
        return {
            "uptime_seconds": uptime,
            "uptime_formatted": str(timedelta(seconds=int(uptime))),
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": f"{success_rate:.2f}%",
            "errors": self.get_error_stats(),
            "performance": self.get_performance_stats()
        }
    
    def reset(self):
        """重置所有指标"""
        self.errors.clear()
        self.performance.clear()
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.start_time = datetime.now()
        logger.info("指标已重置")


# 全局指标收集器
_global_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """获取全局指标收集器"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics


def track_performance(operation: str):
    """
    性能追踪装饰器
    
    Usage:
        @track_performance("llm_call")
        async def call_llm():
            ...
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                get_metrics().record_performance(operation, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                get_metrics().record_performance(operation, duration)
                get_metrics().record_error(type(e).__name__, str(e))
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                get_metrics().record_performance(operation, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                get_metrics().record_performance(operation, duration)
                get_metrics().record_error(type(e).__name__, str(e))
                raise
        
        if asyncio and asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 导入asyncio
try:
    import asyncio
except ImportError:
    asyncio = None
