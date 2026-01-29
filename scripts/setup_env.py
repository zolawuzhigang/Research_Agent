"""
环境设置脚本
"""

import os
import sys
from pathlib import Path


def create_directories():
    """创建必要的目录结构"""
    directories = [
        "data/train",
        "data/test",
        "data/processed",
        "logs",
        "models",
        "results",
        "tests",
        "docs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")


def create_env_file():
    """创建.env示例文件"""
    env_example = """# 环境变量配置

# 大模型API密钥
DASHSCOPE_API_KEY=your_api_key_here
# OPENAI_API_KEY=your_openai_key_here

# 其他配置
LOG_LEVEL=INFO
DEBUG=False
"""
    
    env_file = Path(".env")
    env_example_file = Path(".env.example")
    
    if not env_file.exists():
        env_example_file.write_text(env_example)
        print("✓ Created .env.example file")
        print("⚠ Please copy .env.example to .env and fill in your API keys")
    else:
        print("✓ .env file already exists")


def check_dependencies():
    """检查依赖是否安装"""
    try:
        import numpy
        import pandas
        import yaml
        from loguru import logger
        print("✓ Core dependencies are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("⚠ Please run: pip install -r requirements.txt")
        return False


def main():
    """主函数"""
    print("Setting up development environment...")
    print("-" * 50)
    
    # 创建目录
    create_directories()
    
    # 创建环境变量文件
    create_env_file()
    
    # 检查依赖
    check_dependencies()
    
    print("-" * 50)
    print("Setup complete!")


if __name__ == "__main__":
    main()
