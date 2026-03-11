import argparse
import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class MechanismPoint:
    T_C: float
    T_K: float
    invT_1_per_K: float
    Rb_ohm: Optional[float]
    sigma_S_per_cm: Optional[float]
    log10_sigma: Optional[float]
    quality: Optional[str]
    source_file: Optional[str]


@dataclass
class MechanismSegment:
    T_range_C: Tuple[float, float]
    N_points: int
    Ea_kJ_mol: Optional[float]
    slope: Optional[float]
    intercept: Optional[float]
    fit_r2: Optional[float]
    quality_summary: Optional[str]


def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _fmt_eng(val: Optional[float], fmt: str = ".3e") -> str:
    if val is None:
        return "NA"
    try:
        return format(val, fmt)
    except Exception:
        return "NA"


def _fmt_sig(val: Optional[float], sig: int = 3) -> str:
    if val is None:
        return "NA"
    try:
        return f"{val:.{sig}g}"
    except Exception:
        return "NA"


def _load_report(path: str) -> Dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"report.json 不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_sample(report: Dict) -> Dict:
    config = report.get("configuration", {}) if report else {}
    return {
        "thickness_cm": config.get("thickness_cm"),
        "area_cm2": config.get("area_cm2"),
    }


def _build_points(report: Dict) -> List[MechanismPoint]:
    points = []
    succ = report.get("successful_points", []) or []
    for r in succ:
        t_c = _safe_float(r.get("temperature_C"))
        t_k = _safe_float(r.get("temperature_K")) or (t_c + 273.15 if t_c is not None else None)
        rb = _safe_float(r.get("rb_ohm"))
        sigma = _safe_float(r.get("conductivity_S_per_cm"))
        log_sigma = math.log10(sigma) if sigma and sigma > 0 else None
        if t_c is None and t_k is None:
            continue
        point = MechanismPoint(
            T_C=t_c if t_c is not None else (t_k - 273.15 if t_k is not None else 0.0),
            T_K=t_k if t_k is not None else (t_c + 273.15 if t_c is not None else 0.0),
            invT_1_per_K=1.0 / t_k if t_k and t_k != 0 else None,
            Rb_ohm=rb,
            sigma_S_per_cm=sigma,
            log10_sigma=log_sigma,
            quality=r.get("quality") or r.get("fit_quality"),
            source_file=r.get("raw_data_path"),
        )
        points.append(point)
    points.sort(key=lambda p: p.T_C)
    return points


def _build_segments(report: Dict) -> List[MechanismSegment]:
    arr = report.get("arrhenius_analysis", {}) if report else {}
    segs = arr.get("segments", []) or []
    out: List[MechanismSegment] = []
    for seg in segs:
        t_range_c = seg.get("T_range_C") or (None, None)
        slope = seg.get("slope") if isinstance(seg.get("slope"), (int, float)) else None
        intercept = seg.get("intercept") if isinstance(seg.get("intercept"), (int, float)) else None
        fit_r2 = seg.get("fit_r2") if isinstance(seg.get("fit_r2"), (int, float)) else None
        out.append(
            MechanismSegment(
                T_range_C=(
                    _safe_float(t_range_c[0]) if t_range_c and len(t_range_c) > 0 else None,
                    _safe_float(t_range_c[1]) if t_range_c and len(t_range_c) > 1 else None,
                ),
                N_points=seg.get("data_points") or seg.get("points") or seg.get("data_points_count") or 0,
                Ea_kJ_mol=_safe_float(seg.get("Ea_kJ_per_mol")),
                slope=_safe_float(slope),
                intercept=_safe_float(intercept),
                fit_r2=_safe_float(fit_r2),
                quality_summary=seg.get("quality") or seg.get("fit_quality"),
            )
        )
    return out


