# Research Agent Demo 运行指南

## 🚀 快速开始

### 第一步：环境准备

#### 1. 检查Python版本
```bash
python --version
# 需要 Python 3.8 或更高版本
```

#### 2. 创建虚拟环境（推荐）
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 第二步：安装依赖

```bash
# 进入项目目录
cd c:\Users\bigda\Desktop\ailiyunAgent

# 安装依赖
pip install -r requirements.txt
```

**主要依赖**：
- fastapi, uvicorn (HTTP服务)
- requests, aiohttp (HTTP客户端)
- loguru (日志)
- pyyaml (配置文件)
- pytest (测试，可选)

### 第三步：配置（可选）

LLM配置已内置在代码中，默认使用：
- API地址: `https://newapi.3173721.xyz/v1/chat/completions`
- API Key: `sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz`
- 模型: `qwen3-max`

如需修改，可以：
1. 编辑 `config/config.yaml`
2. 或设置环境变量：
   ```bash
   export LLM_API_BASE="your_api_base"
   export LLM_API_KEY="your_api_key"
   export LLM_MODEL="qwen3-max"
   ```

### 第四步：运行Demo

## 运行方式

### 方式1：HTTP服务模式（推荐）

#### 启动服务
```bash
python run_server.py
```

服务将在 `http://localhost:8000` 启动

#### 测试服务

**方法A：使用测试脚本**
```bash
python test_api.py
```

**方法B：使用curl**
```bash
curl -X POST \
     -H "Authorization: Bearer test_token" \
     -H "Content-Type: application/json" \
     -d '{"question": "法国首都在哪里？"}' \
     "http://localhost:8000/api/v1/predict"
```

**方法C：使用Python**
```python
import requests

url = "http://localhost:8000/api/v1/predict"
headers = {
    "Authorization": "Bearer test_token",
    "Content-Type": "application/json"
}

response = requests.post(
    url,
    headers=headers,
    json={"question": "法国首都在哪里？"}
)

print(response.json())
# 输出: {"answer": "巴黎"}
```

#### API接口说明

**基本预测接口**
```
POST /api/v1/predict
Content-Type: application/json

请求:
{
  "question": "用户问题"
}

响应:
{
  "answer": "答案"
}
```

**健康检查**
```bash
curl http://localhost:8000/health
```

**详细结果接口**
```bash
curl -X POST \
     -H "Authorization: Bearer test_token" \
     -H "Content-Type: application/json" \
     -d '{"question": "法国首都在哪里？"}' \
     "http://localhost:8000/api/v1/predict/detailed"
```

### 方式2：控制台交互模式

```bash
python run_console.py
```

运行后会进入交互式界面：
```
============================================================
Research Agent - 控制台交互模式
============================================================
输入 'quit' 或 'exit' 退出
输入 'clear' 清空对话历史
============================================================

你: 法国首都在哪里？

思考中...

Agent: 巴黎
[置信度: 0.85]

你: 
```

## 测试问题示例

### 简单问题
- "法国首都在哪里？"
- "什么是人工智能？"
- "计算 2 + 3 * 4 的结果"

### 复杂问题
- "请分析最近三年人工智能在医疗影像诊断方面的研究进展"
- "比较BERT和GPT-4在文本分类任务上的效果差异"

## 常见问题排查

### 1. 服务无法启动

**问题**: `ModuleNotFoundError` 或导入错误

**解决**:
```bash
# 确保在项目根目录
cd c:\Users\bigda\Desktop\ailiyunAgent

# 检查依赖是否安装
pip list | grep fastapi

# 重新安装依赖
pip install -r requirements.txt
```

### 2. 端口被占用

**问题**: `Address already in use`

**解决**:
```bash
# Windows: 查找占用8000端口的进程
netstat -ano | findstr :8000

# 修改端口（编辑 run_server.py）
uvicorn.run(..., port=8001)
```

### 3. LLM调用失败

**问题**: `LLM API调用失败`

**检查**:
1. 网络连接是否正常
2. API地址是否正确
3. API密钥是否有效

**解决**:
```bash
# 测试API连接
curl https://newapi.3173721.xyz/v1/chat/completions \
     -H "Authorization: Bearer sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz" \
     -H "Content-Type: application/json" \
     -d '{"model":"qwen3-max","messages":[{"role":"user","content":"test"}]}'
```

### 4. 搜索工具不可用

**问题**: 搜索返回模拟结果

**说明**: 如果未设置 `SERPAPI_KEY`，搜索工具会使用模拟结果，这是正常的。

**解决**（可选）:
```bash
# 设置SerpAPI密钥（如果需要真实搜索）
export SERPAPI_KEY="your_serpapi_key"
```

## 运行测试

### 运行单元测试
```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_normalize.py -v
pytest tests/test_validators.py -v
pytest tests/test_tools.py -v
```

## 开发模式

### 启用自动重载
`run_server.py` 已默认启用 `reload=True`，修改代码后会自动重载。

### 查看日志
日志会输出到控制台，也可以配置输出到文件（在 `config/config.yaml` 中配置）。

## 生产部署

### 使用Gunicorn（推荐）
```bash
pip install gunicorn

gunicorn src.api.http_server:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000
```

### 使用Docker（可选）
```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "run_server.py"]
```

## 完整运行示例

### 示例1：启动HTTP服务并测试

```bash
# 终端1：启动服务
python run_server.py

# 终端2：测试服务
python test_api.py
```

### 示例2：控制台交互

```bash
python run_console.py

# 然后输入问题
你: 法国首都在哪里？
Agent: 巴黎

你: 计算 2 + 3 * 4
Agent: 14
```

### 示例3：Python代码调用

```python
import asyncio
from src.agent import AgentOrchestrator

async def main():
    agent = AgentOrchestrator(use_multi_agent=True)
    result = await agent.process_task("法国首都在哪里？")
    print(f"答案: {result['answer']}")

asyncio.run(main())
```

## 性能优化建议

1. **使用异步客户端**: 已默认启用aiohttp（如果可用）
2. **调整超时**: 在 `config/config.yaml` 中调整超时时间
3. **并发控制**: HTTP服务支持并发请求

## 下一步

- 查看 `README_DEMO.md` 了解详细功能
- 查看 `TECHNICAL_DESIGN.md` 了解技术架构
- 查看 `docs/USAGE_EXAMPLES.md` 查看更多示例

---

**快速命令总结**:
```bash
# 安装依赖
pip install -r requirements.txt

# 启动HTTP服务
python run_server.py

# 启动控制台
python run_console.py

# 测试API
python test_api.py

# 运行测试
pytest tests/ -v
```
