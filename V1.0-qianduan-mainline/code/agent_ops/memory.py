from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def append_memory_event(
    event_type: str,
    payload: Dict[str, Any],
    *,
    log_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Append one JSON line to agent_memory.jsonl (create parent dirs as needed).

    event_type: short label, e.g. "stage1_recipe", "virtual_oracle_match", "stage3_step".
    payload: must be JSON-serializable.
    """
    root = project_root or Path(__file__).resolve().parent.parent.parent
    path = log_path or (root / "output" / "agent_ops" / "agent_memory.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "type": event_type,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