def _diagnose(points: List[MechanismPoint], segments: List[MechanismSegment]) -> Dict:
    rb_jumps = []
    sigma_jumps = []
    poor_runs = []
    ea_turns = []

    # Rb/sigma jumps
    for i in range(1, len(points)):
        p0, p1 = points[i - 1], points[i]
        if p0.Rb_ohm and p1.Rb_ohm and p0.Rb_ohm > 0 and p1.Rb_ohm > 0:
            ratio = p1.Rb_ohm / p0.Rb_ohm
            if ratio >= 3.0 or ratio <= 1 / 3:
                rb_jumps.append(
                    {
                        "from_T": p0.T_C,
                        "to_T": p1.T_C,
                        "ratio": ratio,
                        "Rb0": p0.Rb_ohm,
                        "Rb1": p1.Rb_ohm,
                    }
                )
        if p0.sigma_S_per_cm and p1.sigma_S_per_cm and p0.sigma_S_per_cm > 0 and p1.sigma_S_per_cm > 0:
            ratio = p1.sigma_S_per_cm / p0.sigma_S_per_cm
            if ratio >= 3.0 or ratio <= 1 / 3:
                sigma_jumps.append(
                    {
                        "from_T": p0.T_C,
                        "to_T": p1.T_C,
                        "ratio": ratio,
                        "sigma0": p0.sigma_S_per_cm,
                        "sigma1": p1.sigma_S_per_cm,
                    }
                )

    # Poor runs
    run_start = None
    run_len = 0
    for p in points:
        if p.quality and str(p.quality).lower() == "poor":
            if run_start is None:
                run_start = p.T_C
            run_len += 1
        else:
            if run_len >= 2:
                poor_runs.append({"start_T": run_start, "end_T": points[points.index(p) - 1].T_C, "n": run_len})
            run_start = None
            run_len = 0
    if run_len >= 2:
        poor_runs.append({"start_T": run_start, "end_T": points[-1].T_C, "n": run_len})

    # Ea turns
    for i in range(1, len(segments)):
        prev = segments[i - 1].Ea_kJ_mol
        curr = segments[i].Ea_kJ_mol
        if prev is None or curr is None:
            continue
        delta = abs(curr - prev)
        if delta > 15:
            ea_turns.append(
                {
                    "from_seg": i,
                    "to_seg": i + 1,
                    "delta_Ea_kJ_mol": delta,
                    "Ea_prev": prev,
                    "Ea_curr": curr,
                    "T_prev": segments[i - 1].T_range_C,
                    "T_curr": segments[i].T_range_C,
                }
            )

    return {
        "rb_jumps": rb_jumps,
        "sigma_jumps": sigma_jumps,
        "poor_runs": poor_runs,
        "ea_turns": ea_turns,
    }


def build_mechanism_evidence(report: Dict) -> Dict:
    points = _build_points(report)
    segments = _build_segments(report)
    diagnostics = _diagnose(points, segments)
    sample = _extract_sample(report)

    points_out = []
    for p in points:
        points_out.append(
            {
                "T_C": p.T_C,
                "T_K": p.T_K,
                "invT_1_per_K": p.invT_1_per_K,
                "Rb_ohm": p.Rb_ohm,
                "sigma_S_per_cm": p.sigma_S_per_cm,
                "log10_sigma": p.log10_sigma,
                "quality": p.quality,
                "source_file": p.source_file,
            }
        )

    seg_out = []
    for s in segments:
        seg_out.append(
            {
                "T_range_C": s.T_range_C,
                "N_points": s.N_points,
                "Ea_kJ_mol": s.Ea_kJ_mol,
                "slope": s.slope,
                "intercept": s.intercept,
                "fit_r2": s.fit_r2,
                "quality_summary": s.quality_summary,
            }
        )

    evidence = {
        "sample": sample,
        "points": points_out,
        "segments": seg_out,
        "diagnostics": diagnostics,
    }
    return evidence


def _quality_stats(points: List[MechanismPoint]) -> Dict:
    stats = {"good": 0, "acceptable": 0, "poor": 0, "unknown": 0}
    for p in points:
        q = str(p.quality).lower() if p.quality else "unknown"
        if q in stats:
            stats[q] += 1
        else:
            stats["unknown"] += 1
    return stats


def _sigma_range(points: List[MechanismPoint]) -> Tuple[Optional[float], Optional[float]]:
    vals = [p.sigma_S_per_cm for p in points if p.sigma_S_per_cm and p.sigma_S_per_cm > 0]
    if not vals:
        return None, None
    return min(vals), max(vals)


def _rb_range(points: List[MechanismPoint]) -> Tuple[Optional[float], Optional[float]]:
    vals = [p.Rb_ohm for p in points if p.Rb_ohm and p.Rb_ohm > 0]
    if not vals:
        return None, None
    return min(vals), max(vals)


def _format_points_table(points: List[MechanismPoint]) -> str:
    if not points:
        return "_无成功点_"
    header = "| T(°C) | Rb(Ω) | σ(S/cm) | log10σ | quality | source_file |\n|---|---|---|---|---|---|"
    lines = [header]
    for i, p in enumerate(points, 1):
        lines.append(
            f"| {p.T_C:.1f} | {_fmt_sig(p.Rb_ohm)} | {_fmt_eng(p.sigma_S_per_cm)} | "
            f"{_fmt_sig(p.log10_sigma,3)} | {p.quality or 'NA'} | {p.source_file or ''} |"
        )
        if i % 15 == 0:
            lines.append("\n" + header)
    return "\n".join(lines)


