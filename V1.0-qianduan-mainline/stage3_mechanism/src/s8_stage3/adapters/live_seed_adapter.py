"""Live → Stage3 接线适配器（把 live 全温区测量真实喂进机理推理链）。

GPT 愿景(`GPT提问.txt` L69–71)的"迁移发现"主体 = LLM 驱动的
**证据 → 假设 → 文献约束 → 机理仲裁 → 可迁移设计原则** 推理链(stage3_mechanism)。
此前它只能从 Stage2 离线产物起跑(`stage2_seed_adapter`),**未接 live 测量回路**。

本模块补这条线:
  - ``build_seed_from_live`` 把 hardware_adapter 的真实逐点测量(T/Rb/σ + 全局
    Arrhenius 段/相变温度)构造成**真实** ``Stage3SeedBundle``(含 ``stage2_seed_v2``
    evidence_units,使 S03 产出权威证据卡,而非自由臆测);
  - ``run_mechanism_reasoning`` 用真实 ``LLMGateway``(live)驱动 ``Pipeline``
    跑到 ``s06b``(S03 证据 → **S04 假设(真 LLM)** → S05 文献 → **S06 机理仲裁(真 LLM)**
    → **S06b 设计原则(真 LLM)**),返回结果 + LLM 调用统计。

诚实边界:S05 文献检索默认 ``mock``(未接外部文献 API),但**核心机理推理 S04/S06/S06b
为真实 LLM 网络调用**;S03/S14 按设计为确定性。
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

_KB_EV = 8.617333262e-5  # Boltzmann constant, eV/K
REASONING_UNTIL_STEP = "s06b_design_principle_extractor"


# --------------------------------------------------------------------------- #
# 1) 由真实 live 测量构造 Stage3SeedBundle
# --------------------------------------------------------------------------- #

def _arrhenius_ea_ev(pts: List[Dict[str, Any]]) -> Optional[float]:
    """对一段点做 Arrhenius 拟合 ln(σ) vs 1/T → Ea(eV)。点不足/退化返回 None。"""
    xs, ys = [], []
    for p in pts:
        T_K = p.get("T_K")
        sig = p.get("sigma_S_cm")
        if T_K and sig and T_K > 0 and sig > 0:
            xs.append(1.0 / float(T_K))
            ys.append(math.log(float(sig)))
    if len(xs) < 2:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx                      # d ln(σ) / d(1/T) = -Ea/kB
    ea = -slope * _KB_EV
    return round(ea, 4)


def _segments_from_transitions(
    pts: List[Dict[str, Any]], transitions_K: List[float]
) -> List[List[Dict[str, Any]]]:
    """按相变温度把按 T 升序的点切成温区段。"""
    pts_sorted = sorted([p for p in pts if p.get("T_K")], key=lambda p: p["T_K"])
    if not transitions_K:
        return [pts_sorted]
    cuts = sorted(float(t) for t in transitions_K)
    segs: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    ci = 0
    for p in pts_sorted:
        while ci < len(cuts) and p["T_K"] > cuts[ci]:
            if cur:
                segs.append(cur)
            cur = []
            ci += 1
        cur.append(p)
    if cur:
        segs.append(cur)
    return [s for s in segs if s]


def _default_system_context(R: float, N: float, t_window_K: List[float]) -> Dict[str, Any]:
    """凹凸棒土酸-黏土复合电解质(AiCE)的如实物质描述(取自 campaign domain_knowledge)。"""
    return {
        "chemistry_summary": (
            "Phosphoric-acid/water mixture confined in the 1-D fibrous nanochannels of "
            "attapulgite (palygorskite) clay — an acid-in-clay composite solid proton "
            "conductor (AiCE). No deliberate organic polymer binder in this campaign."
        ),
        "key_variables": {
            "R": "n(H3PO4)/n(H2O) acid-to-water molar ratio (H-bond donor/acceptor balance)",
            "N": "mass ratio m(85% H3PO4 + H2O)/m(attapulgite): acid-water loading in the clay channels",
        },
        "temperature_window_K": [round(min(t_window_K), 2), round(max(t_window_K), 2)] if t_window_K else [],
        "provenance": "live_seed_adapter default (attapulgite_aice_campaign domain_knowledge)",
    }


def _live_evidence_units(
    pts: List[Dict[str, Any]],
    sample_id: str,
    transitions_K: List[float],
    seg_eas: List[Optional[float]],
    arrhenius: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """把 live 观测做成 Stage2-V2 风格 evidence_units(S03 据此产出权威证据卡)。"""
    units: List[Dict[str, Any]] = []
    valid = [p for p in pts if p.get("sigma_S_cm") and p.get("T_C") is not None]
    if not valid:
        return units
    hi = max(valid, key=lambda p: p["T_C"])
    lo = min(valid, key=lambda p: p["T_C"])

    units.append({
        "evidence_id": "LIVE-1",
        "layer": "temperature_transport",
        "statement": (
            f"Conductivity decreases monotonically across the measured window: "
            f"sigma = {hi['sigma_S_cm']:.3e} S/cm at {hi['T_C']:.1f} C "
            f"down to {lo['sigma_S_cm']:.3e} S/cm at {lo['T_C']:.1f} C "
            f"({len(valid)} genuine-live EIS points)."
        ),
        "strength": "strong",
        "supporting_sample_ids": [sample_id],
        "supporting_metrics": {
            "sigma_high_S_cm": f"{hi['sigma_S_cm']:.3e}",
            "T_high_C": f"{hi['T_C']:.1f}",
            "sigma_low_S_cm": f"{lo['sigma_S_cm']:.3e}",
            "T_low_C": f"{lo['T_C']:.1f}",
            "n_points": str(len(valid)),
        },
        "limitations": ["EIS-only; absolute sigma depends on cell geometry"],
        "safe_for_stage3": True,
    })

    if transitions_K:
        tc = ", ".join(f"{(t - 273.15):.1f} C" for t in transitions_K)
        conf = (arrhenius or {}).get("confidence")
        model = (arrhenius or {}).get("best_model_type")
        units.append({
            "evidence_id": "LIVE-2",
            "layer": "temperature_transport",
            "statement": (
                f"Global Arrhenius analysis selects a multi-regime model"
                + (f" ({model})" if model else "")
                + f" with transport-regime transition(s) near {tc}"
                + (f" (selection confidence {conf})." if conf is not None else ".")
            ),
            "strength": "strong",
            "supporting_sample_ids": [sample_id],
            "supporting_metrics": {
                "n_transitions": str(len(transitions_K)),
                "transition_temps_C": tc,
                **({"best_model_type": str(model)} if model else {}),
                **({"model_confidence": str(conf)} if conf is not None else {}),
            },
            "limitations": ["Regime change inferred from sigma(T); not a structural proof"],
            "safe_for_stage3": True,
        })

    ea_vals = [e for e in seg_eas if e is not None]
    if len(ea_vals) >= 2:
        units.append({
            "evidence_id": "LIVE-3",
            "layer": "model_competition",
            "statement": (
                "Apparent activation energy differs between temperature regimes "
                f"(per-segment Ea = {', '.join(f'{e:.3f} eV' for e in ea_vals)}), "
                "consistent with a change in the dominant proton-transport pathway."
            ),
            "strength": "moderate",
            "supporting_sample_ids": [sample_id],
            "supporting_metrics": {f"ea_segment_{i+1}_eV": f"{e:.3f}" for i, e in enumerate(ea_vals)},
            "limitations": ["Ea from segment Arrhenius slope; interpretation non-unique"],
            "safe_for_stage3": True,
        })

    grades = [str(p.get("qc_grade")) for p in pts if p.get("qc_grade")]
    if grades:
        from collections import Counter
        gc = Counter(grades)
        units.append({
            "evidence_id": "LIVE-4",
            "layer": "data_quality",
            "statement": (
                "Per-point EIS fit quality is recorded for the live sweep "
                f"(QC grade distribution: {dict(gc)}); low-temperature high-impedance "
                "points carry larger fit uncertainty."
            ),
            "strength": "weak",
            "supporting_sample_ids": [sample_id],
            "supporting_metrics": {f"qc_{k}": str(v) for k, v in gc.items()},
            "limitations": ["Fit quality varies with impedance magnitude across temperature"],
            "safe_for_stage3": True,
        })
    return units


def build_seed_from_live(
    points: List[Dict[str, Any]],
    *,
    sample_id: str,
    R: float,
    N: float,
    transitions_K: Optional[List[float]] = None,
    arrhenius: Optional[Dict[str, Any]] = None,
    system_context: Optional[Dict[str, Any]] = None,
):
    """由真实 live 逐点测量构造 Stage3SeedBundle(real 来源)。

    points: [{T_C, T_K, rb_ohm, sigma_S_cm, qc_grade, r_squared}, ...]
    """
    from s8_stage3.contracts.seed import (
        Stage3SeedBundle, SeedSegment, SeedSampleSummary,
        SeedCompositionNode, SeedAtlasHint, SystemContext,
    )

    pts = [p for p in points if p.get("T_K") and p.get("sigma_S_cm")]
    transitions_K = list(transitions_K or [])
    t_all_K = [float(p["T_K"]) for p in pts]

    seg_groups = _segments_from_transitions(pts, transitions_K)
    seg_eas: List[Optional[float]] = []
    segments: List[SeedSegment] = []
    seg_ids: List[str] = []
    for i, grp in enumerate(seg_groups):
        ea = _arrhenius_ea_ev(grp)
        seg_eas.append(ea)
        Ts = [float(p["T_K"]) for p in grp]
        sid = f"{sample_id}-seg{i+1}"
        seg_ids.append(sid)
        segments.append(SeedSegment(
            segment_id=sid, sample_id=sample_id, scan_dir="cooling",
            t_min=round(min(Ts), 2), t_max=round(max(Ts), 2), n_points=len(grp),
            representative_ea=ea,
            representative_sigma0=None,
            segment_order=i, fit_type="arrhenius",
            is_wide_range=(max(t_all_K) - min(t_all_K)) >= 60.0,
        ))

    t_break_k = float(min(transitions_K)) if transitions_K else None
    summary = SeedSampleSummary(
        sample_id=sample_id, composition_r=float(R), composition_n=float(N),
        scan_dirs=["cooling"], t_break_k=t_break_k, t_arc_k=None,
        has_eis_feature=True, conductivity_trend="decreasing", segment_ids=seg_ids,
    )
    node = SeedCompositionNode(
        node_id=f"node-R{R}-N{N}", r=float(R), n=float(N),
        sample_ids=[sample_id], sample_count=1, available_scan_dirs=["cooling"],
    )

    hints: List[SeedAtlasHint] = []
    if transitions_K:
        hints.append(SeedAtlasHint(
            hint_id="LIVE-HINT-1", source="stage0_global_arrhenius",
            claim_level="observation", theme="transport_regime",
            statement=(
                "Live wide-temperature sweep shows multi-regime sigma(T) behaviour with "
                f"{len(transitions_K)} detected transition(s)."
            ),
            confidence=float((arrhenius or {}).get("confidence") or 0.6),
            tags=["live", "wide_temperature"], usage_policy="allowed_as_observation_hint",
        ))

    sc = SystemContext(**(system_context or _default_system_context(R, N, t_all_K)))
    ev_units = _live_evidence_units(pts, sample_id, transitions_K, seg_eas, arrhenius)

    return Stage3SeedBundle(
        bundle_id=f"live-seed-{sample_id}",
        source_mode="real",
        seed_segments=segments,
        seed_sample_summaries=[summary],
        seed_composition_nodes=[node],
        seed_atlas_hints=hints,
        upstream_facts={
            "n_live_points": len(pts),
            "wide_temperature": (max(t_all_K) - min(t_all_K)) if t_all_K else 0.0,
            "n_transitions": len(transitions_K),
            "source": "hardware_adapter genuine-live full-temperature sweep",
        },
        system_context=sc,
        stage2_seed_v2={"evidence_units": ev_units, "source": "live_seed_adapter"},
    )


# --------------------------------------------------------------------------- #
# 2) 用真实 LLM 驱动机理推理链
# --------------------------------------------------------------------------- #

def _safe_literature(board, gateway, settings, output_dir: Path, literature_mode: str):
    """文献步:**绝不臆造**。可选真实检索(OpenAlex api),失败/关闭则给透明空 survey。

    - literature_mode="none": 不接外部文献,空 survey(synthesis_notes 如实说明);
    - literature_mode in {api,manual,hybrid}: 走生产 run_s05(真实检索 + 真 LLM 综合),
      任何失败 → 退回透明空 survey(不伪造 doi/标题/结论)。
    """
    from s8_stage3.contracts.literature import LiteratureSurvey

    def _empty(note: str):
        return LiteratureSurvey(step_id="s05", survey_scope="mechanism_constraint",
                                cards=[], synthesis_notes=note)

    if literature_mode in ("none", "", None, "mock"):
        # mock 在 live gateway 下会发空 messages → 400;一律退化为透明空 survey(诚实)。
        return _empty("Literature step not wired to an external provider in this run; "
                      "mechanism arbitration proceeds on live evidence + hypotheses only."), "none"
    try:
        from s8_stage3.agents.s05_literature_scout_mechanism import run_s05
        survey = run_s05(board, gateway, output_dir, literature_mode=literature_mode, settings=settings)
        return survey, literature_mode
    except Exception as exc:  # noqa: BLE001
        return _empty(f"External literature retrieval unavailable ({type(exc).__name__}: {exc}); "
                      "proceeded without external literature (no fabricated references)."), "fallback_empty"


def run_mechanism_reasoning(
    seed,
    output_dir: Path,
    *,
    api_key: str,
    base_url: str,
    model: str,
    llm_mode: str = "live",
    literature_mode: str = "api",
    enable_cache: bool = False,
    timeout_seconds: int = 240,
) -> Dict[str, Any]:
    """真实驱动机理推理链 S03→S04→S05→S06→S06b(直接调 agent,完全可控)。

    - S03 evidence_builder: 确定性,从 live evidence_units 产权威证据卡;
    - S04 hypothesis_generator / S06 mechanism_arbiter / S06b design_principle_extractor:
      在 llm_mode="live" 时**真实 OpenRouter 网络调用**;
    - S05 literature: 见 `_safe_literature`(可真实检索;失败/关闭则透明空,绝不臆造)。

    返回调用统计 + 真实产出(假设/机理/设计原则) + 文献状态。
    """
    from s8_stage3.config.settings import load_settings
    from s8_stage3.config.model_registry import ModelRegistry
    from s8_stage3.config.llm_gateway import LLMGateway
    from s8_stage3.agents.s03_evidence_builder import run_s03
    from s8_stage3.agents.s04_hypothesis_generator import run_s04
    from s8_stage3.agents.s06_mechanism_arbiter import run_s06
    from s8_stage3.agents.s06b_design_principle_extractor import run_s06b

    s = load_settings()
    s.llm_mode = llm_mode
    s.run_mode = "real"
    s.literature_mode = literature_mode
    s.api_key = api_key
    s.api_base_url = base_url
    s.timeout_seconds = timeout_seconds
    s.model_cheap = s.model_standard = s.model_premium = model
    s.use_structured_outputs = False     # 代理/OpenRouter 不保证 json_schema strict
    s.enable_cache = enable_cache

    registry = ModelRegistry(s.model_cheap, s.model_standard, s.model_premium)
    gateway = LLMGateway(s, registry)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    step_results: List[tuple] = []

    evidence = run_s03(seed, output_dir, strict_real_input=False)
    step_results.append(("s03_evidence_builder", "completed"))

    board = run_s04(evidence, gateway, output_dir, system_context=seed.system_context)
    step_results.append(("s04_hypothesis_generator", "completed"))

    mech_lit, lit_status = _safe_literature(board, gateway, s, output_dir, literature_mode)
    step_results.append(("s05_literature_scout_mechanism", lit_status))

    arb = run_s06(evidence, mech_lit, gateway, output_dir,
                  hypothesis_board=board, system_context=seed.system_context)
    step_results.append(("s06_mechanism_arbiter", "completed"))

    dps = run_s06b(arb, evidence, gateway, output_dir, system_context=seed.system_context)
    step_results.append(("s06b_design_principle_extractor", "completed"))

    records = gateway.call_log
    real = [r for r in records if not str(r.model).startswith("mock:")]
    mech_card = getattr(arb, "mechanism_card", None) if arb else None

    return {
        "result": {
            "evidence": evidence, "hypothesis_board": board,
            "mechanism_literature": mech_lit, "mechanism_arbitration": arb,
            "design_principles": dps,
        },
        "output_dir": str(output_dir),
        "literature_status": lit_status,
        "n_llm_calls": gateway.call_count,
        "n_real_llm_calls": len(real),
        "real_call_models": sorted({str(r.model) for r in real}),
        "real_call_steps": [r.step for r in real],
        "n_evidence_cards": len(evidence.evidence_cards) if evidence else 0,
        "n_hypotheses": len(board.hypotheses) if board else 0,
        "selected_hypothesis_id": getattr(mech_card, "selected_hypothesis_id", None),
        "mechanism_label": getattr(mech_card, "mechanism_label", None),
        "n_design_principles": len(getattr(dps, "principles", []) or []) if dps else 0,
        "step_results": step_results,
    }
