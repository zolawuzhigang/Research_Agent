# 依赖安装指南

## 🚨 问题：ModuleNotFoundError: No module named 'uvicorn'

这是因为缺少必要的 Python 依赖包。

## ✅ 快速安装（推荐）

### 方法1：使用批处理脚本（Windows）

```bash
# 双击运行或在PowerShell中执行
install_deps.bat
```

### 方法2：手动安装（分步安装）

#### 步骤1：安装核心Web框架（必需）

```bash
python -m pip install uvicorn[standard] fastapi pydantic
```

#### 步骤2：安装工具库（必需）

```bash
python -m pip install loguru pyyaml requests aiohttp
```

#### 步骤3：安装可选依赖（可选，用于完整功能）

```bash
# 如果网络慢，可以跳过这一步
python -m pip install langchain langgraph dashscope
```

### 方法3：使用国内镜像（如果网络慢）

```bash
# 使用清华镜像
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple uvicorn[standard] fastapi pydantic loguru pyyaml requests aiohttp

# 或使用阿里云镜像
python -m pip install -i https://mirrors.aliyun.com/pypi/simple/ uvicorn[standard] fastapi pydantic loguru pyyaml requests aiohttp
```

## 📦 最小依赖列表（仅运行服务）

如果完整安装失败，至少需要这些包：

```bash
python -m pip install uvicorn fastapi pydantic loguru pyyaml requests
```

## ⚠️ 常见问题

### 1. numpy 安装失败

如果看到 numpy 编译错误，可以：
- 跳过 numpy（如果不需要数据处理功能）
- 或安装预编译版本：`pip install numpy --only-binary :all:`

### 2. 网络超时

使用国内镜像：
```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <包名>
```

### 3. 权限错误

使用 `--user` 参数：
```bash
python -m pip install --user uvicorn fastapi
```

## ✅ 验证安装

安装完成后，验证是否成功：

```bash
python -c "import uvicorn; import fastapi; print('✓ 核心依赖安装成功')"
```

## 🚀 安装完成后

运行服务：

```bash
python run_server_fast.py
```

应该看到：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 📝 完整依赖列表

如果需要完整功能，安装所有依赖：

```bash
python -m pip install -r requirements.txt
```

如果某些包安装失败（如 numpy），可以跳过，核心服务仍可运行。
