"""
WebSearchCrawlTool - 自主网络搜索与深度爬取

从预设站点（百度、知乎）爬取内容，支持多步“点击”链接深入（最多 30 步），
无需外部搜索 API Key。优先 requests + BeautifulSoup；百度结果页若为动态加载，
可后续改为 Selenium 或逆向 Ajax 接口。
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, urljoin, urlparse

from loguru import logger

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

from .tool_registry import BaseTool


# 默认配置
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_DEPTH = 30
DEFAULT_MAX_RESULTS_PER_SOURCE = 10
DEFAULT_MAX_CHARS_PER_PAGE = 8000
DEFAULT_MAX_TOTAL_CHARS = 16000
ANSWER_KEYWORDS = ("公里", "千米", "米", "千米", "km", "米", "厘米", "毫米", "年", "月", "日", "时", "分", "秒", "元", "美元", "人", "个", "条", "次")
# 问答句式与数字+单位模式
ANSWER_PATTERNS = (
    r"答案是[：:]\s*[^\n]{2,80}",
    r"距离为[：:]\s*[^\n]{2,80}",
    r"约为?\s*\d+[\d.]*\s*(?:公里|千米|米|km|元|人|个)",
    r"\d+[\d.]*\s*(?:公里|千米|米|km)\s*(?:左右|约)?",
)
# “查看更多/展开”等可点击文本
MORE_BUTTON_TEXTS = ("查看更多", "展开", "展开更多", "阅读全文", "查看全部", "more", "expand", "read more")


class WebSearchCrawlTool(BaseTool):
    """
    从百度、知乎等预设站点爬取，支持多步深度，无需 API Key。
    输入可为 str（query）或 dict（query, max_depth, max_results）。
    """

    SEARCH_URLS = [
        ("baidu", "https://www.baidu.com/s?wd={query}&ie=utf-8"),
        ("zhihu", "https://www.zhihu.com/api/v4/search_v3?t=general&q={query}&offset=0&limit=20"),
    ]

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_result_tokens: int = 4000,
    ):
        super().__init__(
            name="web_search_crawl",
            description=(
                "从百度、知乎等预设站点爬取网页内容，支持多步深度抓取，无需 API Key；"
                "适用于事实查询、距离/时间等具体答案抽取。"
            ),
        )
        self.timeout = timeout
        self.max_depth = max_depth
        self.max_result_chars = max_result_tokens * 4
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        if self._session is None and requests is not None:
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
            )
            if os.environ.get("WEB_SEARCH_CRAWL_NO_PROXY", "").lower() in ("1", "true", "yes"):
                self._session.trust_env = False
                self._session.proxies = {"http": None, "https": None}
        return self._session

    def _build_url(self, source: str, query: str, mobile: bool = False) -> str:
        encoded = quote(query, safe="")
        if source == "baidu":
            if mobile:
                return f"https://m.baidu.com/s?wd={encoded}&ie=utf-8"
            return f"https://www.baidu.com/s?wd={encoded}&ie=utf-8"
        if source == "zhihu":
            return f"https://www.zhihu.com/api/v4/search_v3?t=general&q={encoded}&offset=0&limit=20"
        return ""

    def _fetch_page(self, url: str, retries: int = 2, mobile_ua: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """返回 (text 或 None, error_message)。mobile_ua=True 时使用移动端 User-Agent。"""
        if not requests:
            return None, "requests 未安装"
        session = self._get_session()
        orig_headers = dict(session.headers)
        if mobile_ua:
            session.headers["User-Agent"] = (
                "Mozilla/5.0 (Linux; Android 10; Mobile) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            )
        try:
            for attempt in range(retries):
                try:
                    resp = session.get(url, timeout=self.timeout)
                    resp.raise_for_status()
                    if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                        resp.encoding = resp.apparent_encoding or "utf-8"
                    return resp.text, None
                except Exception as e:
                    err = str(e)
                    logger.warning(f"请求失败 {url} attempt={attempt + 1}: {err}")
            return None, "请求失败或超时"
        finally:
            if mobile_ua:
                session.headers.update(orig_headers)

    def _parse_baidu(self, html: str, query: str) -> List[Dict[str, Any]]:
        """解析百度 PC 搜索结果页。若页面为动态加载无结果块，则整页兜底提取外链。"""
        if not BeautifulSoup or not html:
            return []
        try:
            soup = BeautifulSoup(html, "html.parser")
            results: List[Dict[str, Any]] = []
            seen_hrefs: Set[str] = set()
            content_left = soup.find(id="content_left")
            if content_left:
                for div in content_left.find_all("div", class_=re.compile(r"c-container|result")):
                    if len(results) >= DEFAULT_MAX_RESULTS_PER_SOURCE:
                        break
                    title_el = div.find("h3") or div.find("a")
                    link_el = div.find("a", href=True)
                    if not link_el:
                        continue
                    href = link_el.get("href", "").strip()
                    if not href.startswith("http"):
                        continue
                    title = (title_el.get_text(strip=True) if title_el else "") or "无标题"
                    snippet_el = div.find("div", class_=re.compile(r"c-abstract|content-right"))
                    snippet = (snippet_el.get_text(strip=True) if snippet_el else "")[:500]
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "link": href,
                        "source": "baidu",
                    })
                    seen_hrefs.add(href)
            if results:
                return results
            # 兜底：无 content_left 或未匹配到块时，整页提取外链（与移动端类似）
            for a in soup.find_all("a", href=re.compile(r"^https?://")):
                if len(results) >= DEFAULT_MAX_RESULTS_PER_SOURCE:
                    break
                href = a.get("href", "").strip()
                if "baidu.com" in href and ("link?" in href or "baidu.com/s?" in href):
                    continue
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                title = a.get_text(strip=True) or "无标题"
                if len(title) < 2:
                    continue
                results.append({
                    "title": title[:200],
                    "snippet": "",
                    "link": href,
                    "source": "baidu",
                })
            return results
        except Exception as e:
            logger.warning(f"百度解析失败: {e}")
            return []

    def _parse_baidu_mobile(self, html: str, query: str) -> List[Dict[str, Any]]:
        """解析百度移动端 m.baidu.com 结果页；多种选择器兜底。"""
        if not BeautifulSoup or not html:
            return []
        try:
            soup = BeautifulSoup(html, "html.parser")
            results = []
            seen_hrefs: Set[str] = set()
            for div in soup.find_all("div", class_=re.compile(r"result|c-container|result-op|c-result|item")):
                if len(results) >= DEFAULT_MAX_RESULTS_PER_SOURCE:
                    break
                link_el = div.find("a", href=True)
                if not link_el:
                    continue
                href = link_el.get("href", "").strip()
                if not href.startswith("http") or "baidu.com" in href and "link?" in href:
                    continue
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                title = link_el.get_text(strip=True) or "无标题"
                snippet_el = div.find(class_=re.compile(r"content|abstract|desc|c-abstract|text"))
                snippet = (snippet_el.get_text(strip=True) if snippet_el else "")[:500]
                if not snippet:
                    snippet = div.get_text(strip=True)[:500]
                results.append({
                    "title": title[:200],
                    "snippet": snippet,
                    "link": href,
                    "source": "baidu_m",
                })
            if results:
                return results
            for a in soup.find_all("a", href=re.compile(r"^https?://")):
                if len(results) >= DEFAULT_MAX_RESULTS_PER_SOURCE:
                    break
                href = a.get("href", "").strip()
                if "baidu.com" in href and ("link?" in href or "baidu.com/s?" in href):
                    continue
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                title = a.get_text(strip=True) or "无标题"
                if len(title) < 2:
                    continue
                results.append({
                    "title": title[:200],
                    "snippet": "",
                    "link": href,
                    "source": "baidu_m",
                })
            return results
        except Exception as e:
            logger.warning(f"百度移动端解析失败: {e}")
            return []

    def _fetch_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """DuckDuckGo 兜底：当百度/知乎均无结果时调用，返回与第一层相同结构。"""
        if not query or DDGS is None:
            return []
        try:
            results: List[Dict[str, Any]] = []
            for item in DDGS().text(query, max_results=DEFAULT_MAX_RESULTS_PER_SOURCE):
                if isinstance(item, dict):
                    title = item.get("title") or ""
                    href = item.get("href") or item.get("link") or ""
                    body = item.get("body") or item.get("snippet") or ""
                else:
                    continue
                if not href.startswith("http"):
                    continue
                results.append({
                    "title": title[:200],
                    "snippet": (body or "")[:500],
                    "link": href,
                    "source": "duckduckgo",
                })
            return results
        except Exception as e:
            logger.warning(f"DuckDuckGo 搜索失败: {e}")
            return []

    def _parse_zhihu_api(self, text: str, query: str) -> List[Dict[str, Any]]:
        """解析知乎搜索 API 返回的 JSON。"""
        import json
        if not text or not text.strip():
            return []
        try:
            data = json.loads(text)
            items = data.get("data", []) if isinstance(data, dict) else []
            results = []
            for item in items:
                if len(results) >= DEFAULT_MAX_RESULTS_PER_SOURCE:
                    break
                if not isinstance(item, dict):
                    continue
                obj = item.get("object", {}) or item
                highlight = item.get("highlight", {}) or {}
                title = (
                    (highlight.get("title") or highlight.get("query", {}).get("title"))
                    or obj.get("title")
                    or obj.get("question", {}).get("title")
                    or "无标题"
                )
                if isinstance(title, dict):
                    title = title.get("raw", "") or str(title)
                snippet = (
                    obj.get("excerpt")
                    or obj.get("content")
                    or highlight.get("description")
                    or ""
                )
                if isinstance(snippet, dict):
                    snippet = snippet.get("raw", "") or str(snippet)
                snippet = (snippet or "")[:500]
                url = (
                    obj.get("url")
                    or obj.get("link", {}).get("url")
                    or ""
                )
                if isinstance(url, dict):
                    url = url.get("url", "") or ""
                if not url or not url.startswith("http"):
                    continue
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "link": url,
                    "source": "zhihu",
                })
            return results
        except Exception as e:
            logger.warning(f"知乎 API 解析失败: {e}")
            return []

    def _is_answer_found(self, text: str, query: str) -> bool:
        """综合判断：问答句式、数字+单位、关键词重叠。"""
        if not text or not query:
            return False
        text_lower = text.lower()
        query_lower = query.lower()
        # 1. 问答句式识别
        for pat in ANSWER_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return True
        # 2. 数字+单位模式（如 1200公里、约 30 元）
        if re.search(r"\d+[\d.]*\s*(?:公里|千米|米|km|元|人|个|条|次)\s*(?:左右|约)?", text):
            query_words = set(re.findall(r"[\w\u4e00-\u9fff]+", query_lower))
            query_words.discard("")
            if not query_words:
                return True
            overlap = sum(1 for w in query_words if len(w) > 1 and w in text_lower)
            if overlap >= 1:
                return True
        # 3. 关键词+单位
        has_unit = any(k in text for k in ANSWER_KEYWORDS)
        query_words = set(re.findall(r"[\w\u4e00-\u9fff]+", query_lower))
        query_words.discard("")
        if not query_words:
            return has_unit
        overlap = sum(1 for w in query_words if len(w) > 1 and w in text_lower)
        return has_unit and (overlap >= 1 or len(query_words) <= 2)

    def _truncate_content(self, text: str, max_chars: int = DEFAULT_MAX_CHARS_PER_PAGE) -> str:
        """简单截断：保留前段。"""
        if not text or len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    def _smart_truncate(self, text: str, max_chars: int, query: str) -> str:
        """智能截断：保留含关键词的句子、开头和结尾重要部分，移除明显无关内容。"""
        if not text or len(text) <= max_chars:
            return text
        query_words = set(re.findall(r"[\w\u4e00-\u9fff]+", query.lower()))
        query_words.discard("")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return text[:max_chars] + "..."
        keep_lines: List[str] = []
        for ln in lines:
            if any(w in ln.lower() for w in query_words if len(w) > 1):
                keep_lines.append(ln)
        head = "\n".join(lines[:5])
        tail = "\n".join(lines[-3:]) if len(lines) > 5 else ""
        combined = "\n".join(keep_lines) if keep_lines else ""
        if head and head not in combined:
            combined = head + "\n" + combined
        if tail and tail not in combined:
            combined = combined + "\n" + tail
        combined = " ".join(combined.split())[:max_chars]
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "..."
        return combined or text[:max_chars] + "..."

    def _extract_links(self, soup: Any, base_url: str, visited: Set[str]) -> List[Tuple[str, str]]:
        """提取可跟进链接：<a href>、查看更多/展开旁的 <a>、.more/.expand 内 <a>，以及 onclick 中的 URL（仅记录）。"""
        if not soup:
            return []
        seen_urls: Set[str] = set()
        out: List[Tuple[str, str]] = []
        try:
            base_domain = urlparse(base_url).netloc

            def _add_link(href: str, link_text: str) -> None:
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    return
                full_url = urljoin(base_url, href)
                if not full_url.startswith("http"):
                    return
                parsed = urlparse(full_url)
                if parsed.netloc != base_domain and base_domain not in ("www.baidu.com", "www.zhihu.com", "m.baidu.com"):
                    return
                if full_url in visited or full_url in seen_urls:
                    return
                if any(x in full_url.lower() for x in ("login", "signin", "logout", "javascript", "void(0)")):
                    return
                seen_urls.add(full_url)
                out.append((full_url, link_text or ""))

            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()
                link_text = a.get_text(strip=True) or ""
                _add_link(href, link_text)

            for tag in soup.find_all(True, class_=re.compile(r"more|expand|read-more|show-more", re.I)):
                a = tag.find("a", href=True)
                if a:
                    _add_link(a.get("href", "").strip(), a.get_text(strip=True) or tag.get_text(strip=True)[:50])

            for node in soup.find_all(string=re.compile("|".join(re.escape(t) for t in MORE_BUTTON_TEXTS))):
                parent = getattr(node, "parent", None)
                if not parent:
                    continue
                a = None
                if getattr(parent, "name", None) == "a" and parent.get("href"):
                    a = parent
                else:
                    a = parent.find("a", href=True) if hasattr(parent, "find") else None
                if a:
                    txt = a.get_text(strip=True) if hasattr(a, "get_text") else ""
                    _add_link(a.get("href", "").strip(), txt[:80])

            for tag in soup.find_all(attrs={"onclick": True}):
                onclick = (tag.get("onclick") or "").strip()
                m = re.search(r"['\"](https?://[^'\"]+)['\"]", onclick)
                if m:
                    _add_link(m.group(1), tag.get_text(strip=True)[:80] or "onclick")
        except Exception as e:
            logger.debug(f"_extract_links error: {e}")
        return out

    def _score_link_relevance(self, url: str, link_text: str, query: str) -> float:
        """简单相关性：query 词在 url + link_text 中出现越多得分越高。"""
        query_words = set(re.findall(r"[\w\u4e00-\u9fff]+", query.lower()))
        query_words.discard("")
        combined = (url + " " + link_text).lower()
        if not query_words:
            return 0.0
        return sum(1 for w in query_words if len(w) > 1 and w in combined) / max(1, len(query_words))

    def _parse_page_text_and_links(self, html: str, page_url: str) -> Tuple[str, List[Tuple[str, str]]]:
        """从 HTML 提取正文与链接。用于深度爬取时的子页面。"""
        if not BeautifulSoup or not html:
            return "", []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            text = " ".join(text.split())[:DEFAULT_MAX_CHARS_PER_PAGE]
            links = self._extract_links(soup, page_url, set())
            return text, links
        except Exception as e:
            logger.debug(f"_parse_page_text_and_links: {e}")
            return "", []

    async def _fetch_first_layer(self, query: str) -> List[Dict[str, Any]]:
        """第一层：并发请求百度与知乎，合并结果。"""
        all_results: List[Dict[str, Any]] = []
        loop = asyncio.get_event_loop()

        def do_baidu():
            url = self._build_url("baidu", query)
            text, err = self._fetch_page(url)
            if err:
                logger.warning(f"百度请求失败: {err}")
                return []
            results = self._parse_baidu(text or "", query)
            if not results:
                url_m = self._build_url("baidu", query, mobile=True)
                text_m, err_m = self._fetch_page(url_m, mobile_ua=True)
                if not err_m and text_m:
                    results = self._parse_baidu_mobile(text_m, query)
                    if results:
                        logger.info("百度 PC 无结果块，使用移动端解析成功")
            return results

        def do_zhihu():
            url = self._build_url("zhihu", query)
            text, err = self._fetch_page(url)
            if err:
                logger.warning(f"知乎请求失败: {err}")
                return []
            return self._parse_zhihu_api(text or "", query)

        try:
            baidu_r, zhihu_r = await asyncio.gather(
                loop.run_in_executor(None, do_baidu),
                loop.run_in_executor(None, do_zhihu),
            )
            all_results.extend(baidu_r or [])
            all_results.extend(zhihu_r or [])
        except Exception as e:
            logger.warning(f"第一层请求异常: {e}")

        if not all_results and DDGS is not None:
            try:
                ddg_results = await loop.run_in_executor(
                    None,
                    lambda: self._fetch_duckduckgo(query),
                )
                all_results.extend(ddg_results or [])
                if ddg_results:
                    logger.info("百度/知乎无结果，使用 DuckDuckGo 兜底成功")
            except Exception as e:
                logger.warning(f"DuckDuckGo 兜底失败: {e}")

        return all_results

    async def _deep_crawl(
        self,
        query: str,
        first_layer_results: List[Dict[str, Any]],
        max_depth: int,
    ) -> Dict[str, Any]:
        """多步深度：从第一层结果中找直接答案或选链接继续抓取。"""
        visited: Set[str] = set()
        summaries: List[str] = []
        sources: List[str] = []
        total_chars = 0

        for r in first_layer_results:
            snippet = (r.get("snippet") or "").strip()
            if snippet and total_chars + len(snippet) <= self.max_result_chars:
                summaries.append(snippet)
                total_chars += len(snippet)
            link = r.get("link", "")
            if link:
                sources.append(link)
            if self._is_answer_found(snippet, query):
                return {
                    "direct_answer": self._truncate_content(snippet, 2000),
                    "sources": sources[:20],
                    "summaries": summaries[:30],
                    "confidence": 0.85,
                    "search_depth": 1,
                }
        if max_depth <= 1:
            return {"direct_answer": None, "sources": sources[:20], "summaries": summaries[:30], "confidence": 0.5, "search_depth": 1}

        current_depth = 1
        candidates: List[Tuple[str, str, float]] = []
        for r in first_layer_results:
            link = r.get("link", "")
            if link and link not in visited:
                title = r.get("title", "")
                score = self._score_link_relevance(link, title, query)
                candidates.append((link, title, score))
        candidates.sort(key=lambda x: -x[2])

        loop = asyncio.get_event_loop()
        while candidates and current_depth < max_depth:
            url, link_text, _ = candidates.pop(0)
            if url in visited:
                continue
            visited.add(url)
            result = await loop.run_in_executor(None, lambda u=url: self._fetch_page(u))
            if result is None:
                continue
            text, err = result
            if err or not text:
                continue
            current_depth += 1
            page_text, next_links = self._parse_page_text_and_links(text or "", url)
            truncated = self._smart_truncate(page_text, 1500, query)
            if truncated and total_chars + len(truncated) <= self.max_result_chars:
                summaries.append(truncated)
                total_chars += len(truncated)
            sources.append(url)
            if self._is_answer_found(page_text, query):
                return {
                    "direct_answer": self._smart_truncate(page_text, 2000, query),
                    "sources": sources[:20],
                    "summaries": summaries[:30],
                    "confidence": 0.8,
                    "search_depth": current_depth,
                }
            for next_url, next_text in next_links:
                if next_url in visited:
                    continue
                score = self._score_link_relevance(next_url, next_text, query)
                candidates.append((next_url, next_text, score))
            candidates.sort(key=lambda x: -x[2])

        return {
            "direct_answer": None,
            "sources": sources[:20],
            "summaries": summaries[:30],
            "confidence": 0.4,
            "search_depth": current_depth,
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索问题或关键词"},
                    "max_depth": {"type": "integer", "description": "最大爬取深度，默认 30", "default": 30},
                    "max_results": {"type": "integer", "description": "每源最多结果数", "default": 10},
                },
                "required": ["query"],
            },
        }

    async def execute(self, input_data: Any) -> Dict[str, Any]:
        if isinstance(input_data, str):
            query = input_data.strip()
            max_depth = self.max_depth
        elif isinstance(input_data, dict):
            query = str(input_data.get("query", "")).strip()
            max_depth = int(input_data.get("max_depth", self.max_depth) or self.max_depth)
        else:
            query = str(input_data or "").strip()
            max_depth = self.max_depth

        if not query:
            return {
                "success": False,
                "error": "query 不能为空",
                "query": query,
                "results": [],
                "count": 0,
            }

        max_depth = max(1, min(max_depth, DEFAULT_MAX_DEPTH))
        logger.info(f"WebSearchCrawlTool: query='{query}', max_depth={max_depth}")

        try:
            first_layer = await self._fetch_first_layer(query)
            if not first_layer:
                return {
                    "success": False,
                    "error": "未获取到任何搜索结果",
                    "query": query,
                    "results": [],
                    "count": 0,
                }
            deep_info = await self._deep_crawl(query, first_layer, max_depth)
            total_chars = sum(len(s) for s in deep_info.get("summaries", []))
            if total_chars > self.max_result_chars:
                summaries = deep_info.get("summaries", [])[:15]
                deep_info["summaries"] = [self._truncate_content(s, self.max_result_chars // max(1, len(summaries))) for s in summaries]

            return {
                "success": True,
                "query": query,
                "results": first_layer,
                "count": len(first_layer),
                "direct_answer": deep_info.get("direct_answer"),
                "sources": deep_info.get("sources", []),
                "related_links": deep_info.get("sources", [])[:10],
                "summaries": deep_info.get("summaries", []),
                "confidence": deep_info.get("confidence", 0.5),
                "search_depth": deep_info.get("search_depth", 1),
            }
        except Exception as e:
            logger.exception(f"WebSearchCrawlTool 执行异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": [],
                "count": 0,
            }
