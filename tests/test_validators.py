"""
测试验证工具
"""

import pytest
from src.utils.validators import (
    validate_question,
    validate_answer,
    validate_step_id,
    validate_confidence
)


def test_validate_question():
    """测试问题验证"""
    # 正常情况
    assert validate_question("测试问题") == "测试问题"
    
    # 空问题
    with pytest.raises(ValueError):
        validate_question("")
    
    with pytest.raises(ValueError):
        validate_question(None)
    
    # 过长问题
    with pytest.raises(ValueError):
        validate_question("a" * 6000)
    
    # 空白字符
    with pytest.raises(ValueError):
        validate_question("   ")


def test_validate_answer():
    """测试答案验证"""
    # 正常情况
    assert validate_answer("测试答案") == "测试答案"
    assert validate_answer(123) == "123"
    
    # 空答案
    with pytest.raises(ValueError):
        validate_answer("")
    
    with pytest.raises(ValueError):
        validate_answer(None)


def test_validate_step_id():
    """测试步骤ID验证"""
    # 正常情况
    assert validate_step_id(1) == 1
    assert validate_step_id("1") == 1
    
    # 无效ID
    with pytest.raises(ValueError):
        validate_step_id(-1)
    
    with pytest.raises(ValueError):
        validate_step_id(None)
    
    with pytest.raises(ValueError):
        validate_step_id("abc")


def test_validate_confidence():
    """测试置信度验证"""
    # 正常情况
    assert validate_confidence(0.5) == 0.5
    assert validate_confidence(0) == 0.0
    assert validate_confidence(1) == 1.0
    
    # 边界情况
    assert validate_confidence(-1) == 0.0
    assert validate_confidence(2) == 1.0
    
    # None处理
    assert validate_confidence(None) == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
