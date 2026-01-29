@echo off
chcp 65001 >nul
echo ========================================
echo 快速安装核心依赖（无需编译）
echo ========================================
echo.

echo [步骤1] 安装基础Web框架...
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple uvicorn fastapi
if %errorlevel% neq 0 (
    echo ❌ 安装失败
    pause
    exit /b 1
)
echo ✓ 完成

echo.
echo [步骤2] 安装工具库...
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple loguru pyyaml requests
if %errorlevel% neq 0 (
    echo ❌ 安装失败
    pause
    exit /b 1
)
echo ✓ 完成

echo.
echo [步骤3] 尝试安装 pydantic（如果失败可跳过）...
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --only-binary :all: pydantic 2>nul
if %errorlevel% neq 0 (
    echo 警告：pydantic 预编译包不可用，尝试普通安装...
    python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pydantic
)
echo ✓ 完成（或已跳过）

echo.
echo [步骤4] 验证安装...
python -c "import uvicorn; import fastapi; print('✓ uvicorn 和 fastapi 安装成功')" 2>nul
python -c "import loguru; print('✓ loguru 安装成功')" 2>nul
python -c "import yaml; print('✓ pyyaml 安装成功')" 2>nul
python -c "import requests; print('✓ requests 安装成功')" 2>nul

echo.
echo ========================================
echo ✓ 核心依赖安装完成！
echo ========================================
echo.
echo 注意：
echo - aiohttp 和 pydantic-core 需要编译器，已跳过
echo - 服务可以使用 requests 作为替代（已支持）
echo - 现在可以运行: python run_server_fast.py
echo.
pause
