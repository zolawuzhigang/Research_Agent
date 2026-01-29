"""
Skill metadata & document model for Claude-style Agent Skills (SKILL.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

import re
import yaml
from loguru import logger


@dataclass
class SkillMeta:
    name: str
    description: str
    license: Optional[str] = None
    raw_meta: Dict[str, Any] = None


@dataclass
class SkillDocument:
    meta: SkillMeta
    path: Path
    full_text: str
    instructions: str
    examples: str = ""
    guidelines: str = ""


def _split_front_matter(text: str) -> (str, str):
    """
    Split YAML front-matter and body.
    Returns (yaml_text, body_text). If no front-matter, yaml_text is "".
    """
    if text.startswith("---"):
        # Look for second '---'
        match = re.search(r"^---\s*$", text, flags=re.MULTILINE)
        if not match:
            return "", text
        start = match.end()
        match2 = re.search(r"^---\s*$", text[start:], flags=re.MULTILINE)
        if not match2:
            # Typical SKILL.md only has one '---' at top and then body, treat until first blank line
            # Fallback: split at first newline after first '---'
            lines = text.splitlines()
            if len(lines) >= 2 and lines[0].strip() == "---":
                # No closing '---', assume single-block yaml header until empty line
                yaml_lines = []
                body_lines = []
                in_yaml = True
                for line in lines[1:]:
                    if in_yaml and line.strip() == "":
                        in_yaml = False
                        continue
                    if in_yaml:
                        yaml_lines.append(line)
                    else:
                        body_lines.append(line)
                return "\n".join(yaml_lines), "\n".join(body_lines)
            return "", text
        yaml_text = text[start:start + match2.start()]
        body = text[start + match2.end():]
        return yaml_text.strip(), body.lstrip()
    return "", text


def parse_skill_md(path: Path) -> Optional[SkillDocument]:
    """
    Parse a SKILL.md file into SkillDocument.
    Only meta is required; body is treated as instructions text with simple section splitting.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read SKILL.md at {path}: {e}")
        return None

    yaml_text, body = _split_front_matter(raw)

    meta_dict: Dict[str, Any] = {}
    if yaml_text:
        try:
            meta_dict = yaml.safe_load(yaml_text) or {}
        except Exception as e:
            logger.warning(f"Failed to parse YAML front-matter in {path}: {e}")

    name = meta_dict.get("name")
    desc = meta_dict.get("description") or meta_dict.get("desc") or ""
    if not name:
        logger.warning(f"SKILL.md at {path} missing 'name' in front-matter, skipping")
        return None
    if not desc:
        desc = f"Skill loaded from {path.name}"

    meta = SkillMeta(
        name=str(name),
        description=str(desc),
        license=meta_dict.get("license"),
        raw_meta=meta_dict,
    )

    # Split sections in body by headings: ## Instructions / ## Examples / ## Guidelines
    instructions = body
    examples = ""
    guidelines = ""

    # Simple regex-based split
    sections = re.split(r"(?m)^##\s+", body)
    if len(sections) > 1:
        # First chunk (before first ##) is usually title/overview; keep in instructions
        header = sections[0]
        rest = sections[1:]
        instr_chunks = [header]
        for sec in rest:
            # sec starts with section title line
            lines = sec.splitlines()
            if not lines:
                continue
            title = lines[0].strip().lower()
            content = "\n".join(lines[1:])
            if "instruction" in title:
                instr_chunks.append(content)
            elif "example" in title:
                examples += content + "\n"
            elif "guideline" in title or "rule" in title:
                guidelines += content + "\n"
            else:
                # default to instructions
                instr_chunks.append(sec)
        instructions = "\n\n".join([c for c in instr_chunks if c.strip()])

    doc = SkillDocument(
        meta=meta,
        path=path,
        full_text=raw,
        instructions=instructions.strip(),
        examples=examples.strip(),
        guidelines=guidelines.strip(),
    )
    logger.info(f"Parsed SKILL.md: {meta.name} ({path})")
    return doc

