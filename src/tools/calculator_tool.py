"""
计算工具 - 数学计算
"""

import re
from typing import Dict, Any
from loguru import logger
from .tool_registry import BaseTool


class CalculatorTool(BaseTool):
    """数学计算工具"""
    
    def __init__(self):
        super().__init__(
            name="calculate",
            description="执行数学计算，支持基本四则运算、幂运算等"
        )
    
    async def execute(self, expression: str) -> Dict[str, Any]:
        """
        执行计算
        
        Args:
            expression: 数学表达式（如 "2 + 3 * 4"）
        
        Returns:
            计算结果
        """
        logger.info(f"CalculatorTool: 计算 - {expression}")
        
        try:
            # 清理表达式
            cleaned = self._clean_expression(expression)
            
            # 安全计算（只允许数学表达式）
            result = self._safe_eval(cleaned)
            
            return {
                "success": True,
                "expression": expression,
                "result": result,
                "formatted": str(result)
            }
        
        except Exception as e:
            logger.error(f"计算失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "expression": expression
            }
    
    def _clean_expression(self, expression: str) -> str:
        """清理表达式，只保留安全的数学字符"""
        # 移除所有非数学字符
        cleaned = re.sub(r'[^0-9+\-*/().\s]', '', expression)
        # 移除多余空格
        cleaned = re.sub(r'\s+', '', cleaned)
        return cleaned
    
    def _safe_eval(self, expression: str) -> float:
        """安全计算（限制可用的操作符）"""
        # 只允许基本的数学运算
        allowed_chars = set('0123456789+-*/(). ')
        if not all(c in allowed_chars for c in expression):
            raise ValueError("表达式包含不允许的字符")
        
        try:
            result = eval(expression)
            return float(result)
        except Exception as e:
            raise ValueError(f"计算错误: {e}")
