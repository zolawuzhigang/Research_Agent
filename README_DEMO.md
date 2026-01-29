# Research Agent Demo 使用指南

## 1. 环境准备

### 1.1 安装依赖

```bash
pip install -r requirements.txt
```

### 1.2 配置环境变量（可选）

```bash
# LLM配置
export LLM_API_BASE="https://newapi.3173721.xyz/v1/chat/completions"
export LLM_API_KEY="sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz"
export LLM_MODEL="qwen3-max"

# 搜索工具配置（可选）
export SERPAPI_KEY="your_serpapi_key"
```

## 2. 启动服务

### 2.1 启动HTTP服务

```bash
python run_server.py
```

服务将在 `http://0.0.0.0:8000` 启动

### 2.2 启动控制台交互

```bash
python run_console.py
```

## 3. 使用方式

### 3.1 HTTP API使用

#### 基本预测接口

```bash
curl -X POST \
     -H "Authorization: Bearer test_token" \
     -H "Content-Type: application/json" \
     -d '{"question": "法国首都在哪里？"}' \
     "http://localhost:8000/api/v1/predict"
```

响应：
```json
{
  "answer": "巴黎"
}
```

#### 流式接口

```bash
curl -X POST \
     -H "Authorization: Bearer test_token" \
     -H "Content-Type: application/json" \
     -H "Accept: text/event-stream" \
     -d '{"question": "法国首都在哪里？"}' \
     "http://localhost:8000/api/v1/predict/stream"
```

#### 详细结果接口

```bash
curl -X POST \
     -H "Authorization: Bearer test_token" \
     -H "Content-Type: application/json" \
     -d '{"question": "法国首都在哪里？"}' \
     "http://localhost:8000/api/v1/predict/detailed"
```

响应：
```json
{
  "answer": "巴黎",
  "confidence": 0.85,
  "reasoning": "问题: 法国首都在哪里？\n任务计划: 3 个步骤\n步骤 1: tool_search_web - ...",
  "success": true,
  "errors": []
}
```

### 3.2 控制台交互

运行 `python run_console.py` 后：

```
你: 法国首都在哪里？

Agent: 巴黎
[置信度: 0.85]

你: 计算 2 + 3 * 4

Agent: 14
[置信度: 0.90]
```

### 3.3 Python客户端

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

result = response.json()
print(f"答案: {result['answer']}")
```

## 4. 测试

### 4.1 运行测试脚本

```bash
python test_api.py
```

### 4.2 测试问题示例

- 简单问题: "法国首都在哪里？"
- 计算问题: "计算 2 + 3 * 4 的结果"
- 复杂问题: "请分析最近三年人工智能在医疗影像诊断方面的研究进展"

## 5. API端点说明

### 5.1 健康检查

```
GET /health
```

### 5.2 根路径

```
GET /
```

### 5.3 预测接口

```
POST /api/v1/predict
```

请求体：
```json
{
  "question": "用户问题"
}
```

响应：
```json
{
  "answer": "答案"
}
```

### 5.4 流式接口

```
POST /api/v1/predict/stream
```

返回SSE格式的流式响应

### 5.5 详细结果接口

```
POST /api/v1/predict/detailed
```

返回包含置信度、推理过程等详细信息

## 6. 配置说明

### 6.1 LLM配置

在代码中或环境变量中配置：

```python
from src.llm.llm_client import LLMClient

llm = LLMClient(
    api_base="https://newapi.3173721.xyz/v1/chat/completions",
    api_key="sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz",
    model="qwen3-max"
)
```

### 6.2 模型选择

支持的模型：
- `qwen3-max`
- `qwen3-max-preview`
- `qwen3-vl-plus`

## 7. 故障排查

### 7.1 服务无法启动

- 检查端口8000是否被占用
- 检查依赖是否安装完整
- 查看日志文件

### 7.2 LLM调用失败

- 检查API密钥是否正确
- 检查网络连接
- 查看错误日志

### 7.3 工具调用失败

- 检查工具配置（如SerpAPI密钥）
- 查看工具调用日志

## 8. 开发模式

启动时使用 `reload=True` 可以自动重载代码：

```python
uvicorn.run(
    "src.api.http_server:app",
    host="0.0.0.0",
    port=8000,
    reload=True
)
```

## 9. 生产部署

### 9.1 使用Gunicorn

```bash
gunicorn src.api.http_server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 9.2 使用Docker（可选）

```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "run_server.py"]
```

## 10. 性能优化

- 使用连接池管理HTTP请求
- 实现结果缓存
- 优化LLM调用（批处理、流式处理）
- 使用异步处理提高并发能力

---

**最后更新**: 2026-01-28
