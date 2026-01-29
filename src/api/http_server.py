"""
HTTP服务 - Research Agent API服务
"""

import asyncio
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agent import AgentOrchestrator
from src.utils.normalize import normalize_answer
from src.utils.validators import validate_question


# 请求模型
class QuestionRequest(BaseModel):
    question: str
    
    class Config:
        # 验证配置
        min_length = 1
        max_length = 5000  # 限制问题长度
    
    @classmethod
    def validate_question(cls, v: str) -> str:
        """验证问题"""
        if not v or not v.strip():
            raise ValueError("问题不能为空")
        if len(v) > 5000:
            raise ValueError("问题长度不能超过5000字符")
        return v.strip()


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

# 全局Agent实例
agent: Optional[AgentOrchestrator] = None


@app.on_event("startup")
async def startup_event():
    """启动时初始化Agent（带超时保护）"""
    global agent
    logger.info("正在初始化Research Agent...")
    
    try:
        # 从配置加载
        logger.info("步骤1/3: 加载配置...")
        from src.config.config_loader import get_config
        config = get_config().config
        logger.info("步骤2/3: 配置加载完成")
        
        # 使用超时保护，避免初始化卡死
        import asyncio
        logger.info("步骤3/3: 初始化Agent（最多等待30秒）...")
        try:
            # 在线程池中初始化，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            agent = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: AgentOrchestrator(config=config, use_multi_agent=True)
                ),
                timeout=30.0  # 30秒超时
            )
            logger.info("✅ Research Agent初始化完成")
        except asyncio.TimeoutError:
            logger.error("❌ Agent初始化超时（超过30秒）")
            logger.warning("使用简化配置重试...")
            # 使用简化配置重试（不加载配置）
            try:
                agent = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: AgentOrchestrator(config={}, use_multi_agent=True)
                    ),
                    timeout=10.0
                )
                logger.warning("✅ 使用简化配置初始化成功")
            except Exception as e2:
                logger.error(f"简化配置初始化也失败: {e2}")
                agent = None
    except Exception as e:
        logger.exception(f"Agent初始化失败: {e}")
        # 不抛出异常，允许服务启动但返回503
        agent = None
        logger.warning("⚠️ Agent未初始化，服务将以降级模式运行（首次请求时会重试）")


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
    """健康检查"""
    return {
        "status": "healthy",
        "agent_ready": agent is not None
    }


@app.post("/api/v1/predict", response_model=AnswerResponse)
async def predict(
    request: QuestionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    处理问题并返回答案
    
    请求格式:
    {
        "question": "用户问题"
    }
    
    响应格式:
    {
        "answer": "答案"
    }
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    try:
        # 验证输入
        try:
            question = validate_question(request.question, max_length=5000)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        logger.info(f"收到问题: {question[:100]}...")  # 只记录前100字符
        
        # 处理问题（添加超时控制）
        try:
            result = await asyncio.wait_for(
                agent.process_task(question),
                timeout=300.0  # 5分钟超时
            )
        except asyncio.TimeoutError:
            logger.error("处理问题超时")
            raise HTTPException(status_code=504, detail="处理超时，请稍后重试")
        
        if not result:
            logger.error("处理结果为空")
            answer = "抱歉，处理过程中出现错误。"
        elif not result.get("success"):
            error_msg = result.get("error", "处理失败")
            logger.error(f"处理失败: {error_msg}")
            # 即使失败也返回一个答案
            answer = "抱歉，我无法回答这个问题。"
        else:
            # 获取答案
            raw_answer = result.get("answer", "")
            
            if not raw_answer:
                logger.warning("生成的答案为空")
                answer = "抱歉，我无法生成答案。"
            else:
                # 归一化答案
                answer = normalize_answer(raw_answer)
                
                if not answer:
                    logger.warning("归一化后的答案为空")
                    answer = "抱歉，我无法生成有效答案。"
                else:
                    logger.info(f"生成答案: {answer[:100]}...")  # 只记录前100字符
                    logger.info(f"置信度: {result.get('confidence', 0.0):.2f}")
        
        # 返回JSON格式
        return AnswerResponse(answer=answer)
    
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except ValueError as e:
        logger.error(f"输入验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"处理请求时出错: {e}")  # 使用exception记录完整堆栈
        raise HTTPException(status_code=500, detail="处理失败，请稍后重试")


@app.post("/api/v1/predict/stream")
async def predict_stream(
    request: QuestionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    流式返回答案（SSE格式）
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    async def generate_stream():
        try:
            logger.info(f"收到流式请求: {request.question}")
            
            # 处理问题
            result = await agent.process_task(request.question)
            
            if result.get("success"):
                raw_answer = result.get("answer", "")
                answer = normalize_answer(raw_answer)
                
                # 流式返回（简单实现：分块返回）
                chunk_size = 10
                for i in range(0, len(answer), chunk_size):
                    chunk = answer[i:i+chunk_size]
                    yield f"data: {json.dumps({'answer': chunk})}\n\n"
                    await asyncio.sleep(0.1)
                
                # 发送最终完整答案
                yield f"data: {json.dumps({'answer': answer})}\n\n"
            else:
                error_msg = result.get("error", "处理失败")
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
        
        except Exception as e:
            logger.error(f"流式处理失败: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.post("/api/v1/predict/detailed")
async def predict_detailed(
    request: QuestionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    返回详细结果（包含推理过程、置信度等）
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    
    try:
        logger.info(f"收到详细请求: {request.question}")
        
        result = await agent.process_task(request.question)
        
        raw_answer = result.get("answer", "")
        answer = normalize_answer(raw_answer)
        
        return {
            "answer": answer,
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "success": result.get("success", False),
            "errors": result.get("errors", [])
        }
    
    except Exception as e:
        logger.error(f"处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("启动Research Agent HTTP服务...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
