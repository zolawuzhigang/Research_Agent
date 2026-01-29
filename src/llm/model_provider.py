"""
模型提供者抽象层 - 支持API云上模型和本地部署模型
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from loguru import logger


class BaseModelProvider(ABC):
    """模型提供者基类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化模型提供者
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.model_name = config.get("model_name", "")
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 2000)
        self.timeout = config.get("timeout", 60)
    
    @abstractmethod
    def chat(self, 
             messages: List[Dict[str, str]],
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             stream: bool = False) -> Dict[str, Any]:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式返回
        
        Returns:
            API响应
        """
        pass
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """
        生成文本（简化接口）
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
        
        Returns:
            生成的文本
        """
        pass
    
    @abstractmethod
    async def generate_async(self, prompt: str, system_prompt: str = None) -> str:
        """
        生成文本（异步版本）
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
        
        Returns:
            生成的文本
        """
        pass


class APIModelProvider(BaseModelProvider):
    """API云上模型提供者（OpenAI兼容API）"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        import os
        # 严格按配置/环境变量读取，不允许回退到“写死的基座模型”
        self.api_base = (config.get("api_base") or os.getenv("LLM_API_BASE") or "").strip()
        self.api_key = (config.get("api_key") or os.getenv("LLM_API_KEY") or "").strip()

        if not self.api_base:
            raise ValueError("APIModelProvider requires model.api_base (or env LLM_API_BASE)")
        if not self.api_key:
            raise ValueError("APIModelProvider requires model.api_key (or env LLM_API_KEY)")

        # model_name 必须明确配置（避免隐式默认导致“换了基座模型还不知道”）
        if not (self.model_name or "").strip():
            raise ValueError("APIModelProvider requires model.model_name (or env LLM_MODEL)")
        
        # 确保requests可用
        try:
            import requests
            self.requests = requests
            REQUESTS_AVAILABLE = True
        except ImportError:
            REQUESTS_AVAILABLE = False
            logger.error("requests库未安装，API模型提供者将无法工作")
        
        logger.info(f"APIModelProvider initialized: model={self.model_name}, api_base={self.api_base[:50]}...")
    
    def chat(self, 
             messages: List[Dict[str, str]],
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             stream: bool = False) -> Dict[str, Any]:
        """发送聊天请求（同步）"""
        if not hasattr(self, 'requests'):
            raise Exception("requests库不可用，请安装requests库")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if stream:
            headers["Accept"] = "text/event-stream"
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": stream
        }
        
        # 记录性能指标
        from ..utils.metrics import get_metrics
        start_time = time.time()
        
        try:
            logger.info(f"发送LLM API请求: {self.api_base}, model: {self.model_name}")
            response = self.requests.post(
                self.api_base,
                headers=headers,
                json=data,
                timeout=self.timeout,
                stream=stream
            )
            duration = time.time() - start_time
            get_metrics().record_performance("llm_api_call", duration)
            
            logger.info(f"收到LLM API响应，状态码: {response.status_code}")
            response.raise_for_status()
            
            if stream:
                return self._handle_stream_response(response)
            else:
                result = response.json()
                logger.info(f"解析JSON响应成功，包含keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
                
                if not isinstance(result, dict):
                    raise Exception(f"LLM响应格式错误: 期望dict，得到{type(result)}")
                
                # 兼容某些代理把OpenAI响应包在 body 里：{"status":"200","body":{...choices...}}
                if "body" in result and isinstance(result.get("body"), dict):
                    return result["body"]
                
                return result
                
        except self.requests.exceptions.Timeout:
            duration = time.time() - start_time
            get_metrics().record_performance("llm_api_call", duration)
            get_metrics().record_error("TimeoutError", "LLM API调用超时")
            logger.error("LLM API调用超时")
            raise Exception("LLM API调用超时，请稍后重试")
        except self.requests.exceptions.ConnectionError as e:
            duration = time.time() - start_time
            get_metrics().record_performance("llm_api_call", duration)
            get_metrics().record_error("ConnectionError", str(e))
            logger.error(f"LLM API连接失败: {e}")
            raise Exception(f"无法连接到LLM服务: {str(e)}")
        except self.requests.exceptions.HTTPError as e:
            duration = time.time() - start_time
            get_metrics().record_performance("llm_api_call", duration)
            get_metrics().record_error(f"HTTPError_{e.response.status_code}", e.response.text[:200])
            logger.error(f"LLM API HTTP错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LLM API HTTP错误: {e.response.status_code}")
        except self.requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            get_metrics().record_performance("llm_api_call", duration)
            get_metrics().record_error("RequestException", str(e))
            logger.error(f"LLM API调用失败: {e}")
            raise Exception(f"LLM API调用失败: {str(e)}")
        except json.JSONDecodeError as e:
            duration = time.time() - start_time
            get_metrics().record_performance("llm_api_call", duration)
            get_metrics().record_error("JSONDecodeError", str(e))
            logger.error(f"LLM响应JSON解析失败: {e}")
            raise Exception(f"LLM响应格式错误: JSON解析失败")
    
    def _handle_stream_response(self, response):
        """处理流式响应"""
        # TODO: 实现流式响应处理
        return {"error": "流式响应暂未实现"}
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """生成文本（同步）"""
        import json
        from ..utils.retry import RetryableError, NonRetryableError
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        logger.info(f"调用LLM chat方法，消息数量: {len(messages)}")
        response = self.chat(messages)
        logger.info(f"LLM chat返回，响应类型: {type(response)}")
        
        # 提取回复内容（兼容OpenAI格式）
        if isinstance(response, dict) and "choices" in response and isinstance(response["choices"], list) and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            logger.info(f"提取到回复内容，长度: {len(content) if content else 0}")
            if content:
                logger.info(f"内容预览: {content[:100]}...")
            return content
        
        # 兼容某些网关/代理的错误格式：{"status": "...", "msg": "...", ...}
        if isinstance(response, dict) and ("msg" in response or "message" in response) and ("status" in response or "code" in response):
            msg = str(response.get("msg") or response.get("message") or "").strip()
            status = str(response.get("status") or response.get("code") or "").strip()
            lowered = (msg + " " + status).lower()
            logger.error(f"LLM返回错误格式响应: status={status}, msg={msg}")
            # 449/429/限流 视为可重试
            if status in {"449", "429"} or "rate limit" in lowered or "限流" in lowered or "too many" in lowered:
                raise RetryableError(f"LLM rate limited ({status}): {msg}")
            # 401/403/认证失败通常不可重试
            if status in {"401", "403"} or "unauthorized" in lowered or "forbidden" in lowered:
                raise NonRetryableError(f"LLM auth error ({status}): {msg}")
            # 其他网关错误，默认可重试
            raise RetryableError(f"LLM gateway error ({status}): {msg}")
        
        # 兼容 {body:{...}, status/msg/...} 已在 chat() 展开；若仍存在 body 字段再兜底一次
        if isinstance(response, dict) and "body" in response and isinstance(response.get("body"), dict):
            response = response["body"]
            if "choices" in response and isinstance(response["choices"], list) and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]
                return content

        logger.error(f"LLM响应格式错误，缺少choices字段: {response}")
        raise Exception(f"LLM响应格式错误: {response}")
    
    async def generate_async(self, prompt: str, system_prompt: str = None) -> str:
        """生成文本（异步版本）"""
        import asyncio
        from ..utils.retry import retry_with_backoff, RetryableError, NonRetryableError
        
        loop = asyncio.get_event_loop()
        try:
            async def _call_in_thread():
                if hasattr(asyncio, 'to_thread'):
                    return await asyncio.to_thread(self.generate, prompt, system_prompt)
                return await loop.run_in_executor(None, lambda: self.generate(prompt, system_prompt))
            
            # 对可重试错误自动重试（尤其是限流/临时网关错误）
            return await retry_with_backoff(
                _call_in_thread,
                max_retries=2,
                initial_delay=1.0,
                max_delay=8.0,
                retryable_exceptions=(RetryableError, Exception),
            )
        except Exception as e:
            logger.error(f"异步生成文本失败: {e}")
            raise


