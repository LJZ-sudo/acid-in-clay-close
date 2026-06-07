"""调试快照：在 debug 模式下将中间结果写入 snapshots/ 目录。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_SNAPSHOT_DIR = Path(__file__).parent.parent.parent.parent / "outputs" / "stage3" / "_snapshots"


def dump_snapshot(step_id: str, data: Any, enabled: bool = False) -> None:
    """若 enabled 为 True（或环境变量 STAGE3_DEBUG_SNAPSHOTS=true），写快照文件。"""
    if not enabled:
        enabled = os.getenv("STAGE3_DEBUG_SNAPSHOTS", "false").lower() in ("1", "true", "yes")
    if not enabled:
        return
    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _SNAPSHOT_DIR / f"{step_id}.json"
    obj = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
