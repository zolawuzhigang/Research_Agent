"""
答案归一化工具
"""

import re
from typing import Optional


def normalize_answer(raw_answer: str) -> str:
    """
    对答案进行归一化处理，匹配赛题要求
    
    Args:
        raw_answer: 模型原始输出
    
    Returns:
        归一化后的答案
    """
    if raw_answer is None:
        return ""
    
    # 1. 转为小写
    normalized = raw_answer.lower()
    
    # 2. 去除首尾空格
    normalized = normalized.strip()
    
    # 3. 提取答案（如果包含 "Answer:" 或 "答案：" 前缀，提取后面的内容）
    if "answer:" in normalized:
        normalized = normalized.split("answer:")[-1].strip()
    if "答案：" in normalized or "答案:" in normalized:
        for prefix in ("答案：", "答案:"):
            if prefix in normalized:
                normalized = normalized.split(prefix)[-1].strip()
                break
    
    # 4. 处理数值格式（更保守的策略）
    # 只有当整个答案看起来是纯数字时才进行数值处理
    # 避免破坏包含数字的文本答案
    if re.match(r'^\s*[\d,.\s]+\s*$', normalized):
        # 整个答案都是数字，进行数值处理
        number_match = re.search(r'(\d[\d,]*\.?\d*)', normalized)
        if number_match:
            num_str = number_match.group(1).replace(',', '')
            try:
                if '.' in num_str:
                    # 浮点数：根据题目可能需要四舍五入或取整
                    num_value = float(num_str)
                    normalized = str(int(round(num_value)))
                else:
                    # 整数：直接使用
                    normalized = num_str
            except (ValueError, OverflowError):
                # 如果转换失败，保持原样
                pass
    
    # 5. 规范多实体分隔符
    # 将中文顿号、分号、连续逗号等统一为 ", "
    normalized = re.sub(r'[；、，]+', ', ', normalized)
    normalized = re.sub(r',\s*,', ',', normalized)  # 处理连续逗号
    normalized = normalized.strip(', ')  # 再次清理
    
    # 6. 移除多余的标点和空格
    normalized = re.sub(r'\s+', ' ', normalized)  # 多个空格合并为一个
    normalized = normalized.strip()
    
    # 7. 处理特殊格式
    # 移除引号
    normalized = normalized.strip('"\'')
    
    return normalized


def test_normalize_answer():
    """测试答案归一化函数"""
    test_cases = [
        ("Answer: 巴黎", "巴黎"),
        ("答案：140", "140"),
        ("北京, 上海, 广州", "北京, 上海, 广州"),
        ("1,234.56", "1235"),  # 浮点数取整
        ("   France  ", "france"),
        ("答案：\"北京\"", "北京"),
    ]
    
    for input_val, expected in test_cases:
        result = normalize_answer(input_val)
        print(f"Input: {input_val} -> Output: {result} (Expected: {expected})")
        assert result == expected.lower(), f"Failed: {input_val}"


if __name__ == "__main__":
    test_normalize_answer()
    print("All tests passed!")
