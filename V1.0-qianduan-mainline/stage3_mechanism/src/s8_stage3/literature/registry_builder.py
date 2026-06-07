"""Registry Builder — 统一管理 paper_registry.json 的增删查改。

为每篇文献分配唯一 paper_id，维护 ingest_status 生命周期，
支持增量导入和与 deduper 协作。
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from pathlib import Path

from s8_stage3.contracts.paper_registry import PaperRegistryEntry

logger = logging.getLogger(__name__)


class PaperRegistry:
    def __init__(self, registry_dir: Path):
        self._dir = Path(registry_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._json_path = self._dir / "paper_registry.json"
        self._csv_path = self._dir / "paper_registry.csv"
        self._entries: dict[str, PaperRegistryEntry] = {}
        self._load()

    def _load(self) -> None:
        if self._json_path.exists():
            try:
                data = json.loads(self._json_path.read_text(encoding="utf-8"))
                for item in data:
                    try:
                        entry = PaperRegistryEntry(**item)
                        self._entries[entry.paper_id] = entry
                    except Exception as e:
                        logger.warning(f"[Registry] Bad entry: {e}")
            except Exception as e:
                logger.warning(f"[Registry] Load error: {e}")
        logger.info(f"[Registry] Loaded {len(self._entries)} entries")

    def save(self) -> None:
        data = [e.model_dump() for e in self._entries.values()]
        self._json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._save_csv()
        logger.info(f"[Registry] Saved {len(data)} entries")

    def _save_csv(self) -> None:
        if not self._entries:
            return
        fields = ["paper_id", "title", "year", "doi", "source_stage",
                  "source_type", "ingest_status", "manually_added", "local_path"]
        with open(self._csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for e in self._entries.values():
                writer.writerow(e.model_dump())

    def get(self, paper_id: str) -> PaperRegistryEntry | None:
        return self._entries.get(paper_id)

    def has(self, paper_id: str) -> bool:
        return paper_id in self._entries

    def all_entries(self) -> list[PaperRegistryEntry]:
        return list(self._entries.values())

    def by_status(self, status: str) -> list[PaperRegistryEntry]:
        return [e for e in self._entries.values() if e.ingest_status == status]

    def by_stage(self, stage: str) -> list[PaperRegistryEntry]:
        return [e for e in self._entries.values()
                if e.source_stage == stage or e.source_stage == "shared"]

    def add(self, entry: PaperRegistryEntry) -> bool:
        """添加条目。如果 paper_id 已存在则跳过，返回 False。"""
        if entry.paper_id in self._entries:
            return False
        if not entry.dedupe_key:
            entry.dedupe_key = entry.computed_dedupe_key
        self._entries[entry.paper_id] = entry
        return True

    def update_status(self, paper_id: str, new_status: str) -> None:
        if paper_id in self._entries:
            self._entries[paper_id].ingest_status = new_status

    def find_by_dedupe_key(self, key: str) -> PaperRegistryEntry | None:
        for e in self._entries.values():
            if e.dedupe_key == key or e.computed_dedupe_key == key:
                return e
        return None

    def generate_paper_id(self, title: str, source: str = "manual") -> str:
        """生成唯一 paper_id，避免冲突。"""
        base = hashlib.md5(title.lower().strip().encode()).hexdigest()[:10]
        candidate = f"{source}_{base}"
        counter = 0
        while candidate in self._entries:
            counter += 1
            candidate = f"{source}_{base}_{counter}"
        return candidate

    @property
    def count(self) -> int:
        return len(self._entries)
