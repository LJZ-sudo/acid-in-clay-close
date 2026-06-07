"""Manual Literature Ingest — 从 inbox 导入手动下载的论文到 registry。

工作流:
  1. 用户将 PDF/TXT/MD/JSON 文件放入 literature_workspace/01_manual_inbox/{stage}/
  2. 调用 ingest_inbox() 自动:
     a. 用 paper_reader 解析文件获取元数据
     b. 生成 PaperRegistryEntry 注册到 registry
     c. 将原文件复制到 03_parsed_text/
  3. registry 可供后续 paper_card_builder 消费
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from s8_stage3.contracts.paper_registry import PaperRegistryEntry
from s8_stage3.literature.paper_reader import (
    ParsedPaper,
    read_paper,
    SUPPORTED_EXTENSIONS,
)
from s8_stage3.literature.registry_builder import PaperRegistry

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    total_files: int = 0
    success: int = 0
    failed: int = 0
    skipped_duplicate: int = 0
    errors: list[str] = field(default_factory=list)


class LiteratureWorkspace:
    """管理 literature_workspace 的完整目录结构。"""

    def __init__(self, base_dir: Path):
        self._base = Path(base_dir)
        self._ensure_dirs()

    @property
    def base(self) -> Path:
        return self._base

    @property
    def query_packets_dir(self) -> Path:
        return self._base / "00_query_packets"

    @property
    def inbox_dir(self) -> Path:
        return self._base / "01_manual_inbox"

    @property
    def registry_dir(self) -> Path:
        return self._base / "02_registry"

    @property
    def parsed_text_dir(self) -> Path:
        return self._base / "03_parsed_text"

    @property
    def paper_cards_dir(self) -> Path:
        return self._base / "04_paper_cards"

    @property
    def evidence_rows_dir(self) -> Path:
        return self._base / "05_evidence_rows"

    @property
    def curated_tables_dir(self) -> Path:
        return self._base / "06_curated_tables"

    @property
    def context_packs_dir(self) -> Path:
        return self._base / "07_context_packs"

    def _ensure_dirs(self):
        for d in [
            self.query_packets_dir / "s05_mechanism",
            self.query_packets_dir / "s08_materials",
            self.inbox_dir / "s05_mechanism",
            self.inbox_dir / "s08_materials",
            self.registry_dir,
            self.parsed_text_dir,
            self.paper_cards_dir / "mechanism",
            self.paper_cards_dir / "materials",
            self.evidence_rows_dir / "mechanism",
            self.evidence_rows_dir / "materials",
            self.curated_tables_dir,
            self.context_packs_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def get_registry(self) -> PaperRegistry:
        return PaperRegistry(self.registry_dir)

    def get_inbox_files(self, stage: str = "") -> list[tuple[Path, str]]:
        """返回 (file_path, source_stage) 列表。"""
        files = []
        stages = [stage] if stage else ["s05_mechanism", "s08_materials"]
        for s in stages:
            inbox = self.inbox_dir / s
            if inbox.is_dir():
                for f in sorted(inbox.iterdir()):
                    if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                        files.append((f, s))
        # 也检查 inbox 根目录（通用文献）
        for f in sorted(self.inbox_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append((f, "shared"))
        return files


def _parsed_to_registry_entry(
    parsed: ParsedPaper,
    paper_id: str,
    source_stage: str,
    local_path: str,
) -> PaperRegistryEntry:
    authors = []
    if parsed.authors:
        authors = [a.strip() for a in parsed.authors.split(",") if a.strip()]

    return PaperRegistryEntry(
        paper_id=paper_id,
        title=parsed.title or Path(parsed.source_path).stem,
        authors=authors,
        year=parsed.year or None,
        doi=None,
        source_stage=source_stage,
        local_path=local_path,
        source_type=Path(parsed.source_path).suffix.lstrip(".").lower() or "unknown",
        manually_added=True,
        ingest_status="parsed",
    )


def ingest_inbox(
    workspace: LiteratureWorkspace,
    stage: str = "",
    copy_to_parsed: bool = True,
) -> IngestResult:
    """处理 inbox 中的所有文件，注册到 registry。"""
    result = IngestResult()
    registry = workspace.get_registry()
    files = workspace.get_inbox_files(stage)
    result.total_files = len(files)

    if not files:
        logger.info("[Ingest] Inbox is empty.")
        return result

    logger.info(f"[Ingest] Processing {len(files)} files...")

    for file_path, source_stage in files:
        try:
            parsed = read_paper(file_path)
            title = parsed.title or file_path.stem
            paper_id = registry.generate_paper_id(title, source="manual")

            dedupe_key = PaperRegistryEntry(
                paper_id="tmp", title=title, year=parsed.year
            ).computed_dedupe_key
            existing = registry.find_by_dedupe_key(dedupe_key)
            if existing:
                result.skipped_duplicate += 1
                logger.info(f"[Ingest] Duplicate: {file_path.name} -> {existing.paper_id}")
                continue

            dest_name = f"{paper_id}{file_path.suffix}"
            local_rel = dest_name
            if copy_to_parsed:
                dest = workspace.parsed_text_dir / dest_name
                shutil.copy2(str(file_path), str(dest))
                local_rel = str(dest.relative_to(workspace.base))

            entry = _parsed_to_registry_entry(parsed, paper_id, source_stage, local_rel)
            entry.dedupe_key = dedupe_key
            registry.add(entry)
            result.success += 1

            if parsed.parse_warnings:
                for w in parsed.parse_warnings:
                    logger.warning(f"[Ingest] {file_path.name}: {w}")

            logger.info(f"[Ingest] OK: {file_path.name} -> {paper_id} ({source_stage})")

        except Exception as e:
            result.failed += 1
            result.errors.append(f"{file_path.name}: {e}")
            logger.error(f"[Ingest] FAILED: {file_path.name}: {e}")

    registry.save()
    logger.info(
        f"[Ingest] Done: {result.success} new, "
        f"{result.skipped_duplicate} dup, {result.failed} failed"
    )
    return result
