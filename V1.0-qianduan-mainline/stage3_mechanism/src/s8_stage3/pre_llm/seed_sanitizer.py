"""Seed Sanitizer — 在送入 LLM 前对异常数值进行标记（不修改原始数据）。

输出 sanitized_seed_digest.json 供 prompt packing 使用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from s8_stage3.contracts.seed import Stage3SeedBundle


@dataclass
class SanitizationFlag:
    sample_id: str
    flag_type: str
    detail: str
    severity: str = "warning"  # warning | info

    def __init__(self, sample_id: str, flag_type: str, detail: str, severity: str = "warning"):
        self.sample_id = sample_id
        self.flag_type = flag_type
        self.detail = detail
        self.severity = severity

    def to_dict(self) -> dict:
        return {
            "sample_id": self.sample_id,
            "flag_type": self.flag_type,
            "detail": self.detail,
            "severity": self.severity,
        }


def _check_sample(summary: Any, flags: list[SanitizationFlag]) -> None:
    sid = summary.sample_id
    t_break = summary.t_break_k
    t_arc = summary.t_arc_k
    trend = summary.conductivity_trend

    if t_arc is not None and t_break is not None:
        if t_arc > t_break:
            flags.append(SanitizationFlag(
                sid, "t_arc_gt_t_break",
                f"T_arc ({t_arc}K) > T_break ({t_break}K); unusual, mark as suspicious",
                "warning",
            ))
        if abs(t_arc - t_break) < 2.0:
            flags.append(SanitizationFlag(
                sid, "t_arc_near_t_break",
                f"T_arc ≈ T_break (diff={abs(t_arc - t_break):.1f}K); hard to distinguish",
                "info",
            ))

    if t_arc is not None and t_break is not None:
        max_t = max(t_arc, t_break)
        if t_arc > 0.9 * max_t:
            flags.append(SanitizationFlag(
                sid, "t_arc_near_max_t",
                f"T_arc ({t_arc}K) close to sample max T; possible measurement artifact",
                "warning",
            ))

    if "decreasing" in trend:
        flags.append(SanitizationFlag(
            sid, "decreasing_conductivity_trend",
            "Conductivity decreases with T; unusual for proton transport — verify segment count",
            "warning",
        ))


def sanitize_seed(bundle: Stage3SeedBundle) -> dict[str, Any]:
    """生成 sanitized seed digest（不修改原始 bundle）。"""
    flags: list[SanitizationFlag] = []
    segment_flags: dict[str, list[str]] = {}

    for summary in bundle.seed_sample_summaries:
        _check_sample(summary, flags)

    # 低 Ea 段检查
    for seg in bundle.seed_segments:
        ea = seg.representative_ea
        if ea is None:
            if (seg.fit_type or "").lower() == "vtf":
                continue
            flags.append(SanitizationFlag(
                seg.sample_id, "missing_ea",
                f"Segment {seg.segment_id}: representative_ea is None",
                "warning",
            ))
            segment_flags.setdefault(seg.segment_id, []).append("missing_ea")
        elif ea < 0.05:
            flags.append(SanitizationFlag(
                seg.sample_id, "low_ea",
                f"Segment {seg.segment_id}: Ea={ea:.3f} eV < 0.05 eV — low confidence",
                "warning",
            ))
            segment_flags.setdefault(seg.segment_id, []).append("low_ea")

    digest = {
        "bundle_id": bundle.bundle_id,
        "n_samples": len(bundle.seed_sample_summaries),
        "n_segments": len(bundle.seed_segments),
        "sanitization_flags": [f.to_dict() for f in flags],
        "flagged_segment_ids": segment_flags,
        "upstream_facts": bundle.upstream_facts,
        "composition_nodes_summary": [
            {"node_id": n.node_id, "r": n.r, "n": n.n, "sample_count": n.sample_count}
            for n in bundle.seed_composition_nodes
        ],
        "note": (
            "Flagged values are preserved in the original bundle but should not be "
            "treated as strong numeric evidence when passed to LLM agents."
        ),
    }
    return digest


def format_sanitizer_warnings_for_prompt(digest: dict) -> str:
    flags = digest.get("sanitization_flags", [])
    if not flags:
        return "No data quality warnings detected."
    lines = [f"[{f['severity'].upper()}] {f['sample_id']}: {f['detail']}" for f in flags]
    return "Data quality warnings (treat flagged values with caution):\n" + "\n".join(lines)
