"""
MCP loader - load MCP tools from config.

For this demo we support a simple "http_json" MCP tool definition:
{
  "name": "tool_name",
  "type": "http_json",
  "url": "http://host/path",
  "method": "POST",
  "timeout": 10
}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
from loguru import logger


class HttpJsonMcpTool:
    """A lightweight MCP tool wrapper calling an HTTP JSON endpoint."""

    def __init__(self, name: str, description: str, url: str, method: str = "POST", timeout: int = 10):
        self.name = name
        self.description = description
        self.url = url
        self.method = method.upper()
        self.timeout = timeout

        try:
            import requests
            self._requests = requests
        except Exception as e:
            self._requests = None
            logger.warning(f"requests not available for MCP tool {name}: {e}")

    async def execute(self, input_data: Any) -> Dict[str, Any]:
        if self._requests is None:
            return {"success": False, "error": "requests_not_available"}

        payload = {"input": input_data}
        try:
            if self.method == "GET":
                r = self._requests.get(self.url, params=payload, timeout=self.timeout)
            else:
                r = self._requests.post(self.url, json=payload, timeout=self.timeout)
            if r.status_code >= 400:
                return {"success": False, "error": f"http_{r.status_code}", "body": r.text[:300]}
            data = r.json()
            # normalize
            if isinstance(data, dict) and "success" in data:
                return data
            return {"success": True, "result": data}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ConfigOnlyMcpTool:
    """
    A lightweight MCP tool that simply exposes MCP server config loaded from a JSON file.
    用于“能不能识别 MCP 配置并集成进 ToolHub”的集成检测，而不是实际发 HTTP 请求。
    """

    def __init__(self, name: str, description: str, server_config: Dict[str, Any]):
        self.name = name
        self.description = description
        self.server_config = server_config

    async def execute(self, input_data: Any) -> Dict[str, Any]:
        # 仅回显配置与输入，方便测试
        return {
            "success": True,
            "result": {
                "echo_input": input_data,
                "server_config": self.server_config,
            },
        }


def load_mcp_tools(mcp_config: Dict[str, Any]) -> List[Any]:
    tools: List[Any] = []
    logger.debug(f"load_mcp_tools called with config: {mcp_config}")
    enabled = bool(mcp_config.get("enabled", False))
    if not enabled:
        return tools

    # 优先：从单独的 MCP 配置文件加载（格式参考 ~/.cursor/mcp.json）
    config_file = mcp_config.get("config_file")
    if config_file:
        try:
            cfg_path = Path(config_file)
            if not cfg_path.is_absolute():
                # 相对项目根目录（src/mcps/loader.py -> .../src/mcps -> project_root）
                project_root = Path(__file__).resolve().parents[2]
                cfg_path = project_root / cfg_path
            logger.debug(f"MCP config_file resolved path: {cfg_path}")
            if not cfg_path.exists():
                logger.warning(f"MCP config_file not found: {cfg_path}")
            else:
                # 使用 utf-8-sig 以兼容带 BOM 的文件
                raw = cfg_path.read_text(encoding="utf-8-sig")
                try:
                    data = json.loads(raw)
                except Exception:
                    # 容错：去掉首尾空白后再尝试一次
                    data = json.loads(raw.strip())
                servers = (data.get("mcpServers") or {}) if isinstance(data, dict) else {}
                for server_name, server_cfg in servers.items():
                    desc = f"MCP server from config_file: {server_name}"
                    tool = ConfigOnlyMcpTool(
                        name=server_name,
                        description=desc,
                        server_config=server_cfg or {},
                    )
                    tools.append(tool)
                    logger.info(f"Loaded MCP server from config_file as tool: {server_name}")
        except Exception as e:
            logger.warning(f"Failed to load MCP tools from config_file: {e}")

    # 兼容旧版：直接从 mcps.tools 数组中加载 http_json 工具
    for item in (mcp_config.get("tools") or []):
        try:
            t_type = (item.get("type") or "").lower()
            name = item.get("name")
            if not name:
                continue
            desc = item.get("description") or f"MCP tool: {name}"
            if t_type == "http_json":
                tool = HttpJsonMcpTool(
                    name=name,
                    description=desc,
                    url=item.get("url", ""),
                    method=item.get("method", "POST"),
                    timeout=int(item.get("timeout", 10)),
                )
                tools.append(tool)
            else:
                logger.warning(f"Unknown MCP tool type: {t_type} ({name})")
        except Exception as e:
            logger.warning(f"Failed to load MCP tool: {e}")
            continue

    return tools

