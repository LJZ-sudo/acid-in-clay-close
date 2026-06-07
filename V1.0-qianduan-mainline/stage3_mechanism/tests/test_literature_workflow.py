"""Literature workflow 全链测试。"""

import json
import pytest
from pathlib import Path

from s8_stage3.contracts.query_packet import QueryPacket, QuerySpec
from s8_stage3.contracts.paper_registry import PaperRegistryEntry
from s8_stage3.contracts.paper_card import PaperCard, TraceSpan
from s8_stage3.contracts.evidence_row import EvidenceRow, CuratedEvidenceTable
from s8_stage3.contracts.context_pack import ContextPack


# ── Contracts ──

class TestContracts:
    def test_query_packet_roundtrip(self):
        packet = QueryPacket(
            packet_id="QP-TEST-001",
            stage_target="s05_mechanism",
            focus_question="Test question",
            search_queries=[QuerySpec(
                query_id="QM01", intent="test", query_text="proton mechanism",
            )],
            stop_rule="stop after 5",
        )
        data = json.loads(packet.model_dump_json())
        assert data["packet_id"] == "QP-TEST-001"
        assert len(data["search_queries"]) == 1

    def test_registry_entry_dedupe_key(self):
        entry = PaperRegistryEntry(
            paper_id="test_001",
            title="Proton Transport in Hydrogels",
            year=2023,
        )
        assert entry.computed_dedupe_key.startswith("titleyear:")
        entry_doi = PaperRegistryEntry(
            paper_id="test_002", doi="10.1234/test",
        )
        assert entry_doi.computed_dedupe_key.startswith("doi:")

    def test_paper_card_creation(self):
        card = PaperCard(
            paper_id="p001",
            stage_target="mechanism",
            bibliography={"title": "Test", "year": 2023},
            mechanism_relevant_findings=["Finding 1"],
            trace_spans=[TraceSpan(page=1, section="Intro", text_snippet="test")],
        )
        assert card.paper_id == "p001"
        assert len(card.mechanism_relevant_findings) == 1

    def test_s08_material_summary_uses_current_paper_card_schema(self):
        from s8_stage3.agents.s08_literature_scout_materials import _paper_card_material_summary

        card = PaperCard(
            paper_id="p001",
            stage_target="materials",
            bibliography={"title": "Material Card", "year": 2024},
            mechanism_relevant_findings=["H-bonded polymer network supports proton transport."],
            arrhenius_vtf_findings=["Ea is low in the high-temperature segment."],
            numerical_findings=[{"metric": "conductivity", "value": "1e-2", "unit": "S/cm"}],
        )
        summary = _paper_card_material_summary(card)
        assert "H-bonded polymer network" in summary
        assert "Ea is low" in summary

    def test_s08_material_card_selection_drops_low_relevance_and_empty_cards(self):
        from s8_stage3.agents.s08_literature_scout_materials import _select_material_paper_cards

        keep = PaperCard(
            paper_id="keep",
            stage_target="materials",
            relevance_judgement={"score": 0.8, "reason": "relevant"},
            mechanism_relevant_findings=["PVA provides a hydrogen-bonded proton pathway."],
        )
        low = PaperCard(
            paper_id="low",
            stage_target="materials",
            relevance_judgement={"score": 0.0, "reason": "unrelated"},
            mechanism_relevant_findings=["Unrelated adsorbent behavior."],
        )
        empty = PaperCard(
            paper_id="empty",
            stage_target="materials",
            relevance_judgement={"score": 0.9, "reason": "relevant but empty"},
        )

        selected = _select_material_paper_cards([keep, low, empty], min_relevance=0.3)

        assert [card.paper_id for card in selected] == ["keep"]

    def test_evidence_row_creation(self):
        row = EvidenceRow(
            row_id="ER-0001",
            paper_id="p001",
            stage_target="mechanism",
            evidence_type="mechanism_claim",
            claim_text="Proton hopping is dominant above 60C",
        )
        assert row.confidence == 0.5
        assert row.evidence_type == "mechanism_claim"

    def test_context_pack_creation(self):
        pack = ContextPack(
            pack_id="ctx-s05",
            stage_target="s05",
            included_row_ids=["ER-0001"],
            summary="Test",
        )
        assert pack.pack_id == "ctx-s05"


# ── Query Packet Builder ──

