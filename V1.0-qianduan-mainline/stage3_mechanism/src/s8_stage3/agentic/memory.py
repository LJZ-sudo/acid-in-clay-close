"""Episodic memory for the Stage 3 agent (Tier 3 / v2 capability).

An append-only, content-ordered store of pipeline events so later steps can
recall what earlier steps decided (a prerequisite for any non-linear / revisable
agent). Events are ordered by a monotonic ``seq`` counter rather than wall-clock
time, so the store is deterministic and never fabricates timestamps. Optional
JSON persistence is provided for cross-run recall.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union


@dataclass
class MemoryRecord:
    seq: int
    step: str
    key: str
    value: Any
    tags: List[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EpisodicMemory:
    """Append-only episodic memory keyed by ``(step, key)`` with recall."""

    def __init__(self, path: Optional[Union[str, Path]] = None):
        self._records: List[MemoryRecord] = []
        self._seq = 0
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            self._load()

    # -- writing ------------------------------------------------------------ #
    def record(
        self,
        step: str,
        key: str,
        value: Any,
        *,
        tags: Sequence[str] = (),
        note: str = "",
    ) -> MemoryRecord:
        rec = MemoryRecord(
            seq=self._seq,
            step=str(step),
            key=str(key),
            value=value,
            tags=list(tags),
            note=str(note),
        )
        self._records.append(rec)
        self._seq += 1
        return rec

    # -- reading ------------------------------------------------------------ #
    def recall(
        self,
        *,
        step: Optional[str] = None,
        key: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[MemoryRecord]:
        out = self._records
        if step is not None:
            out = [r for r in out if r.step == step]
        if key is not None:
            out = [r for r in out if r.key == key]
        if tag is not None:
            out = [r for r in out if tag in r.tags]
        return list(out)

    def latest(self, *, step: Optional[str] = None, key: Optional[str] = None) -> Optional[MemoryRecord]:
        matches = self.recall(step=step, key=key)
        return matches[-1] if matches else None

    def summary(self) -> Dict[str, Any]:
        by_step: Dict[str, int] = {}
        for r in self._records:
            by_step[r.step] = by_step.get(r.step, 0) + 1
        return {"n_records": len(self._records), "by_step": by_step, "next_seq": self._seq}

    def __len__(self) -> int:
        return len(self._records)

    # -- persistence -------------------------------------------------------- #
    def persist(self, path: Optional[Union[str, Path]] = None) -> Path:
        target = Path(path) if path else self._path
        if target is None:
            raise ValueError("EpisodicMemory.persist requires a path")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"next_seq": self._seq, "records": [r.to_dict() for r in self._records]}
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._path = target
        return target

    def _load(self) -> None:
        assert self._path is not None
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._records = [
            MemoryRecord(
                seq=int(r["seq"]),
                step=str(r["step"]),
                key=str(r["key"]),
                value=r.get("value"),
                tags=list(r.get("tags", [])),
                note=str(r.get("note", "")),
            )
            for r in data.get("records", [])
        ]
        self._seq = int(data.get("next_seq", len(self._records)))
