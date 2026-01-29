"""
HTTP服务 - 快速启动版本（延迟初始化Agent）
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.normalize import normalize_answer
from src.utils.validators import validate_question
from src.utils.metrics import get_metrics
from datetime import datetime

# 请求模型
class QuestionRequest(BaseModel):
    question: str

# 响应模型
class AnswerResponse(BaseModel):
    answer: str

# 创建FastAPI应用
app = FastAPI(
    title="Research Agent API",
    description="Research Agent - 能够自主规划、调用工具、整合证据的智能体",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局Agent实例（延迟初始化）
agent: Optional[Any] = None
_agent_initializing = False


async def _ensure_agent_initialized():
    """确保Agent已初始化（延迟初始化）"""
    global agent, _agent_initializing
    
    if agent is not None:
        return True
    
    if _agent_initializing:
        # 如果正在初始化，等待
        for _ in range(30):  # 最多等待30秒
            await asyncio.sleep(1)
            if agent is not None:
                return True
        return False
    
    _agent_initializing = True
    try:
        logger.info("延迟初始化Agent...")
        from src.agent import AgentOrchestrator
        from src.config.config_loader import get_config
        
        # 快速加载配置
        try:
            config = get_config().config
        except Exception as e:
            logger.warning(f"配置加载失败，使用默认配置: {e}")
            config = {}
        
        # 在线程池中初始化（避免阻塞）
        loop = asyncio.get_event_loop()
        agent = await loop.run_in_executor(
            None,
            lambda: AgentOrchestrator(config=config, use_multi_agent=True)
        )
        logger.info("Agent初始化完成")
        return True
    except Exception as e:
        logger.exception(f"Agent初始化失败: {e}")
        return False
    finally:
        _agent_initializing = False


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Research Agent API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查 - 增强版，包含详细指标"""
    from src.utils.metrics import get_metrics
    
    try:
        # 检查Agent是否已初始化
        agent_status = "initialized" if agent is not None else "not_initialized"
        
        # 获取指标
        metrics = get_metrics()
        summary = metrics.get_summary()
        
        return {
            "status": "healthy",
            "agent_status": agent_status,
            "agent_initializing": _agent_initializing,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "uptime": summary["uptime_formatted"],
                "requests": {
                    "total": summary["request_count"],
                    "success": summary["success_count"],
                    "failure": summary["failure_count"],
                    "success_rate": summary["success_rate"]
                },
                "error_summary": {
                    "total_errors": summary["errors"]["total_errors"],
                    "top_errors": [
                        {"type": error_type, "count": metric.count}
                        for error_type, metric in summary["errors"]["top_errors"]
                    ]
                },
                "performance_summary": {
                    op: {
                        "count": stats["total_count"],
                        "avg_time": f"{stats['avg_time']:.3f}s",
                        "recent_avg": f"{stats['recent_avg_time']:.3f}s"
                    }
                    for op, stats in summary["performance"].items()
                }
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/v1/predict", response_model=AnswerResponse)
async def predict(
    request: QuestionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    处理问题并返回答案
    """
    # 延迟初始化Agent
    if not await _ensure_agent_initialized():
        raise HTTPException(status_code=503, detail="Agent初始化失败，请稍后重试")
    
    try:
        # 验证输入
        try:
            question = validate_question(request.question, max_length=5000)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        logger.info(f"收到问题: {question[:100]}...")
        
        # 记录请求开始
        metrics = get_metrics()
        start_time = time.time()
        
        # 处理问题（添加超时控制）
        try:
            result = await asyncio.wait_for(
                agent.process_task(question),
                timeout=300.0  # 5分钟超时
            )
            
            # 记录成功
            duration = time.time() - start_time
            metrics.record_request(success=True)
            metrics.record_performance("request_processing", duration)
            
        except asyncio.TimeoutError:
            logger.error("处理问题超时")
            duration = time.time() - start_time
            metrics.record_request(success=False)
            metrics.record_error("TimeoutError", "请求处理超时")
            metrics.record_performance("request_processing", duration)
            raise HTTPException(status_code=504, detail="处理超时，请稍后重试")
        
        if not result:
            logger.error("处理结果为空")
            metrics.record_error("EmptyResult", "处理结果为空")
            answer = "抱歉，处理过程中出现错误。"
        elif not result.get("success"):
            error_msg = result.get("error", "处理失败")
            logger.error(f"处理失败: {error_msg}")
            metrics.record_error("ProcessingFailed", error_msg)
            answer = "抱歉，我无法回答这个问题。"
        else:
            raw_answer = result.get("answer", "")
            if not raw_answer:
                logger.warning("生成的答案为空")
                answer = "抱歉，我无法生成答案。"
            else:
                answer = normalize_answer(raw_answer)
                if not answer:
                    logger.warning("归一化后的答案为空")
                    answer = "抱歉，我无法生成有效答案。"
                else:
                    logger.info(f"生成答案: {answer[:100]}...")
        
        return AnswerResponse(answer=answer)
    
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"输入验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"处理请求时出错: {e}")
        raise HTTPException(status_code=500, detail="处理失败，请稍后重试")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("启动Research Agent HTTP服务（快速启动模式）...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
