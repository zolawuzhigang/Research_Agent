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
    
    async def execute(self, input_data: Any) -> Dict[str, Any]:
        """
        执行计算
        
        Args:
            input_data: 数学表达式（可为str或dict）
        
        Returns:
            计算结果
        """
        # 处理输入数据
        if isinstance(input_data, dict):
            expression = str(input_data.get("expression", ""))
        else:
            expression = str(input_data or "")
        
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
        """安全计算（限制可用的操作符和函数）"""
        # 只允许基本的数学运算和安全的数学函数
        allowed_pattern = r'^[0-9+\-*/().\s]+$'
        if not re.match(allowed_pattern, expression):
            # 检查是否包含安全的数学函数
            safe_functions = ['sin', 'cos', 'tan', 'sqrt', 'exp', 'log', 'abs', 'pow']
            for func in safe_functions:
                if func in expression:
                    # 检查函数调用格式是否安全
                    if not re.match(r'^[0-9+\-*/().\s%s]+$' % ''.join(safe_functions), expression):
                        raise ValueError("表达式包含不允许的字符或函数")
                    break
            else:
                raise ValueError("表达式包含不允许的字符")
        
        try:
            # 导入安全的数学函数
            import math
            
            # 安全的全局变量
            safe_globals = {
                '__builtins__': {},
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                'sqrt': math.sqrt,
                'exp': math.exp,
                'log': math.log,
                'abs': abs,
                'pow': pow,
                'math': math
            }
            
            result = eval(expression, safe_globals)
            return float(result)
        except Exception as e:
            raise ValueError(f"计算错误: {e}")
