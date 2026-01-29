"""
验证工具 - 输入验证和参数检查
"""

from typing import Any, Optional
import re


def validate_question(question: str, max_length: int = 5000) -> str:
    """
    验证问题
    
    Args:
        question: 问题文本
        max_length: 最大长度
    
    Returns:
        清理后的问题
    
    Raises:
        ValueError: 如果问题无效
    """
    if not question:
        raise ValueError("问题不能为空")
    
    if not isinstance(question, str):
        raise ValueError(f"问题必须是字符串，得到 {type(question)}")
    
    question = question.strip()
    
    if not question:
        raise ValueError("问题不能只包含空白字符")
    
    if len(question) > max_length:
        raise ValueError(f"问题长度不能超过 {max_length} 字符")
    
    return question


def validate_answer(answer: Any) -> str:
    """
    验证答案
    
    Args:
        answer: 答案（可以是任何类型）
    
    Returns:
        字符串格式的答案
    
    Raises:
        ValueError: 如果答案无效
    """
    if answer is None:
        raise ValueError("答案不能为None")
    
    answer_str = str(answer).strip()
    
    if not answer_str:
        raise ValueError("答案不能为空")
    
    return answer_str


def validate_step_id(step_id: Any) -> int:
    """
    验证步骤ID
    
    Args:
        step_id: 步骤ID
    
    Returns:
        整数步骤ID
    
    Raises:
        ValueError: 如果步骤ID无效
    """
    if step_id is None:
        raise ValueError("步骤ID不能为None")
    
    try:
        step_id_int = int(step_id)
        if step_id_int < 0:
            raise ValueError("步骤ID不能为负数")
        return step_id_int
    except (ValueError, TypeError):
        raise ValueError(f"步骤ID必须是整数，得到 {type(step_id)}")


def validate_confidence(confidence: Any) -> float:
    """
    验证置信度
    
    Args:
        confidence: 置信度值
    
    Returns:
        0-1之间的浮点数
    
    Raises:
        ValueError: 如果置信度无效
    """
    if confidence is None:
        return 0.0
    
    try:
        conf_float = float(confidence)
        if conf_float < 0.0:
            return 0.0
        if conf_float > 1.0:
            return 1.0
        return conf_float
    except (ValueError, TypeError):
        return 0.0


def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
    """
    清理字符串（移除危险字符）
    
    Args:
        text: 输入文本
        max_length: 最大长度（可选）
    
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 移除控制字符（保留换行和制表符）
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    
    # 限制长度
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()
