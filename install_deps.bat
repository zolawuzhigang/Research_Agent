@echo off
echo ========================================
echo 安装 Research Agent 依赖包
echo ========================================
echo.

echo [1/3] 安装核心Web框架...
python -m pip install uvicorn[standard] fastapi pydantic
if %errorlevel% neq 0 (
    echo 安装失败，请检查网络连接
    pause
    exit /b 1
)

echo.
echo [2/3] 安装工具库...
python -m pip install loguru pyyaml requests aiohttp
if %errorlevel% neq 0 (
    echo 安装失败，请检查网络连接
    pause
    exit /b 1
)

echo.
echo [3/3] 安装可选依赖（如果失败可以忽略）...
python -m pip install langchain langgraph dashscope
if %errorlevel% neq 0 (
    echo 警告：可选依赖安装失败，但核心功能仍可使用
)

echo.
echo ========================================
echo 安装完成！
echo ========================================
echo.
echo 现在可以运行: python run_server_fast.py
pause
