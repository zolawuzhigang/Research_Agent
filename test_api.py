"""
测试API服务
"""

import requests
import json

# API配置
BASE_URL = "http://localhost:8000"
TOKEN = "test_token"  # 测试用token，实际应该从环境变量获取

def test_predict():
    """测试预测接口"""
    url = f"{BASE_URL}/api/v1/predict"
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 测试问题
    test_questions = [
        "法国首都在哪里？",
        "计算 2 + 3 * 4 的结果",
        "什么是人工智能？"
    ]
    
    print("=" * 60)
    print("测试Research Agent API")
    print("=" * 60)
    
    for question in test_questions:
        print(f"\n问题: {question}")
        print("-" * 60)
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json={"question": question},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"答案: {result.get('answer', '')}")
            else:
                print(f"错误: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"请求失败: {e}")
    
    print("\n" + "=" * 60)


def test_health():
    """测试健康检查"""
    url = f"{BASE_URL}/health"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print("服务健康:", response.json())
        else:
            print(f"健康检查失败: {response.status_code}")
    except Exception as e:
        print(f"无法连接到服务: {e}")


if __name__ == "__main__":
    print("检查服务状态...")
    test_health()
    print("\n")
    test_predict()
