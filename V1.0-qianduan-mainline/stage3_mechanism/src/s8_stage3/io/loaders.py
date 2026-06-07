"""JSON / CSV 加载工具，统一处理编码与错误。"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path | str) -> Any:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSON file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_csv_dicts(path: Path | str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV file not found: {p}")
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_text(path: Path | str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Text file not found: {p}")
    return p.read_text(encoding="utf-8")
