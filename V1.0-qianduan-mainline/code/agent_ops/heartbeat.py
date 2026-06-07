from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def write_heartbeat(
    stage: str,
    status: str = "alive",
    *,
    extra: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Overwrite agent_heartbeat.json with last-seen stage and UTC time.

    Intended for cheap file-based monitoring (CI, humans, or a tiny watcher).
    """
    root = project_root or Path(__file__).resolve().parent.parent.parent
    path = root / "output" / "agent_ops" / "agent_heartbeat.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "stage": stage,
        "status": status,
    }
    if extra:
        body["extra"] = extra
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
