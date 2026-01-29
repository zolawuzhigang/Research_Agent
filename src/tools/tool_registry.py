"""
工具注册表 - 统一管理所有工具
"""

from typing import Dict, Any, Optional, Callable, List
from abc import ABC, abstractmethod
from loguru import logger


class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, input_data: Any) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            input_data: 工具输入
        
        Returns:
            工具执行结果
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具schema（用于LLM function calling）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {}
        }


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        logger.info("ToolRegistry initialized")
    
    def register(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.info(f"工具已注册: {tool.name} - {tool.description}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools.values()
        ]
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取所有工具的schema（用于LLM function calling）"""
        return [tool.get_schema() for tool in self.tools.values()]
