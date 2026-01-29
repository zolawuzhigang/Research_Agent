"""
AdvancedWebSearchTool
---------------------

基于 openmanus WebSearch 思路，适配到本项目的 BaseTool 接口：
- 多搜索引擎兜底（DuckDuckGo + Bing 为主，便于国内环境与依赖安装）
- 可选抓取结果页面正文（BeautifulSoup 提取，做长度截断）
- 输出结构化结果，字段与现有 SearchTool 尽量对齐：
  {
      "success": True,
      "query": "xxx",
      "results": [
          {"title": "...", "snippet": "...", "link": "...", "source": "..."}
      ],
      "count": N
  }

ToolHub 会自动从 description 中提取 "search" / "extract" / "document" 能力标签，
用于 GAIA 这类需要高质量检索 + 正文抽取的任务。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger
import asyncio

# 依赖采用“懒加载+降级”策略：如果缺失，不阻塞整个 Agent，只在本工具内部报错
try:  # type: ignore
    import requests  # noqa: F401
except Exception:  # pragma: no cover - 仅用于运行时环境探测
    requests = None  # type: ignore

try:  # type: ignore
    from bs4 import BeautifulSoup  # noqa: F401
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

try:  # type: ignore
    from duckduckgo_search import DDGS  # noqa: F401
except Exception:  # pragma: no cover
    DDGS = None  # type: ignore

from .tool_registry import BaseTool


@dataclass
class AdvSearchItem:
    """单条搜索结果"""

    title: str
    url: str
    description: str = ""
    source: str = "duckduckgo"


class DuckDuckGoSimpleEngine:
    """简化版 DuckDuckGo 搜索引擎"""

    def perform_search(self, query: str, num_results: int = 10) -> List[AdvSearchItem]:
        if DDGS is None:
            logger.warning("duckduckgo_search 未安装，DuckDuckGoSimpleEngine 不可用")
            return []
        results: List[AdvSearchItem] = []
        raw_results = DDGS().text(query, max_results=num_results)
        for i, item in enumerate(raw_results):
            if isinstance(item, dict):
                title = item.get("title") or f"DuckDuckGo Result {i+1}"
                url = item.get("href") or ""
                desc = item.get("body") or ""
            else:
                title = f"DuckDuckGo Result {i+1}"
                url = str(item)
                desc = ""
            results.append(
                AdvSearchItem(
                    title=title,
                    url=url,
                    description=desc,
                    source="duckduckgo",
                )
            )
        return results


class BingSimpleEngine:
    """
    简化版 Bing 搜索引擎。
    仅解析基础标题/URL/摘要，避免完整 openmanus 版本中的复杂 UA/翻页逻辑。
    """

    def __init__(self) -> None:
        if requests is None:
            self.session = None
            return
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9,zh-CN,zh;q=0.8",
            }
        )

    def perform_search(self, query: str, num_results: int = 10) -> List[AdvSearchItem]:
        if requests is None or BeautifulSoup is None:
            logger.warning("requests/bs4 未安装，BingSimpleEngine 不可用")
            return []

        if not query:
            return []
        try:
            url = "https://www.bing.com/search"
            params = {"q": query}
            res = self.session.get(url, params=params, timeout=10)
            res.raise_for_status()
        except Exception as e:
            logger.warning(f"BingSimpleEngine 请求失败: {e}")
            return []

        try:
            soup = BeautifulSoup(res.text, "html.parser")  # type: ignore[arg-type]
            ol = soup.find("ol", id="b_results")
            if not ol:
                return []
            items: List[AdvSearchItem] = []
            for li in ol.find_all("li", class_="b_algo"):
                if len(items) >= num_results:
                    break
                h2 = li.find("h2")
                if not h2 or not h2.a:
                    continue
                title = h2.get_text(strip=True) or "Bing Result"
                link = h2.a.get("href", "")
                p = li.find("p")
                desc = p.get_text(strip=True) if p else ""
                items.append(
                    AdvSearchItem(
                        title=title,
                        url=link,
                        description=desc,
                        source="bing",
                    )
                )
            return items
        except Exception as e:
            logger.warning(f"BingSimpleEngine 解析失败: {e}")
            return []


class AdvancedWebSearchTool(BaseTool):
    """
    高级网络搜索工具：
    - 使用 DuckDuckGo + Bing 等多引擎搜索
    - 支持抓取网页正文（用于复杂事实题、多跳题的精确抽取）
    - 适用于 search / research / document / extract 场景
    """

    def __init__(self) -> None:
        super().__init__(
            name="advanced_web_search",
            description=(
                "高级网络搜索工具，使用 DuckDuckGo/Bing 等多搜索引擎检索信息，"
                "并可选抓取网页正文内容，适用于复杂事实查询、文档内容提取、"
                "RAG 和多跳推理场景。"
            ),
        )
        self.ddg_engine = DuckDuckGoSimpleEngine()
        self.bing_engine = BingSimpleEngine()

    def get_schema(self) -> Dict[str, Any]:
        """为 LLM function calling 提供参数 schema。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "必填，搜索查询问题或关键词。",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "可选，返回的结果数量（默认 5，最大 10）。",
                        "default": 5,
                    },
                    "fetch_content": {
                        "type": "boolean",
                        "description": "可选，是否抓取网页正文内容（默认 False）。",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, input_data: Any) -> Dict[str, Any]:
        """
        input_data 可以是：
        - 纯字符串：视为 query
        - dict：{"query": "...", "num_results": 5, "fetch_content": true}
        """
        if isinstance(input_data, str):
            query = input_data.strip()
            num_results = 5
            fetch_content = False
        elif isinstance(input_data, dict):
            query = str(input_data.get("query", "")).strip()
            num_results = int(input_data.get("num_results", 5) or 5)
            fetch_content = bool(input_data.get("fetch_content", False))
        else:
            query = str(input_data or "").strip()
            num_results = 5
            fetch_content = False

        if not query:
            logger.warning("AdvancedWebSearchTool: query 为空")
            return {
                "success": False,
                "error": "query 不能为空",
                "query": query,
                "results": [],
                "count": 0,
            }

        num_results = max(1, min(num_results, 10))

        logger.info(
            f"AdvancedWebSearchTool: 搜索 query='{query}', num_results={num_results}, fetch_content={fetch_content}"
        )

        # 先用 DuckDuckGo，若无结果再用 Bing 兜底
        results: List[AdvSearchItem] = []
        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.ddg_engine.perform_search(query, num_results)
            )
        except Exception as e:
            logger.warning(f"DuckDuckGo 搜索失败: {e}")

        if not results:
            try:
                results = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.bing_engine.perform_search(query, num_results)
                )
            except Exception as e:
                logger.warning(f"Bing 搜索失败: {e}")

        if not results:
            return {
                "success": False,
                "error": "all_engines_failed",
                "query": query,
                "results": [],
                "count": 0,
            }

        # 可选抓取正文
        if fetch_content:
            await self._fetch_contents(results)

        # 规范化输出为现有 SearchTool 类似结构
        norm_results: List[Dict[str, Any]] = []
        for item in results:
            snippet = item.description or ""
            # 如果抓了正文，可以把一部分正文拼到 snippet 里；这里保持简单，由 ExecutionAgent 控制截断
            norm_results.append(
                {
                    "title": item.title,
                    "snippet": snippet,
                    "link": item.url,
                    "source": item.source,
                }
            )

        return {
            "success": True,
            "query": query,
            "results": norm_results,
            "count": len(norm_results),
        }

    async def _fetch_contents(self, items: List[AdvSearchItem]) -> None:
        """为若干结果抓取网页正文（简单版本，注意超时与长度控制）。"""

        async def _fetch_one(it: AdvSearchItem) -> None:
            if requests is None or BeautifulSoup is None:
                return
            if not it.url:
                return
            try:
                def _req() -> Optional[str]:
                    resp = requests.get(it.url, timeout=8)  # type: ignore[call-arg]
                    if resp.status_code != 200:
                        return None
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "header", "footer", "nav"]):
                        tag.extract()
                    text = soup.get_text(separator="\n", strip=True)
                    if not text:
                        return None
                    # 控制正文长度，避免 token 爆炸
                    return " ".join(text.split())[:8000]

                content = await asyncio.get_event_loop().run_in_executor(None, _req)
                if content:
                    # 这里不单独暴露 raw_content，避免结构过重；
                    # 直接把前一部分给到 description，后续再由 ExecutionAgent 截断。
                    if it.description:
                        it.description = f"{it.description}\n{content}"
                    else:
                        it.description = content
            except Exception as e:
                logger.debug(f"抓取正文失败 {it.url}: {e}")

        tasks = [asyncio.create_task(_fetch_one(it)) for it in items]
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)

