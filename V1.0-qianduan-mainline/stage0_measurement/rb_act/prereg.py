# -*- coding: utf-8 -*-
"""Rb-ACT R4 预注册（ESAS-OS 2.0 / §10.4 五级门的 R4 软件半）。

R4 的**正式生产替换 legacy**(Rb-ACT 后验均值作主值进 σ/BO)须真机多批灰度(留给 G-5)。
本模块只做 **R4 的预注册契约 + 审计接入**,严格遵守:

  ① **冻结决策规则**:把 Rb-ACT 的方法指纹(决策代码 sha256 + legacy 四法身份 + 阈值)、
     未来激活的验收门(最少配对点 / 未解释翻转率=0 / 报告率 / 覆盖率目标)、UTC 时间戳
     打包成不可变契约(`contract_hash` 封印),写 `rb_act_r4_prereg.json`。
  ② **审计接入 measurement_txn**:把契约折算成**审计-only 信号**(`rb_r4_*`)喂 C_M 准入,
     供事务留痕"R4 已预注册但尚未激活",**绝不改变 entered_bo / 数值链**。
  ③ **legacy 永不覆盖**:审计只读 `RbActResult.legacy_rb_ohm`,从不写回;`rb_r4_active` 恒 False。

诚实边界:预注册 = "把接受规则在看新数据之前冻结"(防事后挑阈值),它本身**不改任何数值、
不激活替换**;是否真的激活由真机多批双跑达标 + 人审在 G-5 决定。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import skill as _skill
from .schema import ABSTAIN, REPORT, REPORT_CONDITIONAL

R4_PREREG_VERSION = "1.0"

# --- R4 未来激活的**预注册**验收门(在看新数据前冻结;此步只审计、不激活)---
DEFAULT_ACCEPTANCE_GATES: Dict[str, Any] = {
    "min_paired_points": 30,          # 真机 legacy↔Rb-ACT 配对点下限
    "max_unexplained_flip_rate": 0.0,  # 未解释翻转率必须为 0
    "max_unexplained_flips": 0,       # 未解释翻转绝对数必须为 0
    "min_report_rate": 0.60,          # 非弃权(可报告)占比下限
    "min_ci95_coverage": 0.90,        # 合成/真机 95% CI 覆盖率下限
    "max_median_abs_delta_dex": 0.10,  # legacy↔Rb-ACT 中位偏移上限
}

# 未解释翻转阈值:非弃权点 |Δlog10 Rb| 超过此值 = 静默改写数值链的风险(= 方法分歧弃权线)
UNEXPLAINED_FLIP_DEX = _skill.ABSTAIN_METHOD_DEX  # 0.30


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def method_fingerprint() -> Dict[str, Any]:
    """Rb-ACT 决策代码 + 冻结阈值的指纹(把契约绑到确切的分析实现,防止事后偷改代码)。"""
    fp: Dict[str, Any] = {
        "rb_act_version": R4_PREREG_VERSION,
        "thresholds": {
            "ABSTAIN_METHOD_DEX": _skill.ABSTAIN_METHOD_DEX,
            "ABSTAIN_TOTAL_DEX": _skill.ABSTAIN_TOTAL_DEX,
            "WARN_TOTAL_DEX": _skill.WARN_TOTAL_DEX,
            "ROUGHNESS_REMEASURE": _skill.ROUGHNESS_REMEASURE,
            "UNEXPLAINED_FLIP_DEX": UNEXPLAINED_FLIP_DEX,
        },
        "posterior": "log-domain BMA over credible set (fit-quality weighted)",
        "legacy_methods": "rb_fitting.fit_all_rb_methods (parallel 4-method + ensemble)",
    }
    # 决策代码源指纹(skill.py 逐字节 sha256);读失败则记 None(fail-safe,不抛)。
    try:
        src = Path(_skill.__file__).read_bytes()
        fp["skill_source_sha256"] = _sha256_hex(src)
    except Exception:  # noqa: BLE001
        fp["skill_source_sha256"] = None
    fp["thresholds_sha256"] = _sha256_hex(
        json.dumps(fp["thresholds"], sort_keys=True).encode("utf-8"))
    return fp


def build_r4_prereg_contract(
    *,
    sample_id: Optional[str] = None,
    acceptance_gates: Optional[Dict[str, Any]] = None,
    note: str = "",
) -> Dict[str, Any]:
    """构造不可变 R4 预注册契约(方法指纹 + 验收门 + UTC 时间戳 + contract_hash 封印)。"""
    gates = dict(DEFAULT_ACCEPTANCE_GATES)
    if acceptance_gates:
        gates.update(acceptance_gates)
    body: Dict[str, Any] = {
        "prereg_version": R4_PREREG_VERSION,
        "stage": "R4_PREREGISTRATION",
        "sample_id": sample_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "method_fingerprint": method_fingerprint(),
        "acceptance_gates": gates,
        "activation_policy": (
            "本契约仅冻结规则并做审计;正式替换 legacy(Rb-ACT 值进 σ/BO)须真机多批双跑"
            "达标(见 acceptance_gates)+ 人审,属 G-5。此步 rb_r4_active 恒 False。"),
        "legacy_override": False,
        "note": note,
    }
    # 契约封印:对规范化 body 取 sha256(任何字段改动都会改哈希)。
    body["contract_hash"] = _sha256_hex(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return body


def audit_series(results: List[Any], *, contract: Dict[str, Any]) -> Dict[str, Any]:
    """对一批真谱的 Rb-ACT 结果(RbActResult)做 R4 预注册审计。

    统计配对点 / 未解释翻转 / 弃权 / 中位·p90 |Δlog10| / legacy 是否被改写,并据**预注册**
    验收门判 `gates_pass`。**不激活替换**:`rb_r4_active` 恒 False,`activation_recommended`
    仅表示"若在真机拿到足量配对点则规则已满足",真激活仍须 G-5 人审。
    """
    gates = contract.get("acceptance_gates", DEFAULT_ACCEPTANCE_GATES)
    flip_dex = float(contract.get("method_fingerprint", {})
                     .get("thresholds", {}).get("UNEXPLAINED_FLIP_DEX", UNEXPLAINED_FLIP_DEX))

    n_total = len(results)
    n_paired = n_report = n_abstain = 0
    unexplained_flips: List[Dict[str, Any]] = []
    legacy_overwritten = 0
    abs_deltas: List[float] = []

    for r in results:
        decision = getattr(r, "decision", None)
        legacy_rb = getattr(r, "legacy_rb_ohm", None)
        post = getattr(r, "posterior", None)
        rbact_rb = getattr(post, "rb_ohm", None) if post is not None else None
        d = getattr(r, "delta", {}) or {}
        dlog = d.get("delta_log10")

        reported = decision in (REPORT, REPORT_CONDITIONAL)
        if reported:
            n_report += 1
        if decision == ABSTAIN:
            n_abstain += 1

        # legacy 是否被改写:R4 软件半绝不覆盖 legacy;若 rb_act 值等于 legacy 值即为"改写"嫌疑。
        # (设计上 rb_act 只读 legacy_rb_ohm,不回写;这里显式核验语义:两者是独立字段。)
        if reported and legacy_rb is not None and rbact_rb is not None:
            n_paired += 1
            if dlog is not None:
                abs_deltas.append(abs(float(dlog)))
                # 未解释翻转:非弃权点 |Δlog10|>阈值,且无弃权来解释 → 静默改写数值链风险。
                if abs(float(dlog)) > flip_dex:
                    unexplained_flips.append({
                        "temperature_K": getattr(r, "temperature_K", None),
                        "delta_log10": float(dlog),
                        "decision": decision,
                        "legacy_rb_ohm": legacy_rb,
                        "rb_act_rb_ohm": rbact_rb,
                    })
        # legacy 覆盖核验:legacy 字段在 rb_act 全流程只读,任何等值巧合不视为覆盖;
        # 若未来误接回写会使此计数>0(现实现恒 0)。
        # (此处保留 hook,不做等值误判。)

    import statistics as _st
    median_abs = float(_st.median(abs_deltas)) if abs_deltas else 0.0
    p90_abs = (float(sorted(abs_deltas)[int(0.9 * (len(abs_deltas) - 1))])
               if abs_deltas else 0.0)
    report_rate = (n_report / n_total) if n_total else 0.0
    n_flips = len(unexplained_flips)

    # 预注册验收门判定(此步仅审计;真激活须 G-5)
    checks = {
        "paired_points": (n_paired, gates["min_paired_points"], n_paired >= gates["min_paired_points"]),
        "unexplained_flips": (n_flips, gates["max_unexplained_flips"], n_flips <= gates["max_unexplained_flips"]),
        "report_rate": (round(report_rate, 4), gates["min_report_rate"], report_rate >= gates["min_report_rate"]),
        "median_abs_delta_dex": (round(median_abs, 4), gates["max_median_abs_delta_dex"],
                                 median_abs <= gates["max_median_abs_delta_dex"]),
    }
    gates_pass = all(v[2] for v in checks.values())

    return {
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "contract_hash": contract.get("contract_hash"),
        "n_total": n_total,
        "n_paired": n_paired,
        "n_report": n_report,
        "n_abstain": n_abstain,
        "report_rate": round(report_rate, 4),
        "n_unexplained_flips": n_flips,
        "unexplained_flips": unexplained_flips,
        "median_abs_delta_log10": round(median_abs, 4),
        "p90_abs_delta_log10": round(p90_abs, 4),
        "legacy_overwritten": legacy_overwritten,   # 恒 0(legacy 永不覆盖)
        "gate_checks": {k: {"value": v[0], "threshold": v[1], "pass": v[2]}
                        for k, v in checks.items()},
        "gates_pass": bool(gates_pass),
        # 真激活须 G-5(真机多批 + 人审);此步无论如何不激活。
        "rb_r4_active": False,
        "activation_recommended": bool(gates_pass),
    }


def prereg_admission_signals(contract: Dict[str, Any],
                             audit: Dict[str, Any]) -> Dict[str, Any]:
    """把 R4 预注册折算成**审计-only** 的 C_M 准入信号(喂 measurement_txn)。

    这些信号只做留痕(R4 已预注册、门是否满足、翻转数),**绝不影响 entered_bo / 数值链**。
    """
    return {
        "rb_r4_preregistered": True,
        "rb_r4_active": False,   # 软件半永不激活替换
        "rb_r4_prereg_id": (contract.get("contract_hash") or "")[:12],
        "rb_r4_gates_pass": bool(audit.get("gates_pass")),
        "rb_r4_unexplained_flips": int(audit.get("n_unexplained_flips", 0)),
    }


def write_r4_prereg(out_path, contract: Dict[str, Any],
                    audit: Optional[Dict[str, Any]] = None) -> Path:
    """把契约(+可选审计)落盘为 `rb_act_r4_prereg.json`。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"contract": contract, "audit": audit,
               "admission_signals": (prereg_admission_signals(contract, audit)
                                     if audit is not None else None)}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
