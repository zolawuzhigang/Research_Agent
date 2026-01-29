"""
Skill loader - scans src/skills for python modules and loads tool objects.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, List
from loguru import logger

from .skill_model import SkillDocument, parse_skill_md


def load_skill_tools(skills_dir: Path) -> List[Any]:
    """
    Load Python-based skill tools for backward-compatibility.
    Expected pattern: each .py exposes TOOL or TOOLS compatible with BaseTool.
    """
    tools: List[Any] = []
    if not skills_dir.exists():
        return tools

    # 仅加载“可执行 skill 工具”模块；跳过内部支撑模块（否则会出现相对导入错误/重复加载）。
    skip = {"__init__.py", "loader.py", "skill_model.py", "skill_tool.py"}
    for py in skills_dir.glob("*.py"):
        if py.name in skip:
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"skills.{py.stem}", str(py))
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore

            if hasattr(module, "TOOLS"):
                for t in getattr(module, "TOOLS"):
                    tools.append(t)
            if hasattr(module, "TOOL"):
                tools.append(getattr(module, "TOOL"))

            logger.info(f"Loaded skills from {py.name}")
        except Exception as e:
            logger.warning(f"Failed to load skill module {py.name}: {e}")
            continue

    return tools


def load_skills_from_skillmd(skills_root: Path) -> List[SkillDocument]:
    """
    Discover Claude-style skills defined by SKILL.md under skills_root/*/SKILL.md.
    Only parses metadata and lightweight sections; heavy content is handled lazily by SkillTool.
    """
    docs: List[SkillDocument] = []
    if not skills_root.exists():
        return docs

    # Each subdirectory with SKILL.md is a skill
    for skill_dir in skills_root.iterdir():
        if not skill_dir.is_dir():
            continue
        md_path = skill_dir / "SKILL.md"
        if not md_path.exists():
            continue
        try:
            doc = parse_skill_md(md_path)
            if doc:
                docs.append(doc)
        except Exception as e:
            logger.warning(f"Failed to parse SKILL.md in {skill_dir}: {e}")
            continue

    return docs
