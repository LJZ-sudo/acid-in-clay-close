# -*- coding: utf-8 -*-
"""Rb-ACT R4 **激活模式**（ESAS-OS 2.0 / §10.4 五级门的 R4 生产半）。

`prereg.py` 只做 R4 的**预注册契约 + 审计-only 信号**(`rb_r4_active` 恒 False,绝不改数值链)。
本模块补上真正的**激活路径**:当且仅当**三条件同时满足**才让 Rb-ACT 后验均值旁产
**σ_v2 + delta**(喂 BO 的噪声感知方差 train_Yvar_v2),否则恒回退 legacy:

  ① `rb_r4_activate=True`  ——运行显式请求激活(默认 False);
  ② 预注册审计 `gates_pass=True` ——冻结规则已在真数据上达标;
  ③ **人审签核 token** 存在 ——人把关(把"是否替换 legacy"的最终决定权交给人)。

**铁律(*_v2 + delta 纪律)**:
  * `legacy_overwritten` 恒 0 ——只读 legacy_rb / legacy σ,**从不回写**;σ_v2 是并行新字段;
  * 每点产 `delta_log10_sigma`(legacy vs v2)+ 翻转标记;
  * "BO 不劣化"守卫:legacy↔v2 的 σ 排序 Spearman ≥ 0.99 且中位 |Δlog10σ| ≤ 契约门,
    否则 `bo_not_degraded=False`(激活产物仍出,但明确告警不可采纳)。

诚实边界:单批激活(本模块)验证"接得上、不劣化、不覆盖 legacy";**跨批多片**双跑互证 +
你最终签核仍属 G-5。此模块不做无人值守的自动生产替换。
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional

R4_ACTIVATION_VERSION = "1.0"
DEFAULT_FLIP_DEX = 0.30          # 与 prereg.UNEXPLAINED_FLIP_DEX 同源(方法分歧弃权线)
DEFAULT_FLOOR_DEX = 0.02         # 与 rbact_noise_bridge 同源(防 0 方差)
DEFAULT_MAX_MEDIAN_DELTA_DEX = 0.10   # 与 prereg 验收门 max_median_abs_delta_dex 同源


def sigma_from_rb(rb_ohm: Optional[float], thickness_cm: float, area_cm2: float) -> Optional[float]:
    """几何映射 σ = thickness / (Rb · area)(S/cm);无效输入 → None。"""
    try:
        if rb_ohm and rb_ohm > 0 and area_cm2 > 0 and thickness_cm > 0:
            return float(thickness_cm) / (float(rb_ohm) * float(area_cm2))
    except (TypeError, ValueError):
        return None
    return None


def _spearman(a: List[float], b: List[float]) -> Optional[float]:
    """Spearman 秩相关(无 scipy 依赖)。样本 <3 → None。"""
    n = len(a)
    if n < 3 or n != len(b):
        return None

    def _ranks(x: List[float]) -> List[float]:
        order = sorted(range(n), key=lambda i: x[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and x[order[j + 1]] == x[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    ra, rb = _ranks(a), _ranks(b)
    ma = sum(ra) / n
    mb = sum(rb) / n
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    va = math.sqrt(sum((ra[i] - ma) ** 2 for i in range(n)))
    vb = math.sqrt(sum((rb[i] - mb) ** 2 for i in range(n)))
    if va == 0 or vb == 0:
        return None
    return cov / (va * vb)


def _signoff_id(human_signoff: Optional[str]) -> Optional[str]:
    if not human_signoff or not isinstance(human_signoff, str) or len(human_signoff.strip()) < 6:
        return None
    return hashlib.sha256(human_signoff.strip().encode("utf-8")).hexdigest()[:12]


def build_activation(
    results: List[Any],
    *,
    contract: Dict[str, Any],
    audit: Dict[str, Any],
    rb_r4_activate: bool,
    human_signoff: Optional[str],
    thickness_cm: float = 0.1,
    area_cm2: float = 1.96,
    floor_dex: float = DEFAULT_FLOOR_DEX,
    flip_dex: float = DEFAULT_FLIP_DEX,
) -> Dict[str, Any]:
    """据三条件门决定是否激活 R4;产 σ_v2 + 逐点 delta + "BO 不劣化"守卫。

    results: RbActResult 列表(需含 legacy_rb_ohm + posterior.rb_ohm + posterior.sigma_log10_total)。
    """
    gates_pass = bool(audit.get("gates_pass"))
    signoff_id = _signoff_id(human_signoff)
    reasons: List[str] = []
    if not rb_r4_activate:
        reasons.append("rb_r4_activate=False")
    if not gates_pass:
        reasons.append("prereg_gates_not_passed")
    if signoff_id is None:
        reasons.append("human_signoff_missing_or_too_short")
    activated = bool(rb_r4_activate and gates_pass and signoff_id is not None)

    # 激活前快照 legacy_rb(用于事后核验"legacy 永不覆盖")。
    legacy_snapshot = [getattr(r, "legacy_rb_ohm", None) for r in results]

    per_point: List[Dict[str, Any]] = []
    sig_legacy_list: List[float] = []
    sig_v2_list: List[float] = []
    abs_deltas: List[float] = []
    u_dex_list: List[float] = []
    n_flips = 0
    for r in results:
        legacy_rb = getattr(r, "legacy_rb_ohm", None)
        post = getattr(r, "posterior", None)
        rbact_rb = getattr(post, "rb_ohm", None) if post is not None else None
        u_dex = getattr(post, "sigma_log10_total", None) if post is not None else None
        sig_legacy = sigma_from_rb(legacy_rb, thickness_cm, area_cm2)
        sig_v2_raw = sigma_from_rb(rbact_rb, thickness_cm, area_cm2)
        dlog = None
        if sig_legacy and sig_v2_raw and sig_legacy > 0 and sig_v2_raw > 0:
            dlog = math.log10(sig_v2_raw) - math.log10(sig_legacy)
            abs_deltas.append(abs(dlog))
            sig_legacy_list.append(sig_legacy)
            sig_v2_list.append(sig_v2_raw)
            if abs(dlog) > flip_dex:
                n_flips += 1
        if isinstance(u_dex, (int, float)):
            u_dex_list.append(float(u_dex))
        per_point.append({
            "temperature_K": getattr(r, "temperature_K", None),
            "decision": getattr(r, "decision", None),
            "legacy_rb_ohm": legacy_rb,
            "rb_act_rb_ohm": rbact_rb,
            "sigma_legacy_S_cm": sig_legacy,
            # σ_v2 只在激活时对外给出(未激活恒 None → 数值链完全走 legacy)。
            "sigma_v2_S_cm": (sig_v2_raw if activated else None),
            "delta_log10_sigma": (dlog if activated else None),
            "u_total_dex": u_dex,
        })

    import statistics as _st
    median_abs = float(_st.median(abs_deltas)) if abs_deltas else 0.0
    spearman = _spearman(sig_legacy_list, sig_v2_list)
    max_median_gate = float(
        (contract.get("acceptance_gates") or {}).get(
            "max_median_abs_delta_dex", DEFAULT_MAX_MEDIAN_DELTA_DEX))
    bo_not_degraded = bool(
        activated
        and (spearman is not None and spearman >= 0.99)
        and (median_abs <= max_median_gate))

    # legacy 永不覆盖:核验输入 legacy_rb 前后一致(本模块只读)。
    legacy_after = [getattr(r, "legacy_rb_ohm", None) for r in results]
    legacy_overwritten = sum(1 for a, b in zip(legacy_snapshot, legacy_after) if a != b)

    # 激活时才产 train_Yvar_v2(否则 None → BO 仍用 legacy/R3 通道)。
    train_yvar_v2: Optional[List[float]] = None
    if activated and u_dex_list:
        train_yvar_v2 = [max(u, floor_dex) ** 2 for u in u_dex_list]

    return {
        "activation_version": R4_ACTIVATION_VERSION,
        "rb_r4_active": activated,
        "reasons": reasons or ["activated"],
        "contract_hash": contract.get("contract_hash"),
        "human_signoff_id": signoff_id,
        "gates_pass": gates_pass,
        "legacy_overwritten": legacy_overwritten,     # 恒 0(不变量)
        "n_points": len(results),
        "n_paired": len(abs_deltas),
        "n_flips": n_flips,
        "median_abs_delta_log10_sigma": round(median_abs, 4),
        "spearman_legacy_vs_v2": (round(spearman, 4) if spearman is not None else None),
        "max_median_abs_delta_dex_gate": max_median_gate,
        "bo_not_degraded": bo_not_degraded,
        "train_Yvar_v2": train_yvar_v2,
        "per_point": per_point,
        "note": ("R4 激活:σ_v2 由 Rb-ACT 后验均值旁产,legacy σ 只读并存;"
                 "跨批多片互证 + 最终签核仍属 G-5。"),
    }
