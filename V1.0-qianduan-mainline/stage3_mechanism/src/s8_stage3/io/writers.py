"""Structured output helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path | str, data: Any, *, indent: int = 2) -> Path:
    """Write JSON data and create parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(data, "model_dump"):
        obj = data.model_dump(mode="json")
    else:
        obj = data
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8")
    return p


def write_markdown(path: Path | str, content: str) -> Path:
    """Write Markdown text and create parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p
