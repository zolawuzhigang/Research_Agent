"""
LLM客户端 - 封装LLM调用（支持API云上模型和本地部署模型）
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger

from .model_provider import ModelProviderFactory, BaseModelProvider, LocalModelProvider


class LLMClient:
    """LLM客户端 - 支持API云上模型和本地部署模型"""
    
    def __init__(self, 
                 api_base: str = None,
                 api_key: str = None,
                 model: str = None,
                 temperature: float = None,
                 max_tokens: int = None,
                 provider: str = None,
                 config: Dict[str, Any] = None):
        """
        初始化LLM客户端
        
        Args:
            api_base: API基础URL（可选，优先使用，仅用于API提供者）
            api_key: API密钥（可选，优先使用，仅用于API提供者）
            model: 模型ID（可选，优先使用）
            temperature: 温度参数（可选）
            max_tokens: 最大token数（可选）
            provider: 提供者类型（"api" 或 "local"，可选）
            config: 配置字典（可选，用于批量设置）
        """
        # 优先使用传入参数，其次环境变量，最后配置文件
        if config is None:
            try:
                from ..config.config_loader import get_config
                config = get_config().get_section("model")
            except Exception:
                config = {}
        
        # 确定提供者类型
        provider_type = (
            provider or 
            os.getenv("LLM_PROVIDER") or 
            config.get("provider", "api")
        ).lower()
        
        # 构建提供者配置
        provider_config = {
            "provider": provider_type,
            "model_name": (
                model or 
                os.getenv("LLM_MODEL") or 
                config.get("model_name") or 
                ""
            ),
            "temperature": (
                temperature if temperature is not None else 
                config.get("temperature", 0.1)
            ),
            "max_tokens": (
                max_tokens if max_tokens is not None else 
                config.get("max_tokens", 2000)
            ),
            "timeout": config.get("timeout", 60)
        }
        
        # 根据提供者类型添加特定配置
        if provider_type in ["api", "openai", "custom", "cloud"]:
            provider_config["api_base"] = (
                api_base or 
                os.getenv("LLM_API_BASE") or 
                config.get("api_base") or 
                ""
            )
            provider_config["api_key"] = (
                api_key or 
                os.getenv("LLM_API_KEY") or 
                config.get("api_key") or 
                ""
            )
        elif provider_type in ["local", "local_model", "huggingface", "transformers"]:
            provider_config["model_path"] = (
                config.get("model_path") or 
                os.getenv("LLM_MODEL_PATH") or 
                ""
            )
            provider_config["device"] = config.get("device", "cuda")
            provider_config["load_in_8bit"] = config.get("load_in_8bit", False)
            provider_config["load_in_4bit"] = config.get("load_in_4bit", False)
        
        # 强校验：彻底与代码解耦（缺配置就直接报错，不允许“写死回退”）
        if not provider_config.get("model_name"):
            raise ValueError("LLMClient requires model.model_name (or env LLM_MODEL)")
        if provider_type in ["api", "openai", "custom", "cloud"]:
            if not provider_config.get("api_base"):
                raise ValueError("LLMClient requires model.api_base (or env LLM_API_BASE)")
            if not provider_config.get("api_key"):
                raise ValueError("LLMClient requires model.api_key (or env LLM_API_KEY)")

        # 创建模型提供者
        try:
            self.provider: BaseModelProvider = ModelProviderFactory.create_provider(provider_config)
            self.model = provider_config["model_name"]
            self.temperature = provider_config["temperature"]
            self.max_tokens = provider_config["max_tokens"]
            logger.info(f"LLMClient initialized: provider={provider_type}, model={self.model}")
        except Exception as e:
            logger.exception(f"初始化模型提供者失败: {e}")
            # 严格模式：不做“换基座模型”的隐式降级，直接向上抛错
            raise
    
    def chat(self, 
             messages: List[Dict[str, str]],
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             stream: bool = False) -> Dict[str, Any]:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表，格式：[{"role": "user", "content": "..."}]
            temperature: 温度参数（可选，使用默认值）
            max_tokens: 最大token数（可选，使用默认值）
            stream: 是否流式返回
        
        Returns:
            API响应
        """
        return self.provider.chat(messages, temperature, max_tokens, stream)
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """
        生成文本（简化接口）- 同步方法
        
        注意：在异步环境中调用时，应使用 generate_async 方法
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
        
        Returns:
            生成的文本
        """
        try:
            return self.provider.generate(prompt, system_prompt)
        except Exception as e:
            logger.exception(f"generate方法执行失败: {e}")
            raise
    
    async def generate_async(self, prompt: str, system_prompt: str = None) -> str:
        """
        生成文本（异步版本）
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
        
        Returns:
            生成的文本
        """
        return await self.provider.generate_async(prompt, system_prompt)
    
    def generate_with_tools(self, 
                           prompt: str,
                           tools: List[Dict[str, Any]] = None,
                           system_prompt: str = None) -> Dict[str, Any]:
        """
        使用工具调用生成
        
        Args:
            prompt: 用户提示词
            tools: 工具列表（function calling格式）
            system_prompt: 系统提示词
        
        Returns:
            包含回复和工具调用的响应
        
        注意：目前只有API提供者支持工具调用
        """
        # 对于本地模型，暂时不支持工具调用
        if isinstance(self.provider, LocalModelProvider):
            logger.warning("本地模型暂不支持工具调用，使用普通生成")
            result = self.provider.generate(prompt, system_prompt)
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": result
                    }
                }]
            }
        
        # API提供者支持工具调用
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # 使用提供者的chat方法，但需要添加tools参数
        # 注意：这需要扩展BaseModelProvider接口以支持tools参数
        # 目前简化实现：直接调用chat，工具调用功能待扩展
        return self.provider.chat(messages)