def _format_segments(segments: List[MechanismSegment]) -> str:
    if not segments:
        return "- 无分段结果\n"
    lines = []
    for s in segments:
        t0, t1 = s.T_range_C
        lines.append(
            f"- T_range: {t0:.1f}~{t1:.1f}°C | N={s.N_points} | Ea={_fmt_sig(s.Ea_kJ_mol,3)} kJ/mol "
            f"| r2={_fmt_sig(s.fit_r2,3)} | quality={s.quality_summary or 'NA'}"
        )
    lines.append(
        "\n提示：Ea 拐点可能对应载流子机制变化/玻璃化或相变/含水或塑化状态变化/界面极化变化等方向，可结合 Nyquist 与控湿/控压/频段扩展复核。"
    )
    return "\n".join(lines)


def _format_anomalies(diag: Dict) -> str:
    lines = []
    if diag.get("rb_jumps"):
        lines.append("Rb 跳变:")
        for j in diag["rb_jumps"]:
            lines.append(
                f"- {j['from_T']:.1f}→{j['to_T']:.1f}°C, ratio={_fmt_sig(j['ratio'],3)} "
                f"(Rb0={_fmt_sig(j['Rb0'])}, Rb1={_fmt_sig(j['Rb1'])})"
            )
    if diag.get("sigma_jumps"):
        lines.append("σ 突变:")
        for j in diag["sigma_jumps"]:
            lines.append(
                f"- {j['from_T']:.1f}→{j['to_T']:.1f}°C, ratio={_fmt_sig(j['ratio'],3)} "
                f"(σ0={_fmt_eng(j['sigma0'])}, σ1={_fmt_eng(j['sigma1'])})"
            )
    if diag.get("poor_runs"):
        lines.append("连续 poor 区间:")
        for r in diag["poor_runs"]:
            lines.append(f"- {r['start_T']:.1f}~{r['end_T']:.1f}°C, n={r['n']}")
    if diag.get("ea_turns"):
        lines.append("Ea 拐点:")
        for t in diag["ea_turns"]:
            lines.append(
                f"- seg{t['from_seg']}→seg{t['to_seg']}, ΔEa={_fmt_sig(t['delta_Ea_kJ_mol'],3)} kJ/mol, "
                f"T_prev={t['T_prev']}, T_curr={t['T_curr']}"
            )
    if not lines:
        lines.append("- 未检测到显著异常")
    lines.append(
        "\n复核建议：对异常点/poor 区间优先复测；查看 Nyquist 形貌；必要时扩展频段/控湿/控压/界面处理做对照。"
    )
    return "\n".join(lines)


def build_mechanism_prompt(report: Dict) -> str:
    points = _build_points(report)
    segments = _build_segments(report)
    diag = _diagnose(points, segments)
    sample = _extract_sample(report)
    qstats = _quality_stats(points)
    sigma_min, sigma_max = _sigma_range(points)
    rb_min, rb_max = _rb_range(points)

    lines = []
    lines.append("## Role & Task")
    lines.append("你是电化学/固态离子导体专家，目标是基于给定实验数据做机理推断（非项目总结）。")

    lines.append("\n## Data Snapshot")
    lines.append(
        f"- 样品: 厚度={sample.get('thickness_cm')} cm, 面积={sample.get('area_cm2')} cm²"
    )
    lines.append(f"- 温度点数: {len(points)}")
    lines.append(f"- σ范围: {_fmt_eng(sigma_min)} ~ {_fmt_eng(sigma_max)} S/cm")
    lines.append(f"- Rb范围: {_fmt_sig(rb_min)} ~ {_fmt_sig(rb_max)} Ω")
    lines.append(
        f"- 质量统计: good={qstats['good']}, acceptable={qstats['acceptable']}, poor={qstats['poor']}, unknown={qstats['unknown']}"
    )
    if diag.get("poor_runs"):
        runs_str = "; ".join([f"{r['start_T']:.1f}~{r['end_T']:.1f}°C(n={r['n']})" for r in diag["poor_runs"]])
        lines.append(f"- 连续 poor 区间: {runs_str}")
    else:
        lines.append("- 连续 poor 区间: 无")

    lines.append("\n## Temperature-point Table")
    lines.append(_format_points_table(points))

    lines.append("\n## Arrhenius Segments")
    lines.append(_format_segments(segments))

    lines.append("\n## Anomalies & Checks")
    lines.append(_format_anomalies(diag))

    lines.append("\n## Mechanism Hypotheses（大模型需输出）")
    lines.append(
        "请给出 3-5 个可检验假设。每个假设必须包含："
        "引用表格或分段的具体数值/温区 -> 可能原因 -> 如何验证（增加何种测量/对照/拟合/控湿/控压等）。"
    )

    lines.append("\n## Output Format（严格遵守）")
    lines.append(
        "以固定小标题输出：\n"
        "- Observations\n"
        "- Segment-wise interpretation\n"
        "- Competing hypotheses\n"
        "- Recommended next experiments\n"
        "- Risks & confounders"
    )
    lines.append(
        "禁止写项目总结/复盘；禁止空泛描述；每条论断必须引用上面表格或分段结果中的具体数值或区间。"
    )

    return "\n".join(lines)


