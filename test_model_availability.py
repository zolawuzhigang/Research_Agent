#!/usr/bin/env python3
"""
测试基座模型可用性
"""

import asyncio
from src.llm.llm_client import LLMClient

async def test_model_availability():
    """测试基座模型可用性"""
    print("测试基座模型可用性...")
    
    try:
        # 初始化LLM客户端
        client = LLMClient()
        print(f"\n模型配置:")
        print(f"- 提供者类型: {client.provider_type}")
        print(f"- 模型名称: {client.model}")
        print(f"- 温度参数: {client.temperature}")
        print(f"- 最大token数: {client.max_tokens}")
        
        # 测试同步生成
        print("\n测试同步生成...")
        test_prompt = "你好，请问你是谁？"
        result = client.generate(test_prompt)
        print(f"同步生成结果: {result}")
        
        # 测试异步生成
        print("\n测试异步生成...")
        async_result = await client.generate_async(test_prompt)
        print(f"异步生成结果: {async_result}")
        
        # 测试聊天接口
        print("\n测试聊天接口...")
        messages = [
            {"role": "system", "content": "你是一个智能助手"},
            {"role": "user", "content": test_prompt}
        ]
        chat_result = client.chat(messages)
        print(f"聊天接口结果: {chat_result}")
        
        print("\n✅ 基座模型可用！")
        return True
        
    except Exception as e:
        print(f"\n❌ 基座模型不可用: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_model_availability())
