"""
测试千问基座模型API是否可访问
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import json
from loguru import logger

# 测试配置
API_BASE = "https://newapi.3173721.xyz/v1/chat/completions"
API_KEY = "sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz"
MODELS = ["qwen3-max", "qwen3-max-preview"]


def test_model_api(model_name: str) -> dict:
    """测试单个模型的API调用（使用requests）"""
    try:
        import requests
    except ImportError:
        logger.error("requests库未安装，请运行: pip install requests")
        return {
            "success": False,
            "model": model_name,
            "error": "requests库未安装"
        }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": "你好，请简单介绍一下你自己。"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    logger.info(f"测试模型: {model_name}")
    logger.info(f"API地址: {API_BASE}")
    
    try:
        response = requests.post(
            API_BASE,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        status = response.status_code
        logger.info(f"HTTP状态码: {status}")
        
        if status == 200:
            result = response.json()
            logger.info(f"响应成功: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
            
            # 提取回复内容
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                logger.success(f"模型回复: {content[:200]}")
                return {
                    "success": True,
                    "model": model_name,
                    "status": status,
                    "response": content,
                    "full_response": result
                }
            else:
                logger.warning(f"响应格式异常: {result}")
                return {
                    "success": False,
                    "model": model_name,
                    "status": status,
                    "error": "响应格式异常",
                    "response": result
                }
        else:
            error_text = response.text
            logger.error(f"API调用失败: {error_text[:500]}")
            return {
                "success": False,
                "model": model_name,
                "status": status,
                "error": error_text[:500]
            }
    except requests.Timeout:
        logger.error(f"请求超时: {model_name}")
        return {
            "success": False,
            "model": model_name,
            "error": "请求超时"
        }
    except Exception as e:
        logger.exception(f"测试模型 {model_name} 时发生异常: {e}")
        return {
            "success": False,
            "model": model_name,
            "error": str(e)
        }


async def test_with_llm_client(model_name: str) -> dict:
    """使用项目的LLMClient测试"""
    try:
        from src.llm.llm_client import LLMClient
        from src.config.config_loader import get_config
        
        # 临时修改配置
        config = get_config()
        model_config = config.get_section("model") or {}
        original_api_base = model_config.get("api_base")
        original_api_key = model_config.get("api_key")
        original_model = model_config.get("model")
        
        # 设置测试配置
        model_config["api_base"] = API_BASE
        model_config["api_key"] = API_KEY
        model_config["model"] = model_name
        model_config["provider"] = "api"
        
        logger.info(f"使用LLMClient测试模型: {model_name}")
        
        # 创建新的LLMClient实例
        client = LLMClient()
        
        # 测试生成
        prompt = "你好，请用一句话介绍你自己。"
        result = await client.generate_async(prompt)
        
        logger.success(f"LLMClient测试成功: {result[:200]}")
        
        return {
            "success": True,
            "model": model_name,
            "method": "LLMClient",
            "response": result
        }
    except Exception as e:
        logger.exception(f"LLMClient测试失败: {e}")
        return {
            "success": False,
            "model": model_name,
            "method": "LLMClient",
            "error": str(e)
        }


def main():
    """主测试函数"""
    print("=" * 80)
    print("千问基座模型API测试")
    print("=" * 80)
    print(f"API地址: {API_BASE}")
    print(f"API Key: {API_KEY[:20]}...")
    print(f"测试模型: {', '.join(MODELS)}")
    print("=" * 80)
    print()
    
    results = []
    
    # 测试每个模型
    for model in MODELS:
        print(f"\n{'='*80}")
        print(f"测试模型: {model}")
        print(f"{'='*80}\n")
        
        # 方法1: 直接API调用
        print("方法1: 直接API调用")
        result1 = test_model_api(model)
        results.append(result1)
        
        if result1.get("success"):
            print(f"✅ {model} - API调用成功")
            print(f"   回复: {result1.get('response', '')[:100]}...")
        else:
            print(f"❌ {model} - API调用失败: {result1.get('error', '未知错误')}")
        
        print()
        
        # 方法2: 使用LLMClient
        print("方法2: 使用项目LLMClient")
        result2 = asyncio.run(test_with_llm_client(model))
        results.append(result2)
        
        if result2.get("success"):
            print(f"✅ {model} - LLMClient调用成功")
            print(f"   回复: {result2.get('response', '')[:100]}...")
        else:
            print(f"❌ {model} - LLMClient调用失败: {result2.get('error', '未知错误')}")
        
        print()
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    success_count = sum(1 for r in results if r.get("success"))
    total_count = len(results)
    
    print(f"总测试数: {total_count}")
    print(f"成功数: {success_count}")
    print(f"失败数: {total_count - success_count}")
    print()
    
    for result in results:
        model = result.get("model", "unknown")
        method = result.get("method", "直接API")
        success = result.get("success", False)
        status = "✅" if success else "❌"
        print(f"{status} {model} ({method}): ", end="")
        if success:
            response = result.get("response", "")
            print(f"成功 - {response[:50]}...")
        else:
            error = result.get("error", "未知错误")
            print(f"失败 - {error[:100]}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
