# 启动时间说明

## 📊 正常启动时间预期

### 标准启动模式 (`run_server.py`)

**预期时间：3-10秒**

启动流程包括：

1. **加载配置** (`config.yaml`)
   - 时间：< 1秒
   - 操作：读取YAML文件，解析配置

2. **初始化AgentOrchestrator**
   - 时间：2-8秒
   - 包括：
     - MemoryManager初始化：< 0.1秒
     - MultiAgentSystem初始化：1-5秒
       - LLMClient初始化：< 1秒（不进行网络测试）
       - 4个Agent初始化：< 1秒
     - ToolRegistry初始化：< 0.5秒
     - LangGraphWorkflow初始化：1-3秒（如果LangGraph已安装）

3. **FastAPI服务启动**
   - 时间：< 1秒

**总计：3-10秒**

### 快速启动模式 (`run_server_fast.py`)

**预期时间：< 2秒**

- 只启动FastAPI服务
- Agent在第一次请求时才初始化
- 首次请求会额外花费3-10秒初始化Agent

## ⚠️ 如果启动超过30秒

如果启动超过30秒，说明有问题：

### 可能的原因

1. **网络问题**
   - LLM API无法连接（虽然已优化不测试，但某些情况下仍可能尝试连接）
   - 解决方案：检查网络，或使用快速启动模式

2. **LangGraph安装问题**
   - LangGraph未安装或版本不兼容
   - 解决方案：检查 `pip list | grep langgraph`

3. **配置文件问题**
   - 配置文件格式错误或路径问题
   - 解决方案：检查 `config/config.yaml`

4. **依赖缺失**
   - 某些Python包未安装
   - 解决方案：运行 `pip install -r requirements.txt`

### 诊断方法

查看日志输出，观察卡在哪一步：

```
步骤1/3: 加载配置...          # 应该 < 1秒
步骤2/3: 配置加载完成          # 应该立即
步骤3/3: 初始化Agent...        # 应该 2-8秒
✅ Research Agent初始化完成    # 完成标志
```

如果卡在某个步骤超过10秒，说明该步骤有问题。

## 🚀 优化建议

### 如果启动太慢

1. **使用快速启动模式**
   ```bash
   python run_server_fast.py
   ```
   启动时间：< 2秒

2. **检查LangGraph**
   ```bash
   # 如果不需要LangGraph，可以禁用
   # 修改 src/agent/orchestrator.py，设置 use_multi_agent=False
   ```

3. **简化配置**
   - 使用空配置启动：`AgentOrchestrator(config={})`
   - 启动时间会减少到 1-3秒

## 📈 性能对比

| 启动模式 | 启动时间 | Agent初始化 | 首次请求时间 |
|---------|---------|------------|------------|
| 标准模式 | 3-10秒 | 启动时 | 正常（已就绪） |
| 快速模式 | < 2秒 | 首次请求时 | 首次请求：3-10秒<br>后续请求：正常 |

## ✅ 正常启动的标志

看到以下日志表示启动成功：

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     步骤1/3: 加载配置...
INFO:     步骤2/3: 配置加载完成
INFO:     步骤3/3: 初始化Agent（最多等待30秒）...
INFO:     ✅ Research Agent初始化完成
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**如果看到最后一行，说明启动成功，可以开始使用了！**

## 🔧 如果启动失败

1. **查看完整错误日志**
   - 日志会显示具体错误信息

2. **使用快速启动模式**
   ```bash
   python run_server_fast.py
   ```

3. **检查依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **检查Python版本**
   ```bash
   python --version  # 需要 Python 3.8+
   ```
