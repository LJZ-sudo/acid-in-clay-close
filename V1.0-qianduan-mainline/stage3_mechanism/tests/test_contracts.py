"""测试所有 contract 模型的基础导入和字段验证。"""
import pytest
from pydantic import ValidationError


def test_evidence_contract():
    from s8_stage3.contracts.evidence import EvidenceCard, EvidenceBundle
    card = EvidenceCard(
        card_id="E1",
        claim_type="observation",
        statement="Test statement",
        confidence=0.8,
    )
    assert card.card_id == "E1"
    bundle = EvidenceBundle(
        step_id="s03_evidence",
        evidence_cards=[card],
    )
    assert len(bundle.evidence_cards) == 1


def test_hypothesis_contract():
    from s8_stage3.contracts.hypothesis import Hypothesis, HypothesisBoard
    h = Hypothesis(
        hypothesis_id="H1",
        mechanism_label="Test",
        description="A test hypothesis",
        prior_plausibility=0.7,
    )
    assert h.prior_plausibility == 0.7

    # 测试 validator: string -> float
    h2 = Hypothesis(
        hypothesis_id="H2",
        mechanism_label="Test2",
        description="Another test",
        prior_plausibility="medium-high",  # type: ignore
    )
    assert h2.prior_plausibility == 0.65


def test_mechanism_contract():
    from s8_stage3.contracts.mechanism import MechanismCard, MechanismArbitrationResult
    card = MechanismCard(
        selected_hypothesis_id="H1",
        mechanism_label="Test Mechanism",
        justification="Because the evidence says so.",
        confidence=0.75,
    )
    assert card.confidence == 0.75

    # string confidence
    card2 = MechanismCard(
        selected_hypothesis_id="H1",
        mechanism_label="Test",
        justification="...",
        confidence="high",  # type: ignore
    )
    assert card2.confidence == 0.8


def test_literature_contract():
    from s8_stage3.contracts.literature import LiteratureCard, LiteratureSurvey
    c = LiteratureCard(card_id="ML1", title="Test Paper")
    assert c.authors == ""
    assert c.component_descriptor_claims == []

    # list authors -> str
    c2 = LiteratureCard(card_id="ML2", authors=["Author A", "Author B"])  # type: ignore
    assert "Author A" in c2.authors

    # synthesis_notes list -> str
    s = LiteratureSurvey(
        step_id="s05",
        survey_scope="mechanism_constraint",
        synthesis_notes=["note1", "note2"],  # type: ignore
    )
    assert isinstance(s.synthesis_notes, str)


def test_component_descriptor_claim_contract():
    """方案 D4：ComponentDescriptorClaim 的字段与 validator 行为。"""
    from s8_stage3.contracts.literature import (
        ComponentDescriptorClaim,
        LiteratureCard,
    )

    claim = ComponentDescriptorClaim(
        component="attapulgite",
        descriptor_ids=["D2", "D5"],
        quantitative_anchor="35.3 mS/cm at 80 °C",
        claim_text="attapulgite provides 1-D confined proton channel (MAT2).",
        confidence="supported",
    )
    assert claim.component == "attapulgite"
    assert claim.descriptor_ids == ["D2", "D5"]
    assert claim.confidence == "supported"

    # str -> list coercion
    claim2 = ComponentDescriptorClaim(
        component="starch",
        descriptor_ids="D1, D4",  # type: ignore
        claim_text="starch OH backbone",
    )
    assert set(claim2.descriptor_ids) == {"D1", "D4"}
    assert claim2.confidence == "supported"  # default

    # invalid confidence -> defaults to supported
    claim3 = ComponentDescriptorClaim(
        component="PVA",
        descriptor_ids=["D4"],
        claim_text="PVA film former",
        confidence="NOT_A_VALID_VALUE",  # type: ignore
    )
    assert claim3.confidence == "supported"

    # LiteratureCard carries claims
    card = LiteratureCard(
        card_id="MAT2",
        component_descriptor_claims=[claim],
    )
    assert len(card.component_descriptor_claims) == 1
    assert card.component_descriptor_claims[0].component == "attapulgite"


def test_descriptor_contract():
    from s8_stage3.contracts.descriptor import MechanismDescriptor, DescriptorSheet
    d = MechanismDescriptor(
        descriptor_id="D1",
        descriptor_text="OH-rich host",
        mechanism_role="proton hopping backbone",
        priority="critical",
    )
    assert d.priority == "critical"
    sheet = DescriptorSheet(descriptors=[d])
    assert len(sheet.descriptors) == 1


