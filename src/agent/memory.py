"""
记忆管理模块 - 短期记忆和长期记忆
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import deque
from loguru import logger


class ShortTermMemory:
    """
    短期记忆 - 管理对话历史和上下文
    """
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.conversation_history: deque = deque(maxlen=max_size)
        self.current_context: Dict[str, Any] = {}
        # 历史快照：用于在处理任务时提供"处理前"的历史视图
        self._history_snapshot: Optional[List[Dict[str, Any]]] = None
        logger.info(f"ShortTermMemory initialized (max_size={max_size})")
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """添加消息到对话历史"""
        message = {
            "role": role,  # "user", "assistant", "system"
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.conversation_history.append(message)
        logger.debug(f"添加消息: {role} - {content[:50]}...")
    
    def create_snapshot(self):
        """
        创建历史快照 - 用于在处理任务时提供"处理前"的历史视图
        
        当开始处理新任务时，创建快照，这样工具可以访问"处理当前任务之前"的历史
        """
        self._history_snapshot = list(self.conversation_history)
        logger.debug(f"创建历史快照，包含 {len(self._history_snapshot)} 条消息")
    
    def clear_snapshot(self):
        """清除历史快照"""
        self._history_snapshot = None
        logger.debug("清除历史快照")
    
    def get_snapshot(self) -> Optional[List[Dict[str, Any]]]:
        """获取历史快照（处理当前任务之前的历史）"""
        return self._history_snapshot
    
    def get_recent_history(self, n: int = 10, use_snapshot: bool = False) -> List[Dict[str, Any]]:
        """
        获取最近的对话历史
        
        Args:
            n: 获取最近N条消息
            use_snapshot: 如果为True，使用快照（处理前历史），否则使用当前历史
        """
        if use_snapshot and self._history_snapshot is not None:
            history = self._history_snapshot
        else:
            history = list(self.conversation_history)
        
        return history[-n:] if len(history) > n else history
    
    def get_full_history(self, use_snapshot: bool = False) -> List[Dict[str, Any]]:
        """
        获取完整对话历史
        
        Args:
            use_snapshot: 如果为True，使用快照（处理前历史），否则使用当前历史
        """
        if use_snapshot and self._history_snapshot is not None:
            return list(self._history_snapshot)
        return list(self.conversation_history)
    
    def update_context(self, key: str, value: Any):
        """更新当前上下文"""
        self.current_context[key] = value
    
    def get_context(self, key: str = None) -> Any:
        """获取上下文"""
        if key:
            return self.current_context.get(key)
        return self.current_context
    
    def clear_context(self):
        """清空上下文"""
        self.current_context = {}
    
    def summarize(self) -> str:
        """生成对话摘要（用于长对话压缩）"""
        if not self.conversation_history:
            return ""
        
        # 简单的摘要逻辑（实际应该使用LLM）
        summary = f"对话包含 {len(self.conversation_history)} 条消息\n"
        summary += f"最近消息: {self.conversation_history[-1].get('content', '')[:100]}"
        return summary


class LongTermMemory:
    """
    长期记忆 - 存储知识、经验和模式
    """
    
    def __init__(self):
        self.knowledge_base: Dict[str, Any] = {}
        self.patterns: List[Dict[str, Any]] = []
        self.experiences: List[Dict[str, Any]] = []
        logger.info("LongTermMemory initialized")
    
    def store_knowledge(self, key: str, value: Any, metadata: Dict[str, Any] = None):
        """存储知识"""
        self.knowledge_base[key] = {
            "value": value,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        logger.debug(f"存储知识: {key}")
    
    def retrieve_knowledge(self, key: str) -> Optional[Any]:
        """检索知识"""
        if key in self.knowledge_base:
            return self.knowledge_base[key]["value"]
        return None
    
    def store_pattern(self, pattern: Dict[str, Any]):
        """存储模式（如常见问题模式、解决方案模式）"""
        pattern["timestamp"] = datetime.now().isoformat()
        self.patterns.append(pattern)
        logger.debug(f"存储模式: {pattern.get('name', 'unknown')}")
    
    def find_similar_patterns(self, query: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """查找相似模式"""
        # TODO: 实现相似度匹配（可以使用向量相似度）
        return self.patterns[:top_k]
    
    def store_experience(self, experience: Dict[str, Any]):
        """存储经验（成功/失败的案例）"""
        experience["timestamp"] = datetime.now().isoformat()
        self.experiences.append(experience)
        logger.debug("存储经验")
    
    def get_relevant_experiences(self, context: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """获取相关经验"""
        # TODO: 实现基于上下文的经验检索
        return self.experiences[-top_k:]


class MemoryManager:
    """
    记忆管理器 - 统一管理短期和长期记忆
    """
    
    def __init__(self, short_term_size: int = 100):
        self.short_term = ShortTermMemory(max_size=short_term_size)
        self.long_term = LongTermMemory()
        logger.info("MemoryManager initialized")
    
    def add_conversation(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """添加对话"""
        self.short_term.add_message(role, content, metadata)
    
    def create_snapshot(self):
        """
        创建历史快照 - 在处理任务前调用，用于提供"处理前"的历史视图
        """
        self.short_term.create_snapshot()
    
    def clear_snapshot(self):
        """清除历史快照"""
        self.short_term.clear_snapshot()
    
    def get_conversation_context(self, n: int = 10, use_snapshot: bool = False) -> List[Dict[str, Any]]:
        """
        获取对话上下文
        
        Args:
            n: 获取最近N条消息
            use_snapshot: 如果为True，使用快照（处理前历史），否则使用当前历史
        """
        return self.short_term.get_recent_history(n, use_snapshot=use_snapshot)
    
    def update_context(self, key: str, value: Any):
        """更新上下文"""
        self.short_term.update_context(key, value)
    
    def store_knowledge(self, key: str, value: Any, metadata: Dict[str, Any] = None):
        """存储知识到长期记忆"""
        self.long_term.store_knowledge(key, value, metadata)
    
    def retrieve_knowledge(self, key: str) -> Optional[Any]:
        """从长期记忆检索知识"""
        return self.long_term.retrieve_knowledge(key)
    
    def find_similar_patterns(self, query: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """查找相似模式"""
        return self.long_term.find_similar_patterns(query, top_k)
    
    def get_relevant_experiences(self, context: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """获取相关经验"""
        return self.long_term.get_relevant_experiences(context, top_k)
