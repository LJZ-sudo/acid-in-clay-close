"""OA Fetcher — 通过 OpenAlex 召回开源 PDF，下载并登记到 registry。

路径 A 实现: 把 API 模式重新定位为"召回器"。下载的 PDF 被送入 manual 管道
 (inbox -> parse -> card -> evidence -> context) ，保持与 manual-strict 一条链。

工作流:
  1. 从 query 列表调 OpenAlexProvider.search()
  2. 过滤: 必须有 pdf_url + year 达标 + DOI 未在 registry 中
  3. 下载 PDF 到 literature_workspace/01_manual_inbox/{stage}/openalex_{id}.pdf
  4. paper_reader 预解析验证可读性 (不做完整 LLM 提取)
  5. 复制到 03_parsed_text/ 并登记 PaperRegistryEntry (manually_added=False,
     ingest_status="parsed", provider_metadata 存 OpenAlex 元数据)

下游 --rebuild-paper-cards / --rebuild-evidence-tables 会自动消费这些 entry。
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import requests

from s8_stage3.contracts.paper_registry import PaperRegistryEntry
from s8_stage3.literature.manual_ingest import LiteratureWorkspace
from s8_stage3.literature.paper_reader import read_paper
from s8_stage3.literature.providers.openalex_provider import OpenAlexProvider

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    queries_run: int = 0
    papers_returned: int = 0
    downloaded: int = 0
    skipped_no_pdf: int = 0
    skipped_dup_doi: int = 0
    skipped_too_old: int = 0
    skipped_too_large: int = 0
    skipped_bad_content: int = 0
    parse_failed: int = 0
    errors: list[str] = field(default_factory=list)

    def summary_line(self) -> str:
        return (
            f"queries={self.queries_run} returned={self.papers_returned} "
            f"downloaded={self.downloaded} "
            f"skipped(no_pdf={self.skipped_no_pdf}, dup_doi={self.skipped_dup_doi}, "
            f"old={self.skipped_too_old}, oversize={self.skipped_too_large}, "
            f"bad_content={self.skipped_bad_content}) "
            f"parse_failed={self.parse_failed}"
        )


_MAX_PDF_BYTES = 30 * 1024 * 1024  # 30 MB
_DOWNLOAD_TIMEOUT = 60
_VALID_CONTENT_TYPES = ("application/pdf", "application/octet-stream")


def _collect_existing_dois(registry) -> set[str]:
    """registry 中已登记的所有 DOI (规范小写) —— 用于跨批次 DOI 去重。"""
    dois: set[str] = set()
    for e in registry.all_entries():
        if e.doi:
            dois.add(e.doi.lower().strip())
    return dois


def _safe_paper_id(oa_source_url: str, title: str) -> str:
    """从 OpenAlex URL 提取 W-id，没有则用 title hash。"""
    if oa_source_url:
        tail = oa_source_url.rstrip("/").split("/")[-1]
        if tail and tail[0] in ("W", "w"):
            return f"openalex_{tail.lower()}"
    import hashlib
    return f"openalex_{hashlib.md5(title.lower().encode()).hexdigest()[:10]}"


def _download_pdf(
    url: str,
    dest: Path,
    timeout: int = _DOWNLOAD_TIMEOUT,
) -> tuple[bool, str]:
    """下载 PDF. 返回 (ok, reason).  ok=False 时 reason 表明跳过原因."""
    try:
        with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as r:
            r.raise_for_status()
            ctype = (r.headers.get("content-type") or "").lower()
            if not any(c in ctype for c in _VALID_CONTENT_TYPES):
                return False, f"bad_content_type:{ctype[:40]}"
            clen = r.headers.get("content-length")
            if clen and int(clen) > _MAX_PDF_BYTES:
                return False, f"too_large:{int(clen)}"
            written = 0
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > _MAX_PDF_BYTES:
                        f.close()
                        dest.unlink(missing_ok=True)
                        return False, f"too_large_stream:{written}"
                    f.write(chunk)
            return True, "ok"
    except requests.RequestException as e:
        return False, f"http_error:{type(e).__name__}:{str(e)[:80]}"


def fetch_and_download_oa_papers(
    queries: list[str],
    workspace: LiteratureWorkspace,
    stage_target: str,
    mailto: str = "",
    max_per_query: int = 5,
    max_total: int = 10,
    min_year: int = 2010,
) -> FetchResult:
    """OpenAlex 召回 → 下载 OA PDF → 登记 registry (manually_added=False).

    Parameters
    ----------
    stage_target : 's05_mechanism' | 's08_materials'
    """
    if stage_target not in ("s05_mechanism", "s08_materials"):
        raise ValueError(f"Invalid stage_target: {stage_target}")

    result = FetchResult()
    registry = workspace.get_registry()
    existing_dois = _collect_existing_dois(registry)
    logger.info(f"[OAFetch] registry has {len(existing_dois)} existing DOIs")

    inbox = workspace.inbox_dir / stage_target
    inbox.mkdir(parents=True, exist_ok=True)

    provider = OpenAlexProvider(mailto=mailto)
    seen_in_batch: set[str] = set()

    for q in queries:
        if result.downloaded >= max_total:
            logger.info(f"[OAFetch] max_total={max_total} reached, stop.")
            break
        result.queries_run += 1
        papers = provider.search(q, max_results=max_per_query, from_year=min_year)
        result.papers_returned += len(papers)

        for rec in papers:
            if result.downloaded >= max_total:
                break
            if not rec.pdf_url:
                result.skipped_no_pdf += 1
                continue
            if rec.year and rec.year < min_year:
                result.skipped_too_old += 1
                continue
            doi_norm = (rec.doi or "").lower().strip()
            if doi_norm and (doi_norm in existing_dois or doi_norm in seen_in_batch):
                result.skipped_dup_doi += 1
                continue

            paper_id = _safe_paper_id(rec.source_url, rec.title)
            if registry.has(paper_id):
                result.skipped_dup_doi += 1
                continue

            dest_inbox = inbox / f"{paper_id}.pdf"
            ok, reason = _download_pdf(rec.pdf_url, dest_inbox)
            if not ok:
                if reason.startswith("too_large"):
                    result.skipped_too_large += 1
                elif reason.startswith("bad_content"):
                    result.skipped_bad_content += 1
                else:
                    result.errors.append(f"{paper_id}: {reason}")
                    result.skipped_bad_content += 1
                continue

            try:
                parsed = read_paper(dest_inbox)
                if not parsed.full_text or len(parsed.full_text) < 500:
                    result.parse_failed += 1
                    dest_inbox.unlink(missing_ok=True)
                    continue
            except Exception as e:
                result.parse_failed += 1
                result.errors.append(f"{paper_id}: parse failed: {e}")
                dest_inbox.unlink(missing_ok=True)
                continue

            dest_parsed = workspace.parsed_text_dir / f"{paper_id}.pdf"
            try:
                shutil.copy2(str(dest_inbox), str(dest_parsed))
            except Exception as e:
                result.errors.append(f"{paper_id}: copy to parsed_text failed: {e}")
                continue

            authors_list = [
                a.strip()
                for a in (rec.authors or "").split(",")
                if a.strip() and a.strip().lower() != "et al."
            ]

            entry = PaperRegistryEntry(
                paper_id=paper_id,
                title=rec.title or parsed.title or paper_id,
                authors=authors_list,
                year=rec.year or parsed.year or None,
                venue=rec.venue or None,
                doi=rec.doi or None,
                source_stage=stage_target,
                local_path=str(dest_parsed.relative_to(workspace.base)),
                source_type="pdf",
                manually_added=False,
                ingest_status="parsed",
                provider_metadata={
                    "provider": "openalex",
                    "source_url": rec.source_url,
                    "pdf_url": rec.pdf_url,
                    "citation_count": rec.citation_count,
                    "matched_queries": [q],
                },
            )
            if doi_norm:
                entry.dedupe_key = f"doi:{doi_norm}"

            added = registry.add(entry)
            if not added:
                continue
            result.downloaded += 1
            if doi_norm:
                seen_in_batch.add(doi_norm)
                existing_dois.add(doi_norm)
            logger.info(
                f"[OAFetch] + {paper_id} | {rec.year} | {rec.title[:70]}"
            )

    registry.save()
    logger.info(f"[OAFetch] done: {result.summary_line()}")
    return result
