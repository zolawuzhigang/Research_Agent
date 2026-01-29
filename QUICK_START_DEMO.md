# Research Agent Demo 快速开始

## 🚀 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动HTTP服务

```bash
python run_server.py
```

服务将在 `http://localhost:8000` 启动

### 3. 测试服务

#### 方式1: 使用测试脚本

```bash
python test_api.py
```

#### 方式2: 使用curl

```bash
curl -X POST \
     -H "Authorization: Bearer test_token" \
     -H "Content-Type: application/json" \
     -d '{"question": "法国首都在哪里？"}' \
     "http://localhost:8000/api/v1/predict"
```

#### 方式3: 使用控制台交互

```bash
python run_console.py
```

## 📋 API接口说明

### 基本预测接口

**端点**: `POST /api/v1/predict`

**请求**:
```json
{
  "question": "法国首都在哪里？"
}
```

**响应**:
```json
{
  "answer": "巴黎"
}
```

### 流式接口

**端点**: `POST /api/v1/predict/stream`

返回SSE格式的流式响应

### 详细结果接口

**端点**: `POST /api/v1/predict/detailed`

返回包含置信度、推理过程等详细信息

## 🔧 配置

LLM配置已内置在代码中：
- API地址: `https://newapi.3173721.xyz/v1/chat/completions`
- API Key: `sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz`
- 模型: `qwen3-max`

如需修改，编辑 `src/llm/llm_client.py` 或设置环境变量。

## 📝 测试问题示例

1. **简单问题**: "法国首都在哪里？"
2. **计算问题**: "计算 2 + 3 * 4 的结果"
3. **复杂问题**: "请分析最近三年人工智能在医疗影像诊断方面的研究进展"

## 🐛 故障排查

- **服务无法启动**: 检查端口8000是否被占用
- **LLM调用失败**: 检查网络连接和API配置
- **导入错误**: 确保在项目根目录运行

## 📚 更多信息

查看 `README_DEMO.md` 获取详细文档。
