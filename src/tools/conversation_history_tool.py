"""
对话历史工具 - 允许Agent访问对话历史
"""

from typing import Dict, Any, Optional
from loguru import logger
from .tool_registry import BaseTool


class ConversationHistoryTool(BaseTool):
    """对话历史工具 - 检索对话历史"""
    
    def __init__(self, memory_manager=None):
        """
        初始化对话历史工具
        
        Args:
            memory_manager: MemoryManager实例，用于访问对话历史
        """
        super().__init__(
            name="get_conversation_history",
            description="获取对话历史，可以查看之前的用户问题和助手回答"
        )
        self.memory_manager = memory_manager
    
    async def execute(self, query: str) -> Dict[str, Any]:
        """
        执行对话历史查询
        
        Args:
            query: 查询字符串，可以是：
                - "last" 或 "最近" - 获取最后一条消息
                - "last_n" 或数字 - 获取最后N条消息
                - "all" 或 "全部" - 获取所有历史
                - "user" 或 "用户" - 获取所有用户消息
                - "assistant" 或 "助手" - 获取所有助手消息
                - 特殊标记：如果查询包含时间语义词（"刚刚"、"之前"、"刚才"等），自动使用快照
        
        Returns:
            对话历史结果
        """
        logger.info(f"ConversationHistoryTool: 处理查询 - {query}")
        
        if not self.memory_manager:
            logger.warning("MemoryManager未设置，无法获取对话历史")
            return {
                "success": False,
                "error": "MemoryManager未设置",
                "query": query
            }
        
        try:
            query_lower = query.lower().strip()
            
            # 检测时间语义：如果查询涉及"之前"、"刚刚"、"刚才"等，使用快照（处理前历史）
            time_semantic_keywords = ["刚刚", "刚才", "之前", "之前的问题", "之前的问题", "上一个", "上一条", 
                                     "last", "previous", "before", "earlier", "刚才的", "刚刚的"]
            use_snapshot = any(keyword in query_lower for keyword in time_semantic_keywords)
            
            if use_snapshot:
                logger.debug(f"检测到时间语义关键词，使用历史快照（处理前历史）")
            
            # 获取对话历史（根据时间语义决定是否使用快照）
            if query_lower in ["last", "最近", "上一条", "last message"]:
                # 获取最后一条消息
                history = self.memory_manager.get_conversation_context(n=1, use_snapshot=use_snapshot)
                if history:
                    last_msg = history[-1]
                    return {
                        "success": True,
                        "message": last_msg,
                        "role": last_msg.get("role"),
                        "content": last_msg.get("content"),
                        "timestamp": last_msg.get("timestamp"),
                        "formatted": f"[{last_msg.get('role', 'unknown')}]: {last_msg.get('content', '')}"
                    }
                else:
                    return {
                        "success": True,
                        "message": None,
                        "formatted": "对话历史为空"
                    }
            
            elif query_lower in ["last_user", "最后用户", "上一条用户消息"]:
                # 获取最后一条用户消息
                history = self.memory_manager.get_conversation_context(n=20, use_snapshot=use_snapshot)
                user_messages = [msg for msg in history if msg.get("role") == "user"]
                
                if user_messages:
                    last_user_msg = user_messages[-1]
                    return {
                        "success": True,
                        "message": last_user_msg,
                        "role": "user",
                        "content": last_user_msg.get("content"),
                        "timestamp": last_user_msg.get("timestamp"),
                        "formatted": f"用户问题: {last_user_msg.get('content', '')}"
                    }
                else:
                    return {
                        "success": True,
                        "message": None,
                        "formatted": "未找到用户消息"
                    }
            
            elif query_lower in ["all", "全部", "所有"]:
                # 获取所有历史
                history = self.memory_manager.get_conversation_context(n=100, use_snapshot=use_snapshot)
                formatted_messages = []
                for msg in history:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    formatted_messages.append(f"[{role}]: {content}")
                
                return {
                    "success": True,
                    "messages": history,
                    "count": len(history),
                    "formatted": "\n".join(formatted_messages) if formatted_messages else "对话历史为空"
                }
            
            elif query_lower.startswith("last_") or query_lower.isdigit():
                # 获取最后N条消息
                try:
                    if query_lower.startswith("last_"):
                        n = int(query_lower.split("_")[1])
                    else:
                        n = int(query_lower)
                    
                    history = self.memory_manager.get_conversation_context(n=n, use_snapshot=use_snapshot)
                    formatted_messages = []
                    for msg in history:
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        formatted_messages.append(f"[{role}]: {content}")
                    
                    return {
                        "success": True,
                        "messages": history,
                        "count": len(history),
                        "formatted": "\n".join(formatted_messages) if formatted_messages else "对话历史为空"
                    }
                except ValueError:
                    # 如果解析失败，返回所有历史
                    history = self.memory_manager.get_conversation_context(n=10, use_snapshot=use_snapshot)
                    formatted_messages = []
                    for msg in history:
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        formatted_messages.append(f"[{role}]: {content}")
                    
                    return {
                        "success": True,
                        "messages": history,
                        "count": len(history),
                        "formatted": "\n".join(formatted_messages) if formatted_messages else "对话历史为空"
                    }
            
            else:
                # 默认返回最近10条消息
                history = self.memory_manager.get_conversation_context(n=10, use_snapshot=use_snapshot)
                formatted_messages = []
                for msg in history:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    formatted_messages.append(f"[{role}]: {content}")
                
                return {
                    "success": True,
                    "messages": history,
                    "count": len(history),
                    "formatted": "\n".join(formatted_messages) if formatted_messages else "对话历史为空"
                }
        
        except Exception as e:
            logger.error(f"对话历史工具执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