def build_mechanism_evidence_json(report: Dict) -> str:
    evidence = build_mechanism_evidence(report)
    return json.dumps(evidence, ensure_ascii=False, indent=2)


def _build_stub_report(evidence: Dict) -> str:
    segs = evidence.get("segments", [])
    diag = evidence.get("diagnostics", {})
    lines = []
    lines.append("# 机理分析报告（模板，需人工/大模型补全）")
    lines.append("\n## Data recap")
    lines.append(f"- 温度点数: {len(evidence.get('points', []))}")
    lines.append(f"- 分段数: {len(segs)}")
    lines.append("\n## Segment summary")
    for i, s in enumerate(segs, 1):
        tr = s.get("T_range_C") or ("?", "?")
        lines.append(
            f"- Seg{i}: T={tr[0]}~{tr[1]}°C, Ea={s.get('Ea_kJ_mol')} kJ/mol, N={s.get('N_points')}, r2={s.get('fit_r2')}"
        )
    lines.append("\n## Anomalies")
    lines.append(json.dumps(diag, ensure_ascii=False, indent=2))
    lines.append("\n## Hypotheses (fill)")
    lines.append("- [ ] 假设1: 现象 -> 可能原因 -> 验证方案")
    lines.append("- [ ] 假设2: ...")
    lines.append("- [ ] 假设3: ...")
    lines.append("\n## Next experiments")
    lines.append("- [ ] 复测/扩频/控湿/控压/界面处理/原位表征 等")
    lines.append("\n## Risks & confounders")
    lines.append("- [ ] 数据量/温区/噪声/电极界面/含水/相变 等")
    return "\n".join(lines)


def write_mechanism_artifacts(
    report_json_path: str,
    out_dir: str,
    *,
    write_prompt: bool,
    write_evidence: bool,
    write_stub_report: bool,
) -> Dict:
    report = _load_report(report_json_path)
    os.makedirs(out_dir, exist_ok=True)

    outputs = {}

    if write_prompt:
        prompt_text = build_mechanism_prompt(report)
        prompt_path = os.path.join(out_dir, "mechanism_prompt.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)
        outputs["prompt"] = prompt_path

    if write_evidence:
        evidence = build_mechanism_evidence(report)
        evidence_path = os.path.join(out_dir, "mechanism_evidence.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence, f, ensure_ascii=False, indent=2)
        outputs["evidence"] = evidence_path

    if write_stub_report:
        evidence = evidence if "evidence" in outputs else build_mechanism_evidence(report)
        stub = _build_stub_report(evidence)
        stub_path = os.path.join(out_dir, "mechanism_report.md")
        with open(stub_path, "w", encoding="utf-8") as f:
            f.write(stub)
        outputs["stub_report"] = stub_path

    return outputs


def _main():
    parser = argparse.ArgumentParser(description="Mechanism Report Input Builder")
    parser.add_argument("--report", type=str, required=True, help="report.json 路径")
    parser.add_argument("--out-dir", type=str, default="experiment_data", help="输出目录")
    parser.add_argument("--write-prompt", action="store_true", help="生成 mechanism_prompt.txt")
    parser.add_argument("--write-evidence", action="store_true", help="生成 mechanism_evidence.json")
    parser.add_argument("--write-report", action="store_true", help="生成 mechanism_report.md 模板")
    args = parser.parse_args()

    outputs = write_mechanism_artifacts(
        args.report,
        args.out_dir,
        write_prompt=args.write_prompt,
        write_evidence=args.write_evidence,
        write_stub_report=args.write_report,
    )
    for k, v in outputs.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    _main()
