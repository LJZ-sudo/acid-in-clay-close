"""OpenAlex API provider — 免费学术文献搜索。

https://docs.openalex.org/
无需 API key，建议提供 mailto 以获得 polite pool 更高速率。
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional
from urllib.parse import quote

import requests

from s8_stage3.contracts.paper import PaperRecord

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openalex.org"
_RATE_LIMIT_DELAY = 0.12  # polite pool ~10 req/s


class OpenAlexProvider:
    def __init__(self, mailto: str = "", timeout: int = 30):
        self._mailto = mailto
        self._timeout = timeout
        self._session = requests.Session()
        if mailto:
            self._session.params = {"mailto": mailto}

    def search(
        self,
        query: str,
        max_results: int = 10,
        from_year: Optional[int] = None,
    ) -> list[PaperRecord]:
        params: dict = {
            "search": query,
            "per_page": min(max_results, 50),
            "sort": "relevance_score:desc",
            "select": "id,title,authorships,publication_year,doi,primary_location,cited_by_count,abstract_inverted_index,type",
        }
        if from_year:
            params["filter"] = f"from_publication_date:{from_year}-01-01"

        try:
            time.sleep(_RATE_LIMIT_DELAY)
            resp = self._session.get(
                f"{_BASE_URL}/works",
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning(f"[OpenAlex] search failed for '{query[:60]}': {e}")
            return []

        results = data.get("results", [])
        records = []
        for item in results[:max_results]:
            record = self._parse_work(item, query)
            if record:
                records.append(record)
        logger.info(f"[OpenAlex] '{query[:40]}...' -> {len(records)} papers")
        return records

    def _parse_work(self, item: dict, query: str) -> Optional[PaperRecord]:
        try:
            oa_id = item.get("id", "")
            paper_id = oa_id.split("/")[-1] if oa_id else hashlib.md5(str(item).encode()).hexdigest()[:12]

            authors_list = item.get("authorships", [])
            authors = ", ".join(
                a.get("author", {}).get("display_name", "")
                for a in authors_list[:5]
            )
            if len(authors_list) > 5:
                authors += " et al."

            abstract = self._reconstruct_abstract(item.get("abstract_inverted_index"))

            primary = item.get("primary_location") or {}
            pdf_url = ""
            source = primary.get("source") or {}
            venue = source.get("display_name", "")
            if primary.get("is_oa"):
                pdf_url = primary.get("pdf_url", "") or ""

            return PaperRecord(
                paper_id=paper_id,
                title=item.get("title", "") or "",
                authors=authors,
                year=item.get("publication_year", 0) or 0,
                venue=venue,
                doi=(item.get("doi") or "").replace("https://doi.org/", ""),
                abstract=abstract[:2000],
                source_provider="openalex",
                source_url=oa_id,
                citation_count=item.get("cited_by_count", 0) or 0,
                pdf_url=pdf_url,
                relevance_score=0.0,
                matched_queries=[query],
            )
        except Exception as e:
            logger.debug(f"[OpenAlex] parse error: {e}")
            return None

    @staticmethod
    def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
        if not inverted_index:
            return ""
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions)
