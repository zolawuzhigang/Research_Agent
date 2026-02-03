"""
配置加载器 - 统一管理配置
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径（可选）
        """
        self.config_path = config_path or self._find_config_file()
        self.config: Dict[str, Any] = {}
        self._load_config()
        self._load_env_vars()
    
    def _find_config_file(self) -> Optional[str]:
        """查找配置文件"""
        # 查找项目根目录下的config.yaml
        project_root = Path(__file__).parent.parent.parent
        config_file = project_root / "config" / "config.yaml"
        
        if config_file.exists():
            return str(config_file)
        
        return None
    
    def _load_config(self):
        """加载YAML配置文件（快速加载，不阻塞）"""
        if not self.config_path:
            raise FileNotFoundError("未找到 config/config.yaml，严格模式下禁止使用默认模型配置")
        
        try:
            # 快速读取，不进行复杂处理
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            logger.debug(f"配置文件加载成功: {self.config_path}")
        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败: {e}") from e
    
    def _load_env_vars(self):
        """从环境变量加载配置（覆盖配置文件）"""
        # LLM配置
        if os.getenv("LLM_API_BASE"):
            self.config.setdefault("model", {})["api_base"] = os.getenv("LLM_API_BASE")
        
        if os.getenv("LLM_API_KEY"):
            self.config.setdefault("model", {})["api_key"] = os.getenv("LLM_API_KEY")
        
        if os.getenv("LLM_MODEL"):
            self.config.setdefault("model", {})["model_name"] = os.getenv("LLM_MODEL")
        
        # 搜索工具配置
        if os.getenv("SERPAPI_KEY"):
            self.config.setdefault("tools", {})["serpapi_key"] = os.getenv("SERPAPI_KEY")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "agent": {
                "name": "TianchiAgent",
                "version": "1.0.0",
                "mode": "production"
            },
            "model": {
                # 默认配置不再内置任何基座模型/URL/密钥，强制用户通过配置文件或环境变量显式提供
                "provider": "api",
                "model_name": "",
                "api_base": "",
                "api_key": "",
                "temperature": 0.1,
                "max_tokens": 2000,
                "timeout": 60
            },
            "task": {
                "max_retries": 3,
                "timeout": 300,
                "parallel_execution": True,
                "max_parallel_tasks": 5
            },
            "logging": {
                "level": "INFO",
                "file": "logs/agent.log",
                "rotation": "10 MB",
                "retention": "7 days"
            },
            "tools": {
                "enabled": [],
                "timeout": 10,
                "max_retries": 2
            },
            "memory": {
                "short_term_size": 100,
                "long_term_enabled": True,
                "context_window": 4096
            },
            "performance": {
                "cache_enabled": True,
                "cache_ttl": 3600,
                "async_execution": True
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的嵌套键）
        
        Args:
            key: 配置键（如 "model.temperature"）
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置段落"""
        return self.config.get(section, {})
    
    def get_log_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.config.get("logging", {
            "level": "INFO",
            "file": "logs/agent.log",
            "rotation": "10 MB",
            "retention": "7 days"
        })
    
    def update(self, key: str, value: Any):
        """更新配置值"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value


# 全局配置实例
_global_config: Optional[ConfigLoader] = None


def get_config(config_path: Optional[str] = None) -> ConfigLoader:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = ConfigLoader(config_path)
    return _global_config
