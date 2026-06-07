"""从 src/s8_stage3/prompts/ 目录加载 prompt 文本。"""

from __future__ import annotations

import hashlib
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptNotFoundError(FileNotFoundError):
    pass


def load_prompt(name: str) -> str:
    """加载 prompt 文件，name 不含扩展名，如 's04_hypothesis_generator'。"""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise PromptNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def prompt_path(name: str) -> Path:
    """返回 prompt 文件路径，name 不含扩展名。"""
    return _PROMPTS_DIR / f"{name}.md"


def prompt_sha256(name: str) -> str:
    """计算 prompt 文件内容 sha256。"""
    path = prompt_path(name)
    if not path.exists():
        raise PromptNotFoundError(f"Prompt not found: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_manifest() -> list[dict]:
    """列出所有 prompt 文件的路径和 hash。"""
    manifest = []
    for path in sorted(_PROMPTS_DIR.glob("*.md")):
        manifest.append({
            "name": path.stem,
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return manifest


def list_prompts() -> list[str]:
    return [p.stem for p in sorted(_PROMPTS_DIR.glob("*.md"))]
