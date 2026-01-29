# 模型提供者配置指南

## 📋 概述

系统已实现模型提供者抽象层，支持通过配置文件选择使用 **API云上模型** 或 **本地部署模型**，实现代码与模型的解耦。

## 🏗️ 架构设计

```
LLMClient (统一接口)
    │
    ├─ ModelProviderFactory (工厂)
    │   │
    │   ├─ APIModelProvider (API云上模型)
    │   │   └─ 通过HTTP API调用远程模型
    │   │
    │   └─ LocalModelProvider (本地部署模型)
    │       └─ 使用transformers加载本地模型
```

## 📝 配置文件

### 配置文件位置

`config/config.yaml`

### 配置示例

#### 1. 使用API云上模型（默认）

```yaml
model:
  # 提供者类型: "api" 表示使用API云上模型
  provider: "api"
  
  # API配置
  api_base: "https://newapi.3173721.xyz/v1/chat/completions"
  api_key: "sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz"
  
  # 通用配置
  model_name: "qwen3-max"
  temperature: 0.1
  max_tokens: 2000
  timeout: 60
```

#### 2. 使用本地部署模型

```yaml
model:
  # 提供者类型: "local" 表示使用本地部署模型
  provider: "local"
  
  # 本地模型配置
  model_path: "/path/to/local/model"  # 本地模型路径（HuggingFace格式）
  device: "cuda"  # 设备: "cuda" 或 "cpu"
  load_in_8bit: false  # 是否使用8bit量化（节省显存）
  load_in_4bit: false  # 是否使用4bit量化（节省显存）
  
  # 通用配置
  model_name: "qwen-7b-chat"  # 模型名称（用于日志）
  temperature: 0.1
  max_tokens: 2000
  timeout: 60
```

## 🔧 配置说明

### provider 字段

| 值 | 说明 | 使用场景 |
|---|------|---------|
| `"api"` | API云上模型（默认） | 使用远程API服务 |
| `"openai"` | OpenAI兼容API | 使用OpenAI或兼容服务 |
| `"custom"` | 自定义API | 使用自定义API服务 |
| `"cloud"` | 云服务 | 使用云服务提供商 |
| `"local"` | 本地部署模型 | 使用本地HuggingFace模型 |
| `"huggingface"` | HuggingFace模型 | 同local |
| `"transformers"` | Transformers模型 | 同local |

### API云上模型配置项

| 配置项 | 说明 | 必需 | 默认值 |
|--------|------|------|--------|
| `api_base` | API基础URL | 是 | - |
| `api_key` | API密钥 | 是 | - |
| `model_name` | 模型ID/名称 | 是 | "qwen3-max" |
| `temperature` | 温度参数 | 否 | 0.1 |
| `max_tokens` | 最大token数 | 否 | 2000 |
| `timeout` | 请求超时（秒） | 否 | 60 |

### 本地部署模型配置项

| 配置项 | 说明 | 必需 | 默认值 |
|--------|------|------|--------|
| `model_path` | 本地模型路径 | 是 | - |
| `device` | 设备（cuda/cpu） | 否 | "cuda" |
| `load_in_8bit` | 8bit量化 | 否 | false |
| `load_in_4bit` | 4bit量化 | 否 | false |
| `model_name` | 模型名称（日志用） | 否 | - |
| `temperature` | 温度参数 | 否 | 0.1 |
| `max_tokens` | 最大token数 | 否 | 2000 |

## 🌍 环境变量配置

也可以通过环境变量配置（优先级高于配置文件）：

```bash
# 选择提供者类型
export LLM_PROVIDER="api"  # 或 "local"

# API云上模型配置
export LLM_API_BASE="https://api.example.com/v1/chat/completions"
export LLM_API_KEY="your-api-key"
export LLM_MODEL="qwen3-max"

# 本地模型配置
export LLM_MODEL_PATH="/path/to/local/model"
```

## 💻 代码使用示例

### 使用API云上模型

```python
from src.llm import LLMClient

# 方式1: 使用配置文件
client = LLMClient()

# 方式2: 直接指定配置
client = LLMClient(
    provider="api",
    api_base="https://api.example.com/v1/chat/completions",
    api_key="your-key",
    model="qwen3-max"
)

# 使用
result = client.generate("你好")
```

### 使用本地部署模型

```python
from src.llm import LLMClient

# 方式1: 使用配置文件
client = LLMClient()

# 方式2: 直接指定配置
client = LLMClient(
    provider="local",
    config={
        "model_path": "/path/to/model",
        "device": "cuda",
        "model_name": "qwen-7b-chat"
    }
)

# 使用（接口完全一致）
result = client.generate("你好")
```

## 🔄 切换模型提供者

### 方法1: 修改配置文件

编辑 `config/config.yaml`，修改 `provider` 字段：

```yaml
model:
  provider: "local"  # 从 "api" 改为 "local"
  model_path: "/path/to/model"
```

### 方法2: 使用环境变量

```bash
export LLM_PROVIDER="local"
export LLM_MODEL_PATH="/path/to/model"
```

### 方法3: 代码中指定

```python
client = LLMClient(provider="local", config={"model_path": "/path/to/model"})
```

## 📦 依赖要求

### API云上模型

- `requests` - HTTP请求库

```bash
pip install requests
```

### 本地部署模型

- `transformers` - HuggingFace Transformers库
- `torch` - PyTorch（如果使用GPU）

```bash
pip install transformers torch
```

可选（量化支持）：
```bash
pip install bitsandbytes  # 8bit/4bit量化
```

## ⚠️ 注意事项

### 本地模型加载

1. **延迟加载**: 本地模型在第一次调用时才加载，避免启动时卡住
2. **显存要求**: 确保有足够的GPU显存（或使用CPU模式）
3. **模型格式**: 必须使用HuggingFace格式的模型

### API模型

1. **网络连接**: 确保可以访问API服务
2. **API密钥**: 确保API密钥有效
3. **超时设置**: 根据网络情况调整timeout

### 降级机制

如果本地模型加载失败，系统会自动降级到API提供者，确保服务可用。

## 🔍 调试

### 查看当前使用的提供者

```python
from src.llm import LLMClient

client = LLMClient()
print(f"Provider type: {type(client.provider).__name__}")
print(f"Model: {client.model}")
```

### 日志输出

系统会记录使用的提供者类型：

```
INFO: 使用API云上模型提供者
INFO: LLMClient initialized: provider=api, model=qwen3-max
```

或

```
INFO: 使用本地部署模型提供者
INFO: LocalModelProvider initialized: model_path=/path/to/model
```

## 📚 完整配置示例

### config.yaml (API模式)

```yaml
model:
  provider: "api"
  api_base: "https://newapi.3173721.xyz/v1/chat/completions"
  api_key: "sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz"
  model_name: "qwen3-max"
  temperature: 0.1
  max_tokens: 2000
  timeout: 60
```

### config.yaml (本地模式)

```yaml
model:
  provider: "local"
  model_path: "/home/user/models/qwen-7b-chat"
  device: "cuda"
  load_in_8bit: true  # 如果显存不足，启用8bit量化
  model_name: "qwen-7b-chat"
  temperature: 0.1
  max_tokens: 2000
  timeout: 60
```

## ✅ 优势

1. **代码解耦**: 业务代码不依赖具体的模型实现
2. **灵活切换**: 通过配置文件即可切换模型提供者
3. **统一接口**: 无论使用哪种提供者，调用方式完全一致
4. **易于扩展**: 可以轻松添加新的模型提供者（如vLLM、TGI等）

---

**文档版本**: 1.0.0  
**最后更新**: 2026-01-28