class LocalModelProvider(BaseModelProvider):
    """本地部署模型提供者"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.model_path = config.get("model_path", "")
        self.device = config.get("device", "cuda")  # cuda, cpu
        self.load_in_8bit = config.get("load_in_8bit", False)
        self.load_in_4bit = config.get("load_in_4bit", False)
        
        # 延迟加载模型（避免启动时加载）
        self._model = None
        self._tokenizer = None
        self._model_loaded = False
        
        logger.info(f"LocalModelProvider initialized: model_path={self.model_path}, device={self.device}")
    
    def _load_model(self):
        """延迟加载模型"""
        if self._model_loaded:
            return
        
        try:
            logger.info(f"正在加载本地模型: {self.model_path}")
            
            # 尝试使用transformers加载
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                import torch
                
                # 加载tokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_path,
                    trust_remote_code=True
                )
                
                # 加载模型
                load_kwargs = {
                    "trust_remote_code": True,
                    "device_map": "auto" if self.device == "cuda" else None
                }
                
                if self.load_in_8bit:
                    load_kwargs["load_in_8bit"] = True
                elif self.load_in_4bit:
                    load_kwargs["load_in_4bit"] = True
                
                self._model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    **load_kwargs
                )
                
                if self.device == "cpu":
                    self._model = self._model.to("cpu")
                
                self._model.eval()
                self._model_loaded = True
                logger.info("本地模型加载成功")
                
            except ImportError:
                logger.warning("transformers库未安装，无法加载本地模型")
                raise Exception("transformers库未安装，请安装: pip install transformers torch")
            except Exception as e:
                logger.error(f"加载本地模型失败: {e}")
                raise Exception(f"加载本地模型失败: {str(e)}")
                
        except Exception as e:
            logger.exception(f"模型加载异常: {e}")
            raise
    
    def chat(self, 
             messages: List[Dict[str, str]],
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             stream: bool = False) -> Dict[str, Any]:
        """发送聊天请求（本地模型）"""
        if not self._model_loaded:
            self._load_model()
        
        # 构建提示词
        prompt = self._format_messages(messages)
        
        # 生成文本
        try:
            import torch
        except ImportError:
            raise Exception("torch库未安装，请安装: pip install torch")
        
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if self.device == "cuda" and hasattr(inputs, 'to'):
            inputs = inputs.to(self._model.device)
        
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_length=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                do_sample=temperature is not None and temperature > 0,
                pad_token_id=self._tokenizer.eos_token_id if self._tokenizer.eos_token_id else self._tokenizer.pad_token_id
            )
        
        # 解码输出
        generated_text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # 提取新生成的部分
        response_text = generated_text[len(prompt):].strip()
        
        # 返回OpenAI兼容格式
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(inputs.input_ids[0]),
                "completion_tokens": len(outputs[0]) - len(inputs.input_ids[0]),
                "total_tokens": len(outputs[0])
            }
        }
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """格式化消息为提示词"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        
        formatted.append("Assistant:")
        return "\n".join(formatted)
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """生成文本（同步）"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.chat(messages)
        
        if "choices" in response and len(response["choices"]) > 0:
            return response["choices"][0]["message"]["content"]
        else:
            raise Exception(f"本地模型响应格式错误: {response}")
    
    async def generate_async(self, prompt: str, system_prompt: str = None) -> str:
        """生成文本（异步版本）"""
        import asyncio
        
        loop = asyncio.get_event_loop()
        try:
            if hasattr(asyncio, 'to_thread'):
                return await asyncio.to_thread(self.generate, prompt, system_prompt)
            else:
                return await loop.run_in_executor(None, lambda: self.generate(prompt, system_prompt))
        except Exception as e:
            logger.error(f"异步生成文本失败: {e}")
            raise


class ModelProviderFactory:
    """模型提供者工厂"""
    
    @staticmethod
    def create_provider(config: Dict[str, Any]) -> BaseModelProvider:
        """
        创建模型提供者
        
        Args:
            config: 配置字典，必须包含 provider 字段
        
        Returns:
            模型提供者实例
        """
        provider_type = config.get("provider", "api").lower()
        
        if provider_type in ["api", "openai", "custom", "cloud"]:
            logger.info("使用API云上模型提供者")
            return APIModelProvider(config)
        elif provider_type in ["local", "local_model", "huggingface", "transformers"]:
            logger.info("使用本地部署模型提供者")
            return LocalModelProvider(config)
        else:
            logger.warning(f"未知的提供者类型: {provider_type}，默认使用API提供者")
            return APIModelProvider(config)
