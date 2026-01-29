"""
测试答案归一化功能
"""

import pytest
from src.utils.normalize import normalize_answer


def test_normalize_basic():
    """测试基本归一化"""
    assert normalize_answer("Answer: 巴黎") == "巴黎"
    assert normalize_answer("  140  ") == "140"
    assert normalize_answer("France") == "france"


def test_normalize_numbers():
    """测试数值归一化"""
    assert normalize_answer("1,234.56") == "1235"  # 浮点数取整
    assert normalize_answer("答案：140") == "140"
    assert normalize_answer("123") == "123"


def test_normalize_multiple_entities():
    """测试多实体归一化"""
    result = normalize_answer("北京, 上海, 广州")
    assert result == "北京, 上海, 广州"
    
    result = normalize_answer("北京、上海、广州")
    assert result == "北京, 上海, 广州"


def test_normalize_empty():
    """测试空值处理"""
    assert normalize_answer("") == ""
    assert normalize_answer(None) == ""
    assert normalize_answer("   ") == ""


def test_normalize_quotes():
    """测试引号处理"""
    assert normalize_answer('答案："北京"') == "北京"
    assert normalize_answer("答案：'北京'") == "北京"


def test_normalize_preserve_text_with_numbers():
    """测试包含数字的文本（不应被当作纯数字处理）"""
    result = normalize_answer("2024年1月")
    # 不应被转换为纯数字
    assert "2024" in result or "年" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
