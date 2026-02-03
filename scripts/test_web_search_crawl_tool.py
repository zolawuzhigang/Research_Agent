"""
单独测试 WebSearchCrawlTool：用具体问题调用并打印完整返回，便于排查搜不到答案的原因。

用法:
  python scripts/test_web_search_crawl_tool.py                    # 用默认问题测试
  python scripts/test_web_search_crawl_tool.py --diagnose         # 诊断各源（百度/知乎/DuckDuckGo）
  python scripts/test_web_search_crawl_tool.py "你的问题" 5       # 指定问题和深度（Windows 下中文建议用 chcp 65001 或使用默认问题）

环境变量:
  WEB_SEARCH_CRAWL_NO_PROXY=1  禁用代理，避免 ProxyError
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 避免命令行编码问题：默认使用下列问题测试
DEFAULT_QUERIES = [
    "北京到上海有多远",
    "珠穆朗玛峰多高",
]


def _diagnose(tool, query: str) -> None:
    """诊断各搜索源：百度 / 知乎 / DuckDuckGo 的请求与解析结果数量。"""
    from src.tools.web_search_crawl_tool import DDGS
    print("[诊断] 各源请求与解析:")
    # 百度 PC
    url_b = tool._build_url("baidu", query)
    text_b, err_b = tool._fetch_page(url_b)
    n_b = 0
    if not err_b and text_b:
        n_b = len(tool._parse_baidu(text_b, query))
    print(f"  百度 PC: fetch_err={err_b or '无'}, parse_count={n_b}")
    if not n_b:
        url_m = tool._build_url("baidu", query, mobile=True)
        text_m, err_m = tool._fetch_page(url_m, mobile_ua=True)
        n_m = len(tool._parse_baidu_mobile(text_m or "", query)) if not err_m and text_m else 0
        print(f"  百度 移动: fetch_err={err_m or '无'}, parse_count={n_m}")
    # 知乎
    url_z = tool._build_url("zhihu", query)
    text_z, err_z = tool._fetch_page(url_z)
    n_z = len(tool._parse_zhihu_api(text_z or "", query)) if not err_z and text_z else 0
    print(f"  知乎 API: fetch_err={err_z or '无'}, parse_count={n_z}")
    # DuckDuckGo
    if DDGS is not None:
        try:
            ddg = tool._fetch_duckduckgo(query)
            print(f"  DuckDuckGo: count={len(ddg)}")
        except Exception as e:
            print(f"  DuckDuckGo: error={e}")
    else:
        print("  DuckDuckGo: 未安装 (pip install duckduckgo-search)")
    print()


async def run_test(query: str, max_depth: int = 5, diagnose: bool = False):
    from src.tools import WebSearchCrawlTool
    tool = WebSearchCrawlTool()
    print(f"查询: {query}")
    print(f"max_depth: {max_depth}")
    if diagnose:
        _diagnose(tool, query)
    print("-" * 60)
    result = await tool.execute({"query": query, "max_depth": max_depth})
    print("success:", result.get("success"))
    print("count:", result.get("count"))
    print("error:", result.get("error"))
    print("direct_answer:", result.get("direct_answer"))
    print("confidence:", result.get("confidence"))
    print("search_depth:", result.get("search_depth"))
    print("sources 数量:", len(result.get("sources", [])))
    print("summaries 数量:", len(result.get("summaries", [])))
    if result.get("results"):
        print("\n第一层 results 前 3 条:")
        for i, r in enumerate(result["results"][:3]):
            print(f"  [{i+1}] source={r.get('source')} title={r.get('title', '')[:50]}...")
            print(f"       snippet={str(r.get('snippet', ''))[:80]}...")
            print(f"       link={r.get('link', '')[:60]}...")
    if result.get("summaries"):
        print("\nsummaries 首条预览 (前200字):")
        print("  ", (result["summaries"][0] or "")[:200])
    if not result.get("success"):
        err = result.get("error", "")
        if err == "未获取到任何搜索结果":
            print("\n提示: 百度/知乎可能无结果或需登录。可尝试:")
            print("  1) 诊断各源: python scripts/test_web_search_crawl_tool.py --diagnose")
            print("  2) 安装 duckduckgo-search 兜底: pip install duckduckgo-search")
            print("  3) 在 Agent 中可改用其他已注册搜索工具: advanced_web_search、或 Tavily MCP")
        if "proxy" in err.lower() or "ProxyError" in err:
            print("\n提示: 若因代理无法连接，可禁用代理后重试:")
            print("  $env:WEB_SEARCH_CRAWL_NO_PROXY=1; python scripts/test_web_search_crawl_tool.py")
    print("-" * 60)
    return result


def main():
    diagnose = False
    args = [a for a in sys.argv[1:] if a != "--diagnose"]
    if "--diagnose" in sys.argv[1:]:
        diagnose = True
    queries = list(DEFAULT_QUERIES)
    max_depth = 5
    if len(args) >= 1:
        if args[0].isdigit():
            max_depth = int(args[0])
        else:
            queries = [args[0]]
    if len(args) >= 2 and args[1].isdigit():
        max_depth = int(args[1])
    for q in queries:
        asyncio.run(run_test(q, max_depth, diagnose=diagnose))
        print()


if __name__ == "__main__":
    main()
