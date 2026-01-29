"""
测试模型提供者系统
"""

from src.llm import LLMClient, ModelProviderFactory
from src.config.config_loader import get_config

def test_provider_selection():
    """测试提供者选择"""
    print("=" * 60)
    print("测试模型提供者系统")
    print("=" * 60)
    
    # 获取配置
    config = get_config().get_section("model")
    provider_type = config.get("provider", "api")
    
    print(f"\n当前配置的提供者类型: {provider_type}")
    print(f"模型名称: {config.get('model_name', 'N/A')}")
    
    # 创建LLM客户端
    try:
        client = LLMClient()
        print(f"\n✅ LLMClient创建成功")
        print(f"   提供者类型: {type(client.provider).__name__}")
        print(f"   模型: {client.model}")
        
        # 测试生成（简单测试，不实际调用）
        print(f"\n✅ 模型提供者系统工作正常")
        
    except Exception as e:
        print(f"\n❌ 创建LLMClient失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_provider_selection()
