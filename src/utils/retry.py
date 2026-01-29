"""
重试工具 - 智能重试机制（指数退避）
"""

import asyncio
import time
from typing import Callable, Any, Optional, Type, Tuple, List
from functools import wraps
from loguru import logger


class RetryableError(Exception):
    """可重试的错误"""
    pass


class NonRetryableError(Exception):
    """不可重试的错误"""
    pass


def is_retryable_error(error: Exception) -> bool:
    """
    判断错误是否可重试
    
    Args:
        error: 异常对象
    
    Returns:
        是否可重试
    """
    # 网络相关错误 - 可重试
    retryable_errors = (
        TimeoutError,
        ConnectionError,
        OSError,  # 包含网络错误
    )
    
    # 检查异常类型
    if isinstance(error, retryable_errors):
        return True
    
    # 检查异常消息中的关键词
    error_msg = str(error).lower()
    retryable_keywords = [
        "timeout", "超时",
        "connection", "连接",
        "network", "网络",
        "temporary", "临时",
        "unavailable", "不可用",
        "rate limit", "限流",
        "503", "502", "504"  # 服务不可用、网关错误、超时
    ]
    
    if any(keyword in error_msg for keyword in retryable_keywords):
        return True
    
    # 非重试错误
    non_retryable_keywords = [
        "400", "401", "403", "404",  # 客户端错误
        "invalid", "无效",
        "authentication", "认证",
        "authorization", "授权"
    ]
    
    if any(keyword in error_msg for keyword in non_retryable_keywords):
        return False
    
    # 默认：未知错误可重试
    return True


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> Any:
    """
    带指数退避的重试机制
    
    Args:
        func: 要执行的函数（可以是同步或异步）
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数
        retryable_exceptions: 可重试的异常类型
        on_retry: 重试时的回调函数 (attempt, error) -> None
    
    Returns:
        函数执行结果
    
    Raises:
        最后一次尝试的异常
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                result = func()
            return result
        
        except retryable_exceptions as e:
            last_exception = e
            
            # 判断是否可重试
            if not is_retryable_error(e):
                logger.warning(f"遇到不可重试的错误: {e}")
                raise
            
            # 如果已经是最后一次尝试，直接抛出异常
            if attempt >= max_retries:
                logger.error(f"重试 {max_retries} 次后仍然失败: {e}")
                raise
            
            # 计算延迟时间（指数退避）
            delay = min(
                initial_delay * (exponential_base ** attempt),
                max_delay
            )
            
            # 添加随机抖动（避免雷群效应）
            import random
            jitter = random.uniform(0, delay * 0.1)
            delay += jitter
            
            logger.warning(
                f"第 {attempt + 1} 次尝试失败: {e}, "
                f"{delay:.2f}秒后重试 (剩余 {max_retries - attempt} 次)"
            )
            
            # 调用重试回调
            if on_retry:
                try:
                    if asyncio.iscoroutinefunction(on_retry):
                        await on_retry(attempt + 1, e)
                    else:
                        on_retry(attempt + 1, e)
                except Exception as callback_error:
                    logger.error(f"重试回调函数执行失败: {callback_error}")
            
            # 等待后重试
            await asyncio.sleep(delay)
        
        except Exception as e:
            # 非预期的异常，直接抛出
            logger.error(f"遇到非预期异常: {e}")
            raise
    
    # 理论上不会到达这里
    if last_exception:
        raise last_exception
    raise Exception("重试机制异常")


def retry_sync(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    同步函数的重试装饰器
    
    Usage:
        @retry_sync(max_retries=3)
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            def sync_func():
                return func(*args, **kwargs)
            
            return await retry_with_backoff(
                sync_func,
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                retryable_exceptions=retryable_exceptions
            )
        
        return async_wrapper
    return decorator


def retry_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    异步函数的重试装饰器
    
    Usage:
        @retry_async(max_retries=3)
        async def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async def async_func():
                return await func(*args, **kwargs)
            
            return await retry_with_backoff(
                async_func,
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                retryable_exceptions=retryable_exceptions
            )
        
        return wrapper
    return decorator
