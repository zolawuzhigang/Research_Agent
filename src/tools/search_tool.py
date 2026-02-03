"""
搜索工具 - 网络搜索
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List, Union
from loguru import logger
from .tool_registry import BaseTool

# 确保requests可用
try:
    import requests
except ImportError:
    requests = None
    logger.error("requests库未安装")


class SearchTool(BaseTool):
    """网络搜索工具"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="search_web",
            description="使用搜索引擎搜索网络信息，适用于查找事实、最新信息、学术资料等"
        )
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        self.base_url = "https://baidu.com/search"
    
    async def execute(self, input_data: Any) -> Dict[str, Any]:
        """
        执行搜索（异步接口）。input_data 可为 str（查询）或 dict（{"query": "..."}）。
        """
        import asyncio

        if isinstance(input_data, dict):
            query = str(input_data.get("query", "")).strip()
        else:
            query = str(input_data or "").strip()
        
        logger.info(f"SearchTool: 搜索 - {query}")
        
        # 验证输入
        if not query:
            logger.warning("搜索查询为空")
            return {
                "success": False,
                "error": "搜索查询不能为空",
                "query": query,
                "results": []
            }
        
        query = query.strip()
        
        if not self.api_key:
            logger.error("SERPAPI_KEY 未设置，search_web 不可用，请配置或使用 advanced_web_search")
            return {
                "success": False,
                "error": "SERPAPI_KEY_not_configured",
                "query": query,
                "results": [],
                "count": 0,
            }
        
        if not requests:
            logger.error("requests库不可用")
            return {
                "success": False,
                "error": "requests库未安装",
                "query": query,
                "results": []
            }
        
        try:
            # 在异步环境中运行同步的requests调用
            loop = asyncio.get_event_loop()
            params = {
                "q": query,
                "api_key": self.api_key,
                "engine": "google",
                "hl": "zh-cn",
                "gl": "cn",
                "num": 5  # 返回前5个结果
            }
            
            # 使用 run_in_executor 避免阻塞事件循环
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(self.base_url, params=params, timeout=10)
            )
            response.raise_for_status()
            
            # 检查响应内容是否为空
            if not response.text or response.text.strip() == '':
                logger.error(f"搜索API返回空响应: {query}")
                return {
                    "success": False,
                    "error": "搜索API返回空响应",
                    "query": query,
                    "results": []
                }
            
            # 尝试解析JSON响应
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"搜索API返回无效JSON: {e}, 响应内容: {response.text[:200]}")
                return {
                    "success": False,
                    "error": f"搜索API返回无效JSON: {str(e)}",
                    "query": query,
                    "results": []
                }
            
            # 提取结果
            results = self._extract_results(data)
            
            if not results:
                logger.warning(f"搜索 '{query}' 未返回结果")
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results)
            }
        
        except requests.exceptions.Timeout:
            logger.error(f"搜索超时: {query}")
            return {
                "success": False,
                "error": "搜索请求超时",
                "query": query,
                "results": []
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"搜索请求失败: {e}")
            return {
                "success": False,
                "error": f"搜索请求失败: {str(e)}",
                "query": query,
                "results": []
            }
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": []
            }
    
    def _extract_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取搜索结果"""
        results = []
        
        # 知识图谱结果（优先级最高）
        if "knowledge_graph" in data:
            kg = data["knowledge_graph"]
            results.append({
                "title": kg.get("title", ""),
                "snippet": kg.get("description", ""),
                "source": "knowledge_graph",
                "type": "fact"
            })
        
        # 有机搜索结果
        if "organic_results" in data:
            for item in data["organic_results"][:5]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "link": item.get("link", ""),
                    "source": "organic",
                    "type": "webpage"
                })
        
        # 新闻结果
        if "news_results" in data:
            for item in data["news_results"][:3]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "link": item.get("link", ""),
                    "source": "news",
                    "type": "news"
                })
        
        # 图片结果
        if "images_results" in data:
            for item in data["images_results"][:3]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "link": item.get("link", ""),
                    "source": "images",
                    "type": "image"
                })
        
        return results
    
    async def search_across_sources(self, query: str, sources: List[str] = None) -> Dict[str, Any]:
        """
        跨数据源搜索
        
        Args:
            query: 搜索查询
            sources: 数据源列表，如 ["web", "news", "images"]
        
        Returns:
            搜索结果
        """
        logger.info(f"SearchTool: 跨数据源搜索 - {query}")
        
        # 默认数据源
        if sources is None:
            sources = ["web"]
        
        all_results = []
        errors = []
        
        # 对每个数据源执行搜索
        for source in sources:
            try:
                result = await self.execute({
                    "query": query,
                    "source": source
                })
                if result.get("success"):
                    all_results.extend(result.get("results", []))
                else:
                    errors.append(f"{source}: {result.get('error', '搜索失败')}")
            except Exception as e:
                logger.error(f"跨数据源搜索失败: {e}")
                errors.append(f"{source}: {str(e)}")
        
        return {
            "success": len(all_results) > 0,
            "query": query,
            "sources": sources,
            "results": all_results,
            "count": len(all_results),
            "errors": errors
        }
    
    def _mock_search(self, query: str) -> Dict[str, Any]:
        """模拟搜索（用于测试）"""
        return {
            "success": True,
            "query": query,
            "results": [
                {
                    "title": f"关于 {query} 的信息",
                    "snippet": f"这是关于 {query} 的模拟搜索结果",
                    "source": "mock",
                    "type": "mock"
                }
            ],
            "count": 1
        }
