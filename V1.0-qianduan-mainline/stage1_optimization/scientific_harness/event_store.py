# -*- coding: utf-8 -*-
"""事件溯源:append-only SHA256 链式账本（M5-A）。

所有物理/计量/认知提交事件不可变追加,每条 entry_hash=sha256(parent_hash+payload_sha256);
与 three_pillars v2 的 verify_append_only_chain 同构,可事后验链。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class EventStore:
    def __init__(self):
        self._events: List[Dict[str, Any]] = []
        self._head: str = "GENESIS"

    def append(self, event_type: str, payload: Dict[str, Any]) -> str:
        payload_sha = _sha(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8"))
        entry_hash = _sha((self._head + payload_sha).encode("utf-8"))
        entry = {
            "seq": len(self._events),
            "event_type": event_type,
            "at": datetime.now(timezone.utc).astimezone().isoformat(),
            "payload": payload,
            "payload_sha256": payload_sha,
            "parent_hash": self._head,
            "entry_hash": entry_hash,
        }
        self._events.append(entry)
        self._head = entry_hash
        return entry_hash

    def events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if event_type is None:
            return list(self._events)
        return [e for e in self._events if e["event_type"] == event_type]

    def verify_chain(self) -> bool:
        head = "GENESIS"
        for e in self._events:
            if e["parent_hash"] != head:
                return False
            recomputed = _sha((head + e["payload_sha256"]).encode("utf-8"))
            if recomputed != e["entry_hash"]:
                return False
            head = e["entry_hash"]
        return True
