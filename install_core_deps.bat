@echo off
echo ========================================
echo 安装核心依赖（使用预编译包）
echo ========================================
echo.

echo [1/4] 安装基础包（无需编译）...
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple uvicorn fastapi loguru pyyaml requests
if %errorlevel% neq 0 (
    echo 安装失败
    pause
    exit /b 1
)

echo.
echo [2/4] 安装 pydantic（使用预编译wheel）...
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --only-binary :all: pydantic
if %errorlevel% neq 0 (
    echo 警告：pydantic 安装失败，尝试普通安装...
    python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pydantic
)

echo.
echo [3/4] 安装 aiohttp（使用预编译wheel）...
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --only-binary :all: aiohttp
if %errorlevel% neq 0 (
    echo 警告：aiohttp 安装失败，将使用 requests 作为替代
    echo 注意：某些异步功能可能不可用
)

echo.
echo [4/4] 验证安装...
python -c "import uvicorn; import fastapi; import pydantic; import loguru; print('✓ 核心依赖安装成功！')" 2>nul
if %errorlevel% neq 0 (
    echo 验证失败，但可能部分包已安装
) else (
    echo.
    echo ========================================
    echo ✓ 安装完成！现在可以运行服务了
    echo ========================================
    echo.
    echo 运行命令: python run_server_fast.py
)

pause
