"""Mock Seed Factory — 生成最小完整的 Stage3SeedBundle 用于架构测试。

注意：此文件中的所有数据均为 mock fixture，不代表真实科学结论。
mock 数据体现以下特征模式（用于测试当前 Stage3 可执行链闭环）：
- 宽温区 (200K - 340K)
- T_arc < T_break 错位
- Arrhenius 优于 VTF 的片段
- Meyer-Neldel 关系提示
- EIS 形貌启发式（非确定性结论）
"""

from __future__ import annotations

import uuid

from s8_stage3.contracts.seed import (
    SeedAtlasHint,
    SeedCompositionNode,
    SeedSegment,
    SeedSampleSummary,
    Stage3SeedBundle,
    SystemContext,
)


def _make_sample(
    sample_id: str,
    r: float,
    n: float,
    t_break: float | None,
    t_arc: float | None,
) -> tuple[SeedSampleSummary, list[SeedSegment]]:
    summary = SeedSampleSummary(
        sample_id=sample_id,
        composition_r=r,
        composition_n=n,
        scan_dirs=["heating"],
        t_break_k=t_break,
        t_arc_k=t_arc,
        has_eis_feature=t_arc is not None,
        conductivity_trend="increasing",
        segment_ids=[f"{sample_id}_seg0", f"{sample_id}_seg1"],
    )
    seg_low = SeedSegment(
        segment_id=f"{sample_id}_seg0",
        sample_id=sample_id,
        scan_dir="heating",
        t_min=200.0,
        t_max=t_break or 270.0,
        n_points=15,
        representative_ea=0.45,
        representative_sigma0=1e-5,
        segment_order=0,
        fit_type="arrhenius",
        is_wide_range=True,
    )
    seg_high = SeedSegment(
        segment_id=f"{sample_id}_seg1",
        sample_id=sample_id,
        scan_dir="heating",
        t_min=t_break or 270.0,
        t_max=340.0,
        n_points=10,
        representative_ea=0.18,
        representative_sigma0=1e-3,
        segment_order=1,
        fit_type="vtf",
        is_wide_range=False,
    )
    return summary, [seg_low, seg_high]


def create_mock_seed_bundle() -> Stage3SeedBundle:
    """生成 mock Stage3SeedBundle。此为 mock fixture，不是真实科学结论。"""
    samples_config = [
        ("S1_R1N2", 1.0, 2.0, 268.0, 255.0),
        ("S2_R1N4", 1.0, 4.0, 272.0, 260.0),
        ("S3_R2N2", 2.0, 2.0, 275.0, 265.0),
        ("S4_R2N4", 2.0, 4.0, 270.0, None),
        ("S5_R3N2", 3.0, 2.0, 280.0, 268.0),
    ]

    all_summaries: list[SeedSampleSummary] = []
    all_segments: list[SeedSegment] = []

    for sid, r, n, t_break, t_arc in samples_config:
        summary, segs = _make_sample(sid, r, n, t_break, t_arc)
        all_summaries.append(summary)
        all_segments.extend(segs)

    composition_nodes = [
        SeedCompositionNode(
            node_id="C_R1N2", r=1.0, n=2.0,
            sample_ids=["S1_R1N2"], sample_count=1, available_scan_dirs=["heating"],
        ),
        SeedCompositionNode(
            node_id="C_R1N4", r=1.0, n=4.0,
            sample_ids=["S2_R1N4"], sample_count=1, available_scan_dirs=["heating"],
        ),
        SeedCompositionNode(
            node_id="C_R2N2", r=2.0, n=2.0,
            sample_ids=["S3_R2N2"], sample_count=1, available_scan_dirs=["heating"],
        ),
        SeedCompositionNode(
            node_id="C_R2N4", r=2.0, n=4.0,
            sample_ids=["S4_R2N4"], sample_count=1, available_scan_dirs=["heating"],
        ),
        SeedCompositionNode(
            node_id="C_R3N2", r=3.0, n=2.0,
            sample_ids=["S5_R3N2"], sample_count=1, available_scan_dirs=["heating"],
        ),
    ]

    atlas_hints = [
        SeedAtlasHint(
            hint_id="AH1",
            claim_level="observation",
            theme="transport",
            statement=(
                "Conductivity increases monotonically with temperature across 200-340K "
                "for most samples, consistent with thermally-activated proton transport."
            ),
            confidence=0.85,
            tags=["proton_transport", "wide_temp"],
            support_metrics={"samples_count": "5"},
            usage_policy="allowed_as_observation_hint",
        ),
        SeedAtlasHint(
            hint_id="AH2",
            claim_level="interpretation",
            theme="mechanism",
            statement=(
                "EIS arcs disappear near T_arc ~ 260K, suggesting a transition in "
                "impedance response. Interpretation: grain boundary contribution decreases."
            ),
            confidence=0.6,
            tags=["eis", "grain_boundary"],
            support_metrics={},
            usage_policy="allowed_as_context_only",
        ),
        SeedAtlasHint(
            hint_id="AH3",
            claim_level="question",
            theme="mechanism",
            statement="Is the T_arc vs T_break offset due to bulk vs interface proton dynamics?",
            confidence=0.5,
            tags=["t_arc", "t_break"],
            support_metrics={},
            usage_policy="allowed_as_context_only",
        ),
    ]

    return Stage3SeedBundle(
        bundle_id=f"mock_{uuid.uuid4().hex[:8]}",
        source_mode="mock",
        seed_segments=all_segments,
        seed_sample_summaries=all_summaries,
        seed_composition_nodes=composition_nodes,
        seed_atlas_hints=atlas_hints,
        upstream_facts={
            "n_samples": 5,
            "wide_temp_range": True,
            "t_arc_lt_t_break_count": 4,
            "arrhenius_dominant_low_t": True,
            "meyer_neldel_hint": True,
        },
        system_context=SystemContext(
            chemistry_summary=(
                "Mock acid-inorganic electrolyte: an aqueous strong acid (e.g. H3PO4) "
                "confined in a 1-D nanometric inorganic host, measured between 200 K "
                "and 340 K. Chemistry is fixed by the experimental setup and is not "
                "a recommendation target."
            ),
            key_variables={
                "R": "acid / water molar ratio",
                "N": "liquid / solid mass ratio (acid solution vs. inorganic host)",
            },
            temperature_window_K=[200.0, 340.0],
            provenance="mock_seed_factory_fixture",
        ),
        adapter_warnings=[],
    )