class TestQueryPacketBuilder:
    def test_mechanism_query_packet(self):
        from s8_stage3.literature.query_packet_builder import build_mechanism_query_packet
        hb = {"hypotheses": [
            {"hypothesis_id": "H1", "mechanism_label": "Grotthuss proton hopping"},
            {"hypothesis_id": "H2", "mechanism_label": "Vehicle diffusion mechanism"},
        ]}
        packet = build_mechanism_query_packet(hb)
        assert packet.stage_target == "s05_mechanism"
        assert len(packet.search_queries) >= 5
        assert packet.stop_rule

    def test_material_query_packet(self):
        from s8_stage3.literature.query_packet_builder import build_material_query_packet
        ds = {"descriptors": [
            {"descriptor_id": "D1", "descriptor_text": "high proton conductivity",
             "required_material_features": ["hydrogel", "acid-doped"]},
        ]}
        packet = build_material_query_packet(ds)
        assert packet.stage_target == "s08_materials"
        assert len(packet.search_queries) >= 4

    def test_save_query_packet(self, tmp_path):
        from s8_stage3.literature.query_packet_builder import (
            build_mechanism_query_packet, save_query_packet,
        )
        hb = {"hypotheses": [{"hypothesis_id": "H1", "mechanism_label": "test mech"}]}
        packet = build_mechanism_query_packet(hb)
        json_path, md_path = save_query_packet(packet, tmp_path)
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["packet_id"] == packet.packet_id


# ── Registry Builder ──

class TestRegistryBuilder:
    def test_add_and_retrieve(self, tmp_path):
        from s8_stage3.literature.registry_builder import PaperRegistry
        reg = PaperRegistry(tmp_path)
        entry = PaperRegistryEntry(
            paper_id="test_001", title="Test Paper", year=2023,
            source_stage="s05_mechanism", local_path="test.pdf",
        )
        assert reg.add(entry)
        assert not reg.add(entry)  # duplicate
        assert reg.count == 1
        assert reg.get("test_001").title == "Test Paper"

    def test_save_and_reload(self, tmp_path):
        from s8_stage3.literature.registry_builder import PaperRegistry
        reg = PaperRegistry(tmp_path)
        reg.add(PaperRegistryEntry(
            paper_id="p1", title="Paper One", year=2020,
            source_stage="s05_mechanism", local_path="p1.pdf",
        ))
        reg.save()
        reg2 = PaperRegistry(tmp_path)
        assert reg2.count == 1
        assert reg2.get("p1").title == "Paper One"

    def test_generate_paper_id(self, tmp_path):
        from s8_stage3.literature.registry_builder import PaperRegistry
        reg = PaperRegistry(tmp_path)
        id1 = reg.generate_paper_id("Test Paper")
        assert id1.startswith("manual_")
        reg.add(PaperRegistryEntry(paper_id=id1, title="Test Paper"))
        id2 = reg.generate_paper_id("Test Paper")
        assert id2 != id1


# ── Deduper ──

class TestDeduper:
    def test_doi_dedup(self):
        from s8_stage3.contracts.paper import PaperRecord
        from s8_stage3.literature.deduper import deduplicate
        r1 = PaperRecord(paper_id="a", title="Test", doi="10.1234/x", source_provider="manual")
        r2 = PaperRecord(paper_id="b", title="Test variant", doi="10.1234/x", source_provider="openalex")
        result = deduplicate([r1, r2])
        assert result.total_output == 1
        assert len(result.log) == 1

    def test_title_year_dedup(self):
        from s8_stage3.contracts.paper import PaperRecord
        from s8_stage3.literature.deduper import deduplicate
        r1 = PaperRecord(paper_id="a", title="Proton Transport Study", year=2023)
        r2 = PaperRecord(paper_id="b", title="Proton Transport Study", year=2023)
        result = deduplicate([r1, r2])
        assert result.total_output == 1


# ── Paper Reader ──

