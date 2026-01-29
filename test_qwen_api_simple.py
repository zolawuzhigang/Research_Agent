"""
简单的千问API连接测试
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests
import json
from loguru import logger

# 测试配置
API_BASE = "https://newapi.3173721.xyz/v1/chat/completions"
API_KEY = "sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz"
MODELS = ["qwen3-max", "qwen3-max-preview"]


def test_connection():
    """测试基本连接"""
    print("=" * 80)
    print("1. 测试基本连接")
    print("=" * 80)
    
    try:
        # 只测试连接，不发送完整请求
        response = requests.get(API_BASE.replace("/v1/chat/completions", ""), timeout=5)
        print(f"✅ 服务器可访问，状态码: {response.status_code}")
        return True
    except requests.exceptions.Timeout:
        print("❌ 连接超时 - 服务器可能无法访问")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False


def test_api_call(model_name: str, timeout: int = 10):
    """测试API调用（短超时）"""
    print(f"\n{'='*80}")
    print(f"2. 测试API调用 - {model_name}")
    print(f"{'='*80}")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": "你好"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 10  # 只请求10个token，快速测试
    }
    
    print(f"API地址: {API_BASE}")
    print(f"模型: {model_name}")
    print(f"超时设置: {timeout}秒")
    print("发送请求...")
    
    try:
        response = requests.post(
            API_BASE,
            headers=headers,
            json=payload,
            timeout=timeout
        )
        
        print(f"\nHTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                print(f"✅ API调用成功！")
                print(f"模型回复: {content}")
                return True
            else:
                print(f"⚠️ 响应格式异常: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
                return False
        elif response.status_code == 401:
            print("❌ 认证失败 - API Key可能无效")
            print(f"响应: {response.text[:200]}")
            return False
        elif response.status_code == 404:
            print("❌ 接口不存在 - 请检查API地址")
            return False
        else:
            print(f"❌ API调用失败，状态码: {response.status_code}")
            print(f"响应: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时（{timeout}秒）")
        print("可能原因:")
        print("  1. 服务器响应慢")
        print("  2. 网络连接问题")
        print("  3. API服务不可用")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("千问基座模型API诊断测试")
    print("=" * 80)
    print(f"API地址: {API_BASE}")
    print(f"API Key: {API_KEY[:20]}...")
    print(f"测试模型: {', '.join(MODELS)}")
    print("=" * 80)
    
    # 测试1: 基本连接
    connection_ok = test_connection()
    
    if not connection_ok:
        print("\n⚠️ 基本连接失败，跳过API调用测试")
        print("\n建议:")
        print("  1. 检查网络连接")
        print("  2. 检查API地址是否正确")
        print("  3. 检查防火墙/代理设置")
        return
    
    # 测试2: API调用
    results = []
    for model in MODELS:
        success = test_api_call(model, timeout=15)  # 增加超时到15秒
        results.append({
            "model": model,
            "success": success
        })
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    for result in results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['model']}: {'成功' if result['success'] else '失败'}")
    
    success_count = sum(1 for r in results if r["success"])
    if success_count == len(results):
        print("\n✅ 所有模型测试通过！")
    elif success_count > 0:
        print(f"\n⚠️ 部分模型可用 ({success_count}/{len(results)})")
    else:
        print("\n❌ 所有模型测试失败")
        print("\n可能原因:")
        print("  1. API Key无效或过期")
        print("  2. 模型ID不正确")
        print("  3. API服务暂时不可用")
        print("  4. 网络连接问题")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
