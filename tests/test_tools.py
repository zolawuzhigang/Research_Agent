"""
测试工具功能
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.tools import SearchTool, CalculatorTool


@pytest.mark.asyncio
async def test_calculator_tool():
    """测试计算工具"""
    tool = CalculatorTool()
    
    # 正常计算
    result = await tool.execute("2 + 3 * 4")
    assert result["success"] is True
    assert result["result"] == 14.0
    
    # 简单计算
    result = await tool.execute("10 + 5")
    assert result["success"] is True
    assert result["result"] == 15.0
    
    # 无效表达式
    result = await tool.execute("abc")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_search_tool_mock():
    """测试搜索工具（模拟模式：无 API Key 时 mock 返回）"""
    tool = SearchTool(api_key=None)
    mock_result = {
        "success": True,
        "query": "测试查询",
        "results": [{"title": "mock title", "snippet": "mock snippet", "link": "https://example.com"}],
        "count": 1,
    }
    with patch.object(tool, "execute", new_callable=AsyncMock, return_value=mock_result):
        result = await tool.execute("测试查询")
    assert result["success"] is True
    assert "results" in result
    assert len(result["results"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
