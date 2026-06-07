"""Offline, deterministic OpenAlex-shaped provider for the Phase B dry-run.

dry-run only, no scientific claim, v2 remains HOLD.

This provider implements the same ``.search(query, max_results, from_year)``
interface that ``s08_literature_scout_materials._fetch_api_cards`` expects from a
real :class:`OpenAlexProvider`, but it performs NO network I/O. It returns a
fixed set of clearly-synthetic records so the S08 "api" branch can be exercised
end-to-end offline.

Every record is stamped ``synthetic_not_real_evidence`` in its title, abstract
and a ``_marker`` attribute. These are NOT real papers and MUST NOT be cited as
literature evidence. The records exist solely to prove the api-mode plumbing
works without a live OpenAlex connection.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import List, Optional

SYNTHETIC_MARKER = "synthetic_not_real_evidence"


def _record(paper_id: str, title: str, abstract: str, year: int, query: str) -> SimpleNamespace:
    # OpenAlex-shaped record. _fetch_api_cards reads paper_id/title/authors/
    # year/doi/abstract via getattr, so a SimpleNamespace is interface-complete
    # while avoiding any coupling to the pydantic PaperRecord contract.
    return SimpleNamespace(
        paper_id=paper_id,
        title=f"[{SYNTHETIC_MARKER}] {title}",
        authors="Synthetic A, Synthetic B",
        year=year,
        venue=f"{SYNTHETIC_MARKER} venue (not real)",
        doi="",  # intentionally empty: these are not real DOIs
        abstract=f"{abstract} ({SYNTHETIC_MARKER}; do not cite).",
        source_provider="fake_offline_provider",
        source_url=f"synthetic://{paper_id}",
        citation_count=0,
        pdf_url="",
        relevance_score=0.0,
        matched_queries=[query],
        _marker=SYNTHETIC_MARKER,
    )


# A small, fixed pool of clearly-synthetic "papers". The components named here
# (starch, attapulgite, phosphoric acid, ...) match the synthetic descriptor
# vocabulary so the offline api run produces non-empty, schema-valid cards.
_POOL = [
    (
        "SYN-W001",
        "OH-rich biopolymer host for proton transport",
        "A synthetic placeholder describing an OH-rich starch host with hydrogen-bond sites",
        2021,
    ),
    (
        "SYN-W002",
        "One-dimensional clay confinement of acid phases",
        "A synthetic placeholder describing attapulgite 1-D confinement of an acid phase",
        2022,
    ),
    (
        "SYN-W003",
        "Retained phosphoric acid as a mobile proton carrier",
        "A synthetic placeholder describing phosphoric acid acting as a proton donor carrier",
        2023,
    ),
]


class FakeOpenAlexProvider:
    """Offline provider with the OpenAlex ``.search`` interface.

    Deterministic: returns the canned pool for the FIRST query only (so the S08
    de-dupe path is exercised), and an empty list for subsequent queries, mirroring
    the real provider's behaviour under a narrow result set.
    """

    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def search(
        self,
        query: str,
        max_results: int = 10,
        from_year: Optional[int] = None,
    ) -> List[SimpleNamespace]:
        self.calls.append((query, max_results, from_year))
        if len(self.calls) != 1:
            return []
        records = [
            _record(pid, title, abstract, year, query)
            for (pid, title, abstract, year) in _POOL
        ]
        return records[: max(0, int(max_results))] if max_results else records
