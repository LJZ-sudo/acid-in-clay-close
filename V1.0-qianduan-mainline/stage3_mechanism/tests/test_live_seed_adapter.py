# -*- coding: utf-8 -*-
"""P13-F:live_seed_adapter 专用单测(此前仅靠 p9 集成覆盖,无 pytest 单元级断言)。"""
from __future__ import annotations

from s8_stage3.adapters.live_seed_adapter import build_seed_from_live


def test_build_seed_from_live_produces_real_stage3_bundle():
    """真机风格逐点测量 → Stage3SeedBundle:温区段、证据卡、组成节点均 grounded。"""
    points = [
        {"T_C": 20.0, "T_K": 293.15, "rb_ohm": 2.0, "sigma_S_cm": 1.0e-2, "qc_grade": "A"},
        {"T_C": 0.0, "T_K": 273.15, "rb_ohm": 5.0, "sigma_S_cm": 3.0e-3, "qc_grade": "B"},
        {"T_C": -20.0, "T_K": 253.15, "rb_ohm": 50.0, "sigma_S_cm": 5.0e-5, "qc_grade": "C"},
    ]
    seed = build_seed_from_live(
        points,
        sample_id="unit-live-seed",
        R=0.186,
        N=1.029,
        transitions_K=[263.15],
        arrhenius={"best_model_type": "segmented", "confidence": 0.85},
    )
    assert seed.source_mode == "real"
    assert seed.bundle_id == "live-seed-unit-live-seed"
    assert len(seed.seed_segments) == 2
    eas = [s.representative_ea for s in seed.seed_segments]
    assert any(e is not None for e in eas), "至少一段(≥2 点)应算出 Ea"
    summary = seed.seed_sample_summaries[0]
    assert summary.composition_r == 0.186
    assert summary.composition_n == 1.029
    assert summary.t_break_k == 263.15
    ev = seed.stage2_seed_v2["evidence_units"]
    assert len(ev) >= 2
    assert ev[0]["evidence_id"] == "LIVE-1"
    assert "genuine-live" in ev[0]["statement"].lower() or "Conductivity" in ev[0]["statement"]
    assert seed.upstream_facts["n_live_points"] == 3
    assert seed.system_context.key_variables["R"].startswith("n(H3PO4)")
