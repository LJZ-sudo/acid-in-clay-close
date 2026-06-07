"""文献查询缓存。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


def _cache_key(provider: str, query: str, page: int = 0) -> str:
    payload = json.dumps({"provider": provider, "query": query, "page": page}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


class LiteratureCache:
    def __init__(self, cache_dir: Path):
        self._dir = cache_dir / "literature_cache"
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, provider: str, query: str, page: int = 0) -> Optional[list[dict]]:
        key = _cache_key(provider, query, page)
        path = self._dir / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def put(self, provider: str, query: str, page: int, data: list[dict]) -> None:
        key = _cache_key(provider, query, page)
        path = self._dir / f"{key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> None:
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
