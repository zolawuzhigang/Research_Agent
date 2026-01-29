"""
缓存工具 - 结果缓存系统
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
from loguru import logger


class SimpleCache:
    """简单的内存缓存"""
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 1000):
        """
        初始化缓存
        
        Args:
            default_ttl: 默认过期时间（秒）
            max_size: 最大缓存条目数
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        logger.info(f"SimpleCache initialized (ttl={default_ttl}s, max_size={max_size})")
    
    def _generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        # 将参数序列化为字符串
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        # 使用MD5生成短键
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
        
        Returns:
            缓存值，如果不存在或已过期返回None
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        expire_time = entry.get("expire_time")
        
        # 检查是否过期
        if expire_time and time.time() > expire_time:
            logger.debug(f"缓存键 {key} 已过期")
            del self.cache[key]
            return None
        
        # 更新访问时间
        entry["access_time"] = time.time()
        logger.debug(f"缓存命中: {key}")
        return entry.get("value")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值
        """
        # 如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        ttl = ttl or self.default_ttl
        expire_time = time.time() + ttl
        
        self.cache[key] = {
            "value": value,
            "expire_time": expire_time,
            "access_time": time.time(),
            "created_time": time.time()
        }
        logger.debug(f"缓存设置: {key} (ttl={ttl}s)")
    
    def _evict_oldest(self):
        """删除最旧的缓存条目"""
        if not self.cache:
            return
        
        # 找到最久未访问的条目
        oldest_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].get("access_time", 0)
        )
        del self.cache[oldest_key]
        logger.debug(f"缓存淘汰: {oldest_key}")
    
    def delete(self, key: str) -> None:
        """删除缓存条目"""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"缓存删除: {key}")
    
    def clear(self) -> None:
        """清空所有缓存"""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"缓存清空: 删除了 {count} 条条目")
    
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        now = time.time()
        valid_entries = sum(
            1 for entry in self.cache.values()
            if not entry.get("expire_time") or entry.get("expire_time", 0) > now
        )
        
        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self.cache) - valid_entries,
            "max_size": self.max_size,
            "default_ttl": self.default_ttl
        }


# 全局缓存实例
_global_cache: Optional[SimpleCache] = None


def get_cache() -> SimpleCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        try:
            from ..config.config_loader import get_config
            config = get_config()
            perf_config = config.get_section("performance") or {}
            cache_ttl = perf_config.get("cache_ttl", 3600)
        except Exception:
            cache_ttl = 3600
        _global_cache = SimpleCache(default_ttl=cache_ttl, max_size=1000)
    return _global_cache


def cached(
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None
):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存过期时间（秒），None使用默认值
        key_func: 自定义键生成函数 (func, *args, **kwargs) -> str
    
    Usage:
        @cached(ttl=3600)
        async def my_function(arg1, arg2):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache()
            
            # 生成缓存键
            if key_func:
                cache_key = key_func(func, *args, **kwargs)
            else:
                cache_key = cache._generate_key(func.__name__, *args, **kwargs)
            
            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"缓存命中: {func.__name__}")
                return cached_value
            
            # 执行函数
            if asyncio and asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, ttl=ttl)
            logger.debug(f"缓存设置: {func.__name__}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = get_cache()
            
            # 生成缓存键
            if key_func:
                cache_key = key_func(func, *args, **kwargs)
            else:
                cache_key = cache._generate_key(func.__name__, *args, **kwargs)
            
            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"缓存命中: {func.__name__}")
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, ttl=ttl)
            logger.debug(f"缓存设置: {func.__name__}")
            
            return result
        
        if asyncio and asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 导入asyncio用于检查协程函数
try:
    import asyncio
except ImportError:
    asyncio = None