def test_material_contract():
    from s8_stage3.contracts.material import MaterialFamily, MaterialInstance, MaterialFamilySet
    f = MaterialFamily(
        family_id="F1",
        family_name="OH-rich polysaccharide",
        descriptor_match=["D1: matches", "D2: matches"],
    )
    assert len(f.descriptor_match) == 2

    # dict -> list
    f2 = MaterialFamily(
        family_id="F2",
        family_name="Test",
        descriptor_match={"D1": "match", "D2": "match"},  # type: ignore
    )
    assert isinstance(f2.descriptor_match, list)

    # 新合同 (方案 B)：combination_novelty + element_evidence / novelty_rationale
    # 替代旧的 evidence_tier 二分法。
    from s8_stage3.contracts.material import ElementEvidence

    inst = MaterialInstance(
        instance_id="I1",
        family_id="F1",
        instance_name="PAAm-graft-starch / H3PO4 (literature baseline)",
        combination_novelty="exact_match",
        components=["PAAm-graft-starch", "H3PO4"],
        element_evidence=[
            ElementEvidence(
                component="PAAm-graft-starch",
                role_in_formulation="OH-rich 3D host",
                descriptor_satisfied=["D1", "D4"],
                analog_paper_ids=["MAT1"],
                analog_reason="MAT1 reports exactly this system",
            ),
        ],
        novelty_rationale=(
            "Control baseline: reproduces MAT1 crosslinked PAAm-g-starch + H3PO4 "
            "system. Retained to anchor the Top-list in a literature reference."
        ),
    )
    assert inst.combination_novelty == "exact_match"
    # 派生字段校验: literature_support_card_ids 自动来自 element_evidence
    assert "MAT1" in inst.literature_support_card_ids
    assert not hasattr(inst, "lotus_related"), "lotus_related 字段必须已删除"
    assert not hasattr(inst, "evidence_tier"), "evidence_tier 字段已被 combination_novelty 替代"

    # novel_combination 路线: 每个组分都要有 element-level 类比
    novel = MaterialInstance(
        instance_id="I2",
        family_id="F1",
        instance_name="Lotus starch / PVA / H3PO4 / attapulgite",
        combination_novelty="novel_combination",
        components=[
            "lotus rhizome starch",
            "PVA",
            "H3PO4",
            "attapulgite",
        ],
        element_evidence=[
            ElementEvidence(
                component="lotus rhizome starch",
                role_in_formulation="OH host",
                descriptor_satisfied=["D1", "D4"],
                analog_paper_ids=["MAT-lotus", "MAT3"],
                analog_reason="starch+H3PO4 proton channel + biomass characterisation",
            ),
            ElementEvidence(
                component="PVA",
                role_in_formulation="film-forming",
                descriptor_satisfied=["D2"],
                analog_paper_ids=["MAT-pva"],
                analog_reason="PVA/starch H-bonding",
            ),
            ElementEvidence(
                component="H3PO4",
                role_in_formulation="proton donor",
                descriptor_satisfied=["D3"],
                analog_paper_ids=["MAT1"],
                analog_reason="standard proton carrier",
            ),
            ElementEvidence(
                component="attapulgite",
                role_in_formulation="1-D channel",
                descriptor_satisfied=["D5"],
                analog_paper_ids=["MAT2"],
                analog_reason="attapulgite proton channel reported in MAT2",
            ),
        ],
        novelty_rationale=(
            "No S08 card reports this four-component combination as a unit; "
            "each component has its own element-level analog. Relative to the "
            "closest exact paper (MAT2: PVA+H3PO4+MMT), this route swaps layered "
            "MMT for 1-D attapulgite and introduces a biomass OH-host."
        ),
    )
    assert novel.combination_novelty == "novel_combination"
    assert len(novel.element_evidence) == 4
    assert set(novel.literature_support_card_ids) == {"MAT-lotus", "MAT3", "MAT-pva", "MAT1", "MAT2"}

    # D2：descriptor_satisfied 应在合约里正常存活，并允许 str-fallback
    ev = ElementEvidence(
        component="test",
        role_in_formulation="role",
        descriptor_satisfied="D1, D2",  # type: ignore  validator 会 split
        analog_paper_ids=[],
        analog_reason="no S08 analog; inferred from public physicochemical knowledge",
    )
    assert set(ev.descriptor_satisfied) == {"D1", "D2"}
    # 空字符串→ []
    ev2 = ElementEvidence(
        component="test",
        role_in_formulation="role",
    )
    assert ev2.descriptor_satisfied == []


def test_ranking_contract():
    from s8_stage3.contracts.ranking import RankingCriterion, RankedCandidate, RankingResult
    c = RankingCriterion(criterion_name="test", score="0.8", weight="1.5")  # type: ignore
    assert c.score == 0.8
    assert c.weight == 1.5

    cand = RankedCandidate(
        rank=1,
        instance_id="I1",
        instance_name="Test",
        total_score=0.82,
    )
    assert cand.rank == 1


def test_report_contract():
    from s8_stage3.contracts.report import ReportSection, Stage3Report
    section = ReportSection(section_id="S1", title="Test", content="Content here")
    report = Stage3Report(sections=[section])
    assert len(report.sections) == 1


def test_seed_contract():
    from s8_stage3.contracts.seed import Stage3SeedBundle, SeedSegment, SeedSampleSummary
    seg = SeedSegment(
        segment_id="seg0",
        sample_id="S1",
        t_min=200.0,
        t_max=340.0,
        scan_dir="heating",
    )
    summary = SeedSampleSummary(
        sample_id="S1",
        composition_r=1.0,
        composition_n=2.0,
    )
    bundle = Stage3SeedBundle(
        bundle_id="test_bundle",
        source_mode="mock",
        seed_segments=[seg],
        seed_sample_summaries=[summary],
    )
    assert bundle.source_mode == "mock"
    assert len(bundle.seed_segments) == 1