class TestPaperReader:
    def test_read_text_file(self, tmp_path):
        from s8_stage3.literature.paper_reader import read_paper
        f = tmp_path / "test.txt"
        f.write_text("# My Paper Title\n\nAbstract: This is a test.\n\n## Introduction\nSome text.", encoding="utf-8")
        parsed = read_paper(f)
        assert parsed.title == "My Paper Title"
        assert len(parsed.sections) >= 1

    def test_read_json_file(self, tmp_path):
        from s8_stage3.literature.paper_reader import read_paper
        f = tmp_path / "test.json"
        f.write_text(json.dumps({
            "title": "JSON Paper", "authors": "Author A", "year": 2024,
            "abstract": "Test abstract",
        }), encoding="utf-8")
        parsed = read_paper(f)
        assert parsed.title == "JSON Paper"
        assert parsed.year == 2024

    def test_unsupported_extension(self, tmp_path):
        from s8_stage3.literature.paper_reader import read_paper
        f = tmp_path / "test.xyz"
        f.write_text("test", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            read_paper(f)


# ── Evidence Row Builder ──

class TestEvidenceRowBuilder:
    def test_extract_from_card(self):
        from s8_stage3.literature.evidence_row_builder import extract_evidence_rows, reset_counter
        reset_counter()
        card = PaperCard(
            paper_id="p001", stage_target="mechanism",
            mechanism_relevant_findings=["Grotthuss hopping dominates above 60C"],
            numerical_findings=[{"metric": "conductivity", "value": "0.1", "unit": "S/cm"}],
            eis_shape_findings=["Single semicircle in Nyquist plot"],
            limitations=["Only measured at room humidity"],
        )
        rows = extract_evidence_rows(card)
        assert len(rows) == 4
        types = {r.evidence_type for r in rows}
        assert "mechanism_claim" in types
        assert "direct_measurement" in types
        assert "limitation" in types

    def test_negation_moves_tag_to_weakens(self):
        """SDL §14.4: 否定前瞻应把命中关键词移到 weakens."""
        from s8_stage3.literature.evidence_row_builder import extract_evidence_rows, reset_counter
        reset_counter()
        card = PaperCard(
            paper_id="p_neg", stage_target="mechanism",
            mechanism_relevant_findings=[
                "Results are inconsistent with Grotthuss hopping at low temperature",
            ],
        )
        rows = extract_evidence_rows(card)
        assert len(rows) == 1
        r = rows[0]
        assert "Grotthuss" not in r.mechanism_tags
        assert "mechanism:Grotthuss" in r.weakens

    def test_confidence_scales_with_relevance(self):
        """SDL §14.5: confidence = base × relevance_score."""
        from s8_stage3.literature.evidence_row_builder import extract_evidence_rows, reset_counter
        reset_counter()
        card_high = PaperCard(
            paper_id="p_hi", stage_target="mechanism",
            mechanism_relevant_findings=["Proton transport via hydrogen bonds."],
            relevance_judgement={"score": 1.0, "reason": "directly on-topic"},
        )
        card_low = PaperCard(
            paper_id="p_lo", stage_target="mechanism",
            mechanism_relevant_findings=["Proton transport via hydrogen bonds."],
            relevance_judgement={"score": 0.3, "reason": "tangential"},
        )
        r_hi = extract_evidence_rows(card_high)[0]
        r_lo = extract_evidence_rows(card_low)[0]
        assert r_hi.confidence > r_lo.confidence
        assert abs(r_hi.confidence - 0.60 * 1.0) < 1e-6
        assert abs(r_lo.confidence - 0.60 * 0.3) < 1e-6

    def test_supports_axes_propagate_to_rows(self):
        """SDL §14.3: PaperCard.supports_axes / conflicts_axes 透传到 EvidenceRow."""
        from s8_stage3.literature.evidence_row_builder import extract_evidence_rows, reset_counter
        reset_counter()
        card = PaperCard(
            paper_id="p_ax", stage_target="mechanism",
            mechanism_relevant_findings=["H-bond network drives the transport."],
            supports_axes={"transport": "Grotthuss_hopping"},
            conflicts_axes={"temperature_dependence": "pure_Arrhenius"},
        )
        rows = extract_evidence_rows(card)
        assert len(rows) == 1
        r = rows[0]
        assert "transport:Grotthuss_hopping" in r.supports
        assert "temperature_dependence:pure_Arrhenius" in r.weakens


class TestOAFetcher:
    """路径 A: OpenAlex 召回 + 下载 + registry 登记."""

    def test_safe_paper_id_from_oa_url(self):
        from s8_stage3.literature.oa_fetcher import _safe_paper_id
        pid = _safe_paper_id("https://openalex.org/W1234567890", "Some Title")
        assert pid == "openalex_w1234567890"

    def test_safe_paper_id_fallback_to_title_hash(self):
        from s8_stage3.literature.oa_fetcher import _safe_paper_id
        pid = _safe_paper_id("", "Proton conductivity paper")
        assert pid.startswith("openalex_")
        assert len(pid) == len("openalex_") + 10

    def test_collect_existing_dois(self, tmp_path):
        from s8_stage3.literature.oa_fetcher import _collect_existing_dois
        from s8_stage3.literature.registry_builder import PaperRegistry
        from s8_stage3.contracts.paper_registry import PaperRegistryEntry
        reg = PaperRegistry(tmp_path)
        reg.add(PaperRegistryEntry(paper_id="p1", title="a", doi="10.1/AAA"))
        reg.add(PaperRegistryEntry(paper_id="p2", title="b", doi=None))
        dois = _collect_existing_dois(reg)
        assert dois == {"10.1/aaa"}

    def test_fetch_and_download_dedups_by_doi(self, tmp_path, monkeypatch):
        """registry 中已存在的 DOI 不应再次被下载。"""
        from s8_stage3.literature import oa_fetcher
        from s8_stage3.literature.manual_ingest import LiteratureWorkspace
        from s8_stage3.contracts.paper_registry import PaperRegistryEntry
        from s8_stage3.contracts.paper import PaperRecord

        ws = LiteratureWorkspace(tmp_path)
        reg = ws.get_registry()
        reg.add(PaperRegistryEntry(paper_id="existing", title="t", doi="10.1/DUP"))
        reg.save()

        fake_paper = PaperRecord(
            paper_id="W999",
            title="Dup paper",
            authors="A, B",
            year=2022,
            venue="Nat",
            doi="10.1/DUP",
            abstract="x",
            source_provider="openalex",
            source_url="https://openalex.org/W999",
            pdf_url="http://example.com/x.pdf",
        )

        class FakeProvider:
            def __init__(self, *a, **kw): pass
            def search(self, q, max_results=10, from_year=None):
                return [fake_paper]

        monkeypatch.setattr(oa_fetcher, "OpenAlexProvider", FakeProvider)

        def _no_download(*a, **kw):
            raise AssertionError("download should not be called for dup DOI")
        monkeypatch.setattr(oa_fetcher, "_download_pdf", _no_download)

        result = oa_fetcher.fetch_and_download_oa_papers(
            queries=["q1"], workspace=ws, stage_target="s05_mechanism",
            max_per_query=5, max_total=5, min_year=2010,
        )
        assert result.downloaded == 0
        assert result.skipped_dup_doi == 1

    def test_fetch_and_download_skips_no_pdf(self, tmp_path, monkeypatch):
        from s8_stage3.literature import oa_fetcher
        from s8_stage3.literature.manual_ingest import LiteratureWorkspace
        from s8_stage3.contracts.paper import PaperRecord

        ws = LiteratureWorkspace(tmp_path)
        fake = PaperRecord(
            paper_id="W1", title="No-OA paper", authors="", year=2021,
            doi="10.1/x", source_provider="openalex",
            source_url="https://openalex.org/W1",
            pdf_url="",  # no PDF
        )

        class FakeProvider:
            def __init__(self, *a, **kw): pass
            def search(self, *a, **kw): return [fake]
        monkeypatch.setattr(oa_fetcher, "OpenAlexProvider", FakeProvider)

        result = oa_fetcher.fetch_and_download_oa_papers(
            queries=["q1"], workspace=ws, stage_target="s05_mechanism",
            max_per_query=5, max_total=5, min_year=2010,
        )
        assert result.downloaded == 0
        assert result.skipped_no_pdf == 1

    def test_fetch_and_download_registers_entry(self, tmp_path, monkeypatch):
        """成功下载 + parse 后必须写入 registry (manually_added=False, provider_metadata)."""
        from s8_stage3.literature import oa_fetcher
        from s8_stage3.literature.manual_ingest import LiteratureWorkspace
        from s8_stage3.contracts.paper import PaperRecord
        from s8_stage3.literature.paper_reader import ParsedPaper

        ws = LiteratureWorkspace(tmp_path)
        fake = PaperRecord(
            paper_id="W42", title="Some real paper", authors="Alice, Bob",
            year=2022, venue="J. Foo", doi="10.1/OK",
            abstract="abs", source_provider="openalex",
            source_url="https://openalex.org/W0000000042",
            pdf_url="http://example.com/ok.pdf", citation_count=5,
        )

        class FakeProvider:
            def __init__(self, *a, **kw): pass
            def search(self, *a, **kw): return [fake]
        monkeypatch.setattr(oa_fetcher, "OpenAlexProvider", FakeProvider)

        def fake_download(url, dest, timeout=60):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
            return True, "ok"
        monkeypatch.setattr(oa_fetcher, "_download_pdf", fake_download)

        def fake_read(path):
            return ParsedPaper(
                source_path=str(path),
                title="Some real paper",
                authors="Alice, Bob",
                year=2022,
                full_text="This is the full text of the paper. " * 40,
                sections=[], tables=[], parse_warnings=[],
            )
        monkeypatch.setattr(oa_fetcher, "read_paper", fake_read)

        result = oa_fetcher.fetch_and_download_oa_papers(
            queries=["q1"], workspace=ws, stage_target="s05_mechanism",
            max_per_query=5, max_total=5, min_year=2010,
        )
        assert result.downloaded == 1

        reg = ws.get_registry()
        entry = reg.get("openalex_w0000000042")
        assert entry is not None
        assert entry.manually_added is False
        assert entry.doi == "10.1/OK"
        assert entry.ingest_status == "parsed"
        assert entry.source_stage == "s05_mechanism"
        assert entry.provider_metadata.get("provider") == "openalex"
        assert entry.provider_metadata.get("citation_count") == 5

        inbox_pdf = ws.inbox_dir / "s05_mechanism" / "openalex_w0000000042.pdf"
        parsed_pdf = ws.parsed_text_dir / "openalex_w0000000042.pdf"
        assert inbox_pdf.exists()
        assert parsed_pdf.exists()


class TestContextPackAggregation:
    """SDL §14.3 补丁：context_pack_builder 必须保留频次信息且不丢失
    direct_measurement rows 的 supports/weakens（paper-level axes 对所有 row 生效）."""

    def _make_row(self, row_id, etype, supports=None, weakens=None):
        from s8_stage3.contracts.evidence_row import EvidenceRow
        return EvidenceRow(
            row_id=row_id,
            paper_id="p1",
            stage_target="s05_mechanism",
            evidence_type=etype,
            claim_text="x",
            normalized_claim="x",
            supports=supports or [],
            weakens=weakens or [],
            confidence=0.5,
            trace_ref="",
        )

    def test_key_supports_preserves_frequency(self):
        from s8_stage3.contracts.evidence_row import CuratedEvidenceTable
        from s8_stage3.literature.context_pack_builder import build_context_pack
        rows = [
            self._make_row(f"r{i}", "mechanism_claim", supports=["transport:Grotthuss_hopping"])
            for i in range(5)
        ]
        rows.append(self._make_row("r9", "mechanism_claim", supports=["transport:vehicular_diffusion"]))
        table = CuratedEvidenceTable(
            table_id="t", stage_target="s05_mechanism",
            included_rows=rows, excluded_rows=[],
        )
        pack = build_context_pack(table, "s05", max_rows=10)
        top = pack.key_supports[0]
        assert "Grotthuss_hopping" in top
        assert "(x5)" in top  # 频次被保留

    def test_direct_measurement_rows_carry_card_axes(self, tmp_path):
        from s8_stage3.contracts.paper_card import PaperCard
        from s8_stage3.literature.evidence_row_builder import extract_evidence_rows
        card = PaperCard(
            paper_id="p1", stage_target="mechanism",
            bibliography={"title": "t", "authors": []},
            system_identity={}, measurement_scope={},
            mechanism_relevant_findings=[],
            numerical_findings=[{"metric": "sigma", "value": "0.1", "unit": "S/cm", "conditions": "60C"}],
            eis_shape_findings=["Nyquist shows single arc"],
            arrhenius_vtf_findings=[],
            limitations=[],
            relevance_judgement={"score": 0.8, "reason": "x"},
            supports_axes={"transport": "Grotthuss_hopping"},
            conflicts_axes={"transport": "vehicular_diffusion"},
        )
        rows = extract_evidence_rows(card)
        measurement_rows = [r for r in rows if r.evidence_type == "direct_measurement"]
        assert len(measurement_rows) == 2
        for r in measurement_rows:
            assert "transport:Grotthuss_hopping" in r.supports
            assert "transport:vehicular_diffusion" in r.weakens


class TestAxisSanitizer:
    """SDL §14.3 补丁：paper_card_builder._sanitize_axes 必须丢弃非 canonical 值."""

    def test_drops_non_canonical_values(self):
        from s8_stage3.literature.paper_card_builder import _sanitize_axes
        raw = {
            "transport": "Grotthuss_hopping",  # 合法
            "temperature_dependence": "Arrhenius",  # 非合法（应为 pure_Arrhenius 等）
            "unknown_axis": "x",  # 非合法 key
            "phase_structure": "single_percolation_threshold",  # 合法
        }
        clean = _sanitize_axes(raw, "p_test", "supports_axes")
        assert clean == {
            "transport": "Grotthuss_hopping",
            "phase_structure": "single_percolation_threshold",
        }

    def test_non_dict_returns_empty(self):
        from s8_stage3.literature.paper_card_builder import _sanitize_axes
        assert _sanitize_axes("not a dict", "p", "supports_axes") == {}
        assert _sanitize_axes(None, "p", "supports_axes") == {}


class TestHypothesisAxes:
    """SDL §14.6: Hypothesis 必须携带 mechanism_axes 字段."""

    def test_hypothesis_accepts_axes(self):
        from s8_stage3.contracts.hypothesis import Hypothesis
        h = Hypothesis(
            hypothesis_id="H1",
            mechanism_label="Piecewise Arrhenius Grotthuss with single transition",
            description="Proton hopping with one H-bond reorganization threshold.",
            mechanism_axes={
                "transport": "Grotthuss_hopping",
                "phase_structure": "single_continuous_phase",
                "temperature_dependence": "piecewise_Arrhenius",
                "transition_topology": "single_transition",
            },
        )
        assert h.mechanism_axes["transport"] == "Grotthuss_hopping"
        assert h.mechanism_axes["transition_topology"] == "single_transition"

    def test_mock_s04_hypotheses_have_axes_and_compete(self):
        """mock_llm 生成的 4 个假说必须每条都有 4 个 axis key，且至少一个 axis 上存在不同取值."""
        from s8_stage3.mock.mock_llm import _mock_s04
        out = _mock_s04([])
        axes_keys = {"transport", "phase_structure", "temperature_dependence", "transition_topology"}
        for h in out["hypotheses"]:
            assert axes_keys.issubset(h["mechanism_axes"].keys())
        transport_values = {h["mechanism_axes"]["transport"] for h in out["hypotheses"]}
        assert len(transport_values) >= 2, "hypotheses must compete on at least one axis"


# ── Evidence Table Builder ──

class TestEvidenceTableBuilder:
    def test_mechanism_table(self):
        from s8_stage3.literature.evidence_table_builder import build_mechanism_evidence_table
        rows = [
            EvidenceRow(
                row_id=f"ER-{i}", paper_id="p1", stage_target="mechanism",
                evidence_type="mechanism_claim", claim_text=f"Claim {i}",
                confidence=0.7,
            )
            for i in range(5)
        ]
        table = build_mechanism_evidence_table(rows, max_rows=3)
        assert len(table.included_rows) == 3
        assert len(table.excluded_rows) == 2
        assert table.table_id == "mechanism_evidence_table"


# ── Context Pack Builder ──

class TestContextPackBuilder:
    def test_build_context_pack(self):
        from s8_stage3.literature.context_pack_builder import build_context_pack
        rows = [
            EvidenceRow(
                row_id=f"ER-{i}", paper_id="p1", stage_target="mechanism",
                evidence_type="mechanism_claim", claim_text=f"Claim {i}",
            )
            for i in range(5)
        ]
        table = CuratedEvidenceTable(
            table_id="test", stage_target="mechanism",
            included_rows=rows,
        )
        pack = build_context_pack(table, "s05", max_rows=3)
        assert len(pack.included_row_ids) == 3
        assert pack.pack_id == "ctx-s05"

    def test_format_for_llm(self):
        from s8_stage3.literature.context_pack_builder import format_context_for_llm
        rows = [EvidenceRow(
            row_id="ER-1", paper_id="p1", stage_target="mechanism",
            evidence_type="mechanism_claim", claim_text="Test claim",
        )]
        pack = ContextPack(
            pack_id="ctx-s05", stage_target="s05",
            included_row_ids=["ER-1"], summary="test",
        )
        text = format_context_for_llm(pack, rows)
        assert "[p1|mechanism_claim]" in text


# ── Manual Ingest ──

class TestManualIngest:
    def test_workspace_creation(self, tmp_path):
        from s8_stage3.literature.manual_ingest import LiteratureWorkspace
        ws = LiteratureWorkspace(tmp_path / "lit_ws")
        assert (tmp_path / "lit_ws" / "01_manual_inbox" / "s05_mechanism").is_dir()
        assert (tmp_path / "lit_ws" / "02_registry").is_dir()
        assert (tmp_path / "lit_ws" / "07_context_packs").is_dir()

    def test_ingest_txt_file(self, tmp_path):
        from s8_stage3.literature.manual_ingest import LiteratureWorkspace, ingest_inbox
        ws = LiteratureWorkspace(tmp_path / "lit_ws")
        inbox = ws.inbox_dir / "s05_mechanism"
        (inbox / "test_paper.txt").write_text(
            "# Proton Transport\n\nAbstract: A study of proton hopping.",
            encoding="utf-8",
        )
        result = ingest_inbox(ws, stage="s05_mechanism", copy_to_parsed=True)
        assert result.success == 1
        assert result.failed == 0
        reg = ws.get_registry()
        assert reg.count == 1


# ── Pipeline Smoke (mock mode preserved) ──

class TestPipelineMockPreserved:
    def test_mock_pipeline_still_works(self, tmp_path):
        """Ensure mock mode is not broken."""
        import os
        os.environ["STAGE3_LLM_MODE"] = "mock"
        os.environ["STAGE3_LITERATURE_MODE"] = "mock"
        from s8_stage3.config.settings import load_settings
        from s8_stage3.config.model_registry import ModelRegistry
        from s8_stage3.config.llm_gateway import LLMGateway
        from s8_stage3.orchestrator.pipeline import Pipeline

        settings = load_settings()
        reg = ModelRegistry(
            cheap=settings.model_cheap,
            standard=settings.model_standard,
            premium=settings.model_premium,
        )
        gw = LLMGateway(settings, reg)
        pipe = Pipeline(
            settings=settings, gateway=gw,
            output_dir=tmp_path / "outputs" / "stage3",
            literature_mode="mock",
        )
        results = pipe.run_mock()
        assert results["evidence"] is not None
        assert results["ranking"] is not None


# ── Fix 1: query packet path ──

class TestQueryPacketPath:
    def test_run_stage3_uses_correct_hypothesis_dir(self):
        """Verify _run_query_packets references 02_hypotheses (plural)."""
        import inspect
        from s8_stage3.orchestrator import run_stage3
        src = inspect.getsource(run_stage3._run_query_packets)
        assert "02_hypotheses" in src
        assert "02_hypothesis" not in src.replace("02_hypotheses", "")


# ── Fix 2: strict vs fallback manual mode ──

class TestManualStrictMode:
    def test_s05_strict_no_context_pack_raises(self, tmp_path):
        """strict manual: missing context pack -> RuntimeError."""
        from unittest.mock import MagicMock
        ws_dir = tmp_path / "lit_ws"
        for d in [
            "00_query_packets/s05_mechanism", "01_manual_inbox/s05_mechanism",
            "02_registry", "03_parsed_text",
            "04_paper_cards/mechanism", "05_evidence_rows/mechanism",
            "06_curated_tables", "07_context_packs",
        ]:
            (ws_dir / d).mkdir(parents=True, exist_ok=True)

        settings = MagicMock()
        settings.literature_workspace_dir = ws_dir
        from s8_stage3.agents.s05_literature_scout_mechanism import (
            _fetch_manual_cards_and_context,
        )
        with pytest.raises(RuntimeError, match="strict"):
            _fetch_manual_cards_and_context(settings, strict=True)

    def test_s05_fallback_no_context_pack_returns_empty(self, tmp_path):
        """fallback manual: missing context pack -> returns empty cards, no error."""
        from unittest.mock import MagicMock
        ws_dir = tmp_path / "lit_ws"
        for d in [
            "00_query_packets/s05_mechanism", "01_manual_inbox/s05_mechanism",
            "02_registry", "03_parsed_text",
            "04_paper_cards/mechanism", "05_evidence_rows/mechanism",
            "06_curated_tables", "07_context_packs",
        ]:
            (ws_dir / d).mkdir(parents=True, exist_ok=True)
        # Empty registry
        (ws_dir / "02_registry" / "paper_registry.json").write_text("[]", encoding="utf-8")

        settings = MagicMock()
        settings.literature_workspace_dir = ws_dir
        from s8_stage3.agents.s05_literature_scout_mechanism import (
            _fetch_manual_cards_and_context,
        )
        cards, ctx = _fetch_manual_cards_and_context(settings, strict=False)
        assert isinstance(cards, list)
        assert ctx == ""

    def test_s08_strict_no_context_pack_raises(self, tmp_path):
        """strict manual S08: missing context pack -> RuntimeError."""
        from unittest.mock import MagicMock
        ws_dir = tmp_path / "lit_ws"
        for d in [
            "00_query_packets/s08_materials", "01_manual_inbox/s08_materials",
            "02_registry", "03_parsed_text",
            "04_paper_cards/materials", "05_evidence_rows/materials",
            "06_curated_tables", "07_context_packs",
        ]:
            (ws_dir / d).mkdir(parents=True, exist_ok=True)

        settings = MagicMock()
        settings.literature_workspace_dir = ws_dir
        from s8_stage3.agents.s08_literature_scout_materials import (
            _fetch_manual_cards_and_context,
        )
        with pytest.raises(RuntimeError, match="strict"):
            _fetch_manual_cards_and_context(settings, strict=True)


# ── Fix 3: paper card quality gate + fallback extractor ──

class TestPaperCardQualityGate:
    def test_high_quality_card(self):
        """Card with >= 2 findings -> 'carded'."""
        from s8_stage3.literature.paper_card_builder import check_card_quality
        card = PaperCard(
            paper_id="p_hq",
            stage_target="mechanism",
            mechanism_relevant_findings=["Grotthuss hopping dominates", "VTF behavior at high T"],
        )
        assert check_card_quality(card) == "carded"

    def test_low_quality_card(self):
        """Card with 0 findings -> 'low_quality'."""
        from s8_stage3.literature.paper_card_builder import check_card_quality
        card = PaperCard(
            paper_id="p_lq",
            stage_target="mechanism",
        )
        assert check_card_quality(card) == "low_quality"

    def test_borderline_card(self):
        """Card with exactly 1 finding -> 'low_quality' (< 2)."""
        from s8_stage3.literature.paper_card_builder import check_card_quality
        card = PaperCard(
            paper_id="p_bl",
            stage_target="mechanism",
            mechanism_relevant_findings=["Single finding"],
        )
        assert check_card_quality(card) == "low_quality"


class TestFallbackExtractor:
    def test_fallback_extracts_keyword_sentences(self):
        from s8_stage3.literature.paper_reader import ParsedPaper
        from s8_stage3.literature.paper_card_builder import fallback_keyword_extract
        parsed = ParsedPaper(
            source_path="test.pdf",
            full_text=(
                "The proton conductivity was measured at 80°C. "
                "We observed 0.01 S/cm at RH=100%. "
                "The activation energy was 0.35 eV. "
                "A clear semicircle was seen in the Nyquist plot. "
                "Grotthuss hopping dominates at elevated temperatures. "
                "This is an unrelated sentence about weather."
            ),
        )
        findings = fallback_keyword_extract(parsed)
        assert len(findings) >= 4
        assert any("conductivity" in f.lower() for f in findings)
        assert any("eV" in f for f in findings)

    def test_fallback_returns_empty_for_irrelevant_text(self):
        from s8_stage3.literature.paper_reader import ParsedPaper
        from s8_stage3.literature.paper_card_builder import fallback_keyword_extract
        parsed = ParsedPaper(
            source_path="test.pdf",
            full_text="The weather is nice today. Cats are cute. Dogs are adorable.",
        )
        findings = fallback_keyword_extract(parsed)
        assert findings == []

    def test_build_paper_card_applies_quality_gate_and_fallback(self):
        """build_paper_card returns correct status for low quality + fallback."""
        from unittest.mock import MagicMock
        from s8_stage3.literature.paper_reader import ParsedPaper
        from s8_stage3.literature.paper_card_builder import build_paper_card

        gw = MagicMock()
        gw.chat_json.return_value = {
            "system_identity": {},
            "measurement_scope": {},
            "mechanism_relevant_findings": [],
            "numerical_findings": [],
            "eis_shape_findings": [],
            "arrhenius_vtf_findings": [],
            "limitations": [],
            "relevance_judgement": {"score": 0.3, "reason": "marginal"},
        }
        parsed = ParsedPaper(
            source_path="test.pdf",
            title="Test Paper",
            full_text="The proton conductivity reached 0.05 S/cm. Activation energy of 0.4 eV was measured.",
        )
        card, status = build_paper_card(parsed, "p_test", "mechanism", gw)
        assert status in ("carded_fallback", "carded")
        assert len(card.mechanism_relevant_findings) >= 1
