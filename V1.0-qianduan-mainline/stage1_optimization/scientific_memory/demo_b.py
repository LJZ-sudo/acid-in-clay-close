# -*- coding: utf-8 -*-
"""🅱️ Demo B（M5-B Tier S 解锁演示）— 用两个真实历史失效事件验证反事实失效传播。

真实事件(均有据,非臆造):
  1. KK 符号 bug:历史上 KK 残差曾用 Z=zreal−1j*zimag(错号),误报部分谱 KK 不一致;
     已修正为 +1j(见 eis_pipeline.py / kk_validation.py 注释)。
  2. ECE 随机划分泄漏:手稿旧 ECE=0.05 来自随机划分(泄漏),已弃用,改留一数据集 0.13
     (见 PUBLICATION_READINESS §0 / PROJECT_SITUATION_REPORT §6)。
  + 独立支持示例:LRS 亚零度转变由两个独立数据集(6.15_merged、6.12)各自支持。

演示:把 buggy/leaked 证据标 INVALID → 下游主张自动按四值逻辑降级 + 旧决策标 AFFECTED;
独立支持链(6.12)仍在 → 转变主张保持 SUPPORTED。
验收:失效证据被检索率=0 / 下游主张自动重算=100% / 独立支持链存活=100%。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

_THIS = Path(__file__).resolve()
STAGE1 = _THIS.parents[1]
if str(STAGE1) not in sys.path:
    sys.path.insert(0, str(STAGE1))

from scientific_memory.claim_graph import ClaimGraph, NodeType  # noqa: E402
from scientific_memory.invalidation_engine import InvalidationEngine  # noqa: E402

REPO_ROOT = _THIS.parents[3]
OUT_DIR = REPO_ROOT / "research" / "scientific_memory"


def build_demo_graph(db_path: str = ":memory:") -> ClaimGraph:
    g = ClaimGraph(db_path)

    # ---- 事件 1:KK 符号 bug ----
    g.add_node("E_kk_buggy", NodeType.EVIDENCE, "KK residuals with Z=zreal-1j*zimag (sign bug)")
    g.add_node("E_kk_fixed", NodeType.EVIDENCE, "KK recomputed with +1j sign -> spectra pass")
    g.add_node("C_kk_fail", NodeType.CLAIM, "subset of LRS spectra are KK-inconsistent")
    g.add_support(["E_kk_buggy"], "C_kk_fail", set_id="ss_kk_buggy")
    g.add_refute(["E_kk_fixed"], "C_kk_fail", set_id="rs_kk_fixed")
    g.add_node("D_exclude", NodeType.CLAIM, "decision: exclude those spectra from analysis")
    g.add_dependency("D_exclude", "C_kk_fail")   # 决策依赖于"谱 KK 失败"主张

    # ---- 事件 2:ECE 随机划分泄漏 ----
    g.add_node("E_ece_randsplit", NodeType.EVIDENCE, "ECE=0.05 from random split (leakage)")
    g.add_node("E_ece_lodo", NodeType.EVIDENCE, "ECE=0.13 from leave-one-dataset-out (no leak)")
    g.add_node("C_ece_005", NodeType.CLAIM, "calibration achieves ECE=0.05")
    g.add_node("C_ece_013", NodeType.CLAIM, "calibration achieves ECE=0.13 (honest)")
    g.add_support(["E_ece_randsplit"], "C_ece_005", set_id="ss_ece_rand")
    g.add_support(["E_ece_lodo"], "C_ece_013", set_id="ss_ece_lodo")
    g.add_node("D_manuscript_ece", NodeType.CLAIM, "manuscript ECE value")
    g.add_dependency("D_manuscript_ece", "C_ece_005")  # 手稿旧值依赖泄漏证据

    # ---- 独立支持示例:亚零度转变 ----
    g.add_node("E_lrs_615merged", NodeType.EVIDENCE, "LRS 6.15_merged dataset")
    g.add_node("E_lrs_612", NodeType.EVIDENCE, "LRS 6.12 dataset")
    g.add_node("C_transition", NodeType.CLAIM, "LRS shows sub-zero conduction transition")
    g.add_support(["E_lrs_615merged"], "C_transition", set_id="ss_615")  # 独立支持集 A
    g.add_support(["E_lrs_612"], "C_transition", set_id="ss_612")        # 独立支持集 B

    g.recompute_all(cause="demo_b_init")
    return g


def run(db_path: str = ":memory:") -> Dict[str, Any]:
    g = build_demo_graph(db_path)
    eng = InvalidationEngine(g)

    # 同时失效:两个真实 bug 证据 + 一个独立支持(测存活)
    report = eng.mark_invalid(
        ["E_kk_buggy", "E_ece_randsplit", "E_lrs_615merged"],
        reason="KK_sign_bug + ECE_random_split_leak + independent_support_stress")

    result = {
        "demo": "B - counterfactual proof-carrying memory",
        "real_events": [
            "KK sign bug (Z=zreal-1j*zimag -> +1j)",
            "ECE random-split leak (0.05 -> LODO 0.13)",
        ],
        "report": report.to_dict(),
        "narrative_checks": {
            "C_kk_fail_before": report.claim_status_before["C_kk_fail"],
            "C_kk_fail_after": report.claim_status_after["C_kk_fail"],
            "D_exclude_affected": "D_exclude" in report.affected_claims,
            "C_ece_005_before": report.claim_status_before["C_ece_005"],
            "C_ece_005_after": report.claim_status_after["C_ece_005"],
            "D_manuscript_ece_affected": "D_manuscript_ece" in report.affected_claims,
            "C_ece_013_stays_supported": report.claim_status_after["C_ece_013"] == "SUPPORTED",
            "C_transition_survives_via_independent_support":
                report.claim_status_after["C_transition"] == "SUPPORTED",
        },
        "acceptance": report.metrics,
        "acceptance_pass": (
            report.metrics["invalidated_evidence_retrieval_rate"] == 0.0
            and report.metrics["downstream_claim_recomputation_rate"] == 1.0
            and report.metrics["independent_support_preservation_rate"] == 1.0
        ),
    }
    g.close()
    return result


def write_report() -> Dict[str, Any]:
    res = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "demo_b_invalidation_report.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


if __name__ == "__main__":
    res = write_report()
    print("Demo B acceptance:", json.dumps(res["acceptance"], ensure_ascii=False))
    print("acceptance_pass:", res["acceptance_pass"])
    nc = res["narrative_checks"]
    print(f"  C_kk_fail: {nc['C_kk_fail_before']} -> {nc['C_kk_fail_after']} "
          f"| D_exclude AFFECTED={nc['D_exclude_affected']}")
    print(f"  C_ece_005: {nc['C_ece_005_before']} -> {nc['C_ece_005_after']} "
          f"| D_manuscript_ece AFFECTED={nc['D_manuscript_ece_affected']}")
    print(f"  C_ece_013 stays SUPPORTED={nc['C_ece_013_stays_supported']}")
    print(f"  C_transition survives via independent support="
          f"{nc['C_transition_survives_via_independent_support']}")
