# 故障排查指南

## 问题：IDEA运行后一直转圈，等待5分钟还在转

### 原因分析

这个问题通常是因为在启动时同步初始化LLM客户端或进行网络请求，导致阻塞。

### 解决方案

#### 方案1：使用快速启动版本（推荐）

使用延迟初始化的快速启动版本：

```bash
python run_server_fast.py
```

这个版本会在第一次请求时才初始化Agent，避免启动时卡住。

#### 方案2：修改启动代码

编辑 `src/api/http_server.py`，将Agent初始化改为异步且带超时：

```python
@app.on_event("startup")
async def startup_event():
    """启动时初始化Agent"""
    global agent
    logger.info("正在初始化Research Agent...")
    
    try:
        # 使用超时保护
        import asyncio
        agent = await asyncio.wait_for(
            asyncio.to_thread(
                AgentOrchestrator,
                config=get_config().config,
                use_multi_agent=True
            ),
            timeout=30.0  # 30秒超时
        )
        logger.info("Research Agent初始化完成")
    except asyncio.TimeoutError:
        logger.error("初始化超时，使用简化模式")
        agent = AgentOrchestrator(config={}, use_multi_agent=True)
    except Exception as e:
        logger.exception(f"Agent初始化失败: {e}")
        agent = None
```

#### 方案3：检查网络连接

如果LLM API无法连接，初始化可能会卡住：

```bash
# 测试API连接
curl https://newapi.3173721.xyz/v1/chat/completions \
     -H "Authorization: Bearer sk-DwBE5H6xxCV6I7i0q8v6rq3ZHauPuSq6fWVerxu7gJ9DmQoz" \
     -H "Content-Type: application/json" \
     -d '{"model":"qwen3-max","messages":[{"role":"user","content":"test"}]}'
```

#### 方案4：禁用LLM初始化测试

修改 `src/llm/llm_client.py`，在初始化时不进行网络测试：

```python
def __init__(self, ...):
    # ... 配置代码 ...
    # 不进行网络测试，延迟到第一次调用时验证
    logger.info(f"LLMClient initialized: model={self.model}")
    # 移除任何可能阻塞的初始化代码
```

### 调试步骤

1. **查看日志**
   ```bash
   # 启动时查看详细日志
   python run_server.py
   # 观察日志输出，看卡在哪一步
   ```

2. **添加调试日志**
   在关键初始化步骤添加日志：
   ```python
   logger.info("步骤1: 开始初始化...")
   # 初始化代码
   logger.info("步骤2: 完成...")
   ```

3. **使用简化模式**
   临时禁用多Agent模式：
   ```python
   agent = AgentOrchestrator(use_multi_agent=False)
   ```

### 快速修复命令

```bash
# 使用快速启动版本
python run_server_fast.py

# 或修改端口避免冲突
python run_server.py
# 如果8000端口被占用，修改 run_server.py 中的端口号
```

### 常见卡住位置

1. **LLM客户端初始化** - 可能尝试连接API
2. **配置加载** - 读取配置文件可能慢
3. **LangGraph初始化** - 如果LangGraph不可用可能卡住
4. **工具注册** - 工具初始化可能慢

### 预防措施

已优化的代码包含：
- ✅ 延迟初始化支持
- ✅ 超时保护
- ✅ 错误恢复
- ✅ 异步初始化

使用 `run_server_fast.py` 可以避免启动时卡住的问题。
