"""
WorkspaceFilesTool - list files/directories under the project workspace.

Security note:
- Only allows listing paths INSIDE the workspace root (no absolute paths, no '..' escape).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .tool_registry import BaseTool


def _safe_resolve(workspace_root: Path, rel_path: str) -> Path:
    rel_path = (rel_path or "").strip()
    if rel_path in {"", ".", "./"}:
        target = workspace_root
    else:
        # forbid absolute paths explicitly
        p = Path(rel_path)
        if p.is_absolute():
            raise ValueError("path must be relative to workspace root")
        target = (workspace_root / p).resolve()

    root = workspace_root.resolve()
    if root not in [target, *target.parents]:
        raise ValueError("path escapes workspace root")
    return target


def _list_dir(target: Path, max_items: int) -> Tuple[List[str], List[str], bool]:
    files: List[str] = []
    dirs: List[str] = []
    truncated = False

    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except Exception as e:
        raise RuntimeError(f"failed to list directory: {e}") from e

    if len(entries) > max_items:
        entries = entries[:max_items]
        truncated = True

    for p in entries:
        name = p.name + ("/" if p.is_dir() else "")
        if p.is_dir():
            dirs.append(name)
        else:
            files.append(name)
    return dirs, files, truncated


@dataclass
class WorkspaceFilesTool(BaseTool):
    """
    List workspace files/directories.

    Input:
      - str path: relative path under workspace root ("" or "." for root)
      - or dict: {"path": "...", "max_items": 200}
    """

    workspace_root: Path

    def __init__(self, workspace_root: Path):
        super().__init__(
            name="list_workspace_files",
            description=(
                "列出当前工作区(项目根目录)下的文件和文件夹。"
                "输入为相对路径（例如 '.', 'src', 'config'），不允许访问工作区之外的路径。"
            ),
        )
        self.workspace_root = workspace_root

    async def execute(self, input_data: Any) -> Dict[str, Any]:
        try:
            if isinstance(input_data, dict):
                rel = str(input_data.get("path") or ".")
                max_items = int(input_data.get("max_items") or 200)
            else:
                rel = str(input_data or ".")
                max_items = 200

            max_items = max(1, min(max_items, 2000))
            target = _safe_resolve(self.workspace_root, rel)

            if not target.exists():
                return {"success": False, "error": f"path_not_found: {rel}"}
            if not target.is_dir():
                return {
                    "success": True,
                    "result": {
                        "path": rel,
                        "type": "file",
                        "name": target.name,
                    },
                }

            dirs, files, truncated = _list_dir(target, max_items=max_items)
            return {
                "success": True,
                "result": {
                    "path": rel,
                    "type": "directory",
                    "dirs": dirs,
                    "files": files,
                    "truncated": truncated,
                    "max_items": max_items,
                },
            }
        except Exception as e:
            logger.warning(f"WorkspaceFilesTool failed: {e}")
            return {"success": False, "error": str(e)}

