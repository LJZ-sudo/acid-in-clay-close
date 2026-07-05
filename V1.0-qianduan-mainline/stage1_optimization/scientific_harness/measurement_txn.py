# -*- coding: utf-8 -*-
"""测量提交路径事务化（ESAS-OS 2.0 / §10.1，离线可测 helper）。

把一份 **Stage0 结果 bundle**(`result_bundle.Stage0ResultBundle` 或等价 dict)物化为
`measurement_signals` + 一个 `ReplayInstrument`(文件/历史见证)，驱动既有
`EvidenceTransaction.process()`，使**测量证据**也走:
    多见证 → C_P → C_M(用途 U1–U6) → C_E(主张) → 是否进 BO。

为什么是"离线 helper":真机在线见证(ACK/温控/样品条码)只有连到试验台才真实可得;
本模块用已落盘 bundle 的 `file_hashes`(sha256)作**独立 RAW_FILE 见证**,在无真机时也能
端到端验证事务语义。`run_online.py` 的在线 enforce 接入保留给 G1(见 §10.4),**不在
无真机时伪造在线见证**。

关键诚实设计:`rb_method_spread_dex`(方法间分歧)**不在 bundle 里**——它来自 **Rb-ACT**
(§10.1)。因此:
  - 不提供 Rb-ACT 信号 → Rb 可提取性保守判 WEAK → 不进 BO(U5 REJECT);
  - 提供 Rb-ACT "低分歧"信号 → 才可能 PRIMARY → 进 BO。
这正是"测量保真度(Rb-ACT)解锁治理准入(SciTX)"的闭环示范,而非换名。
"""
from __future__ import annotations

import uuid
from statistics import median
from typing import Any, Dict, List, Optional

from .transaction import EvidenceTransaction, ClaimRequest, TransactionResult
from .admission import IntendedUse
from .event_store import EventStore


# ---- bundle 归一化(支持 pydantic 模型或 dict) -------------------------------

def _as_dict(bundle: Any) -> Dict[str, Any]:
    if hasattr(bundle, "model_dump"):
        return bundle.model_dump()
    if isinstance(bundle, dict):
        return bundle
    raise TypeError("bundle 必须是 Stage0ResultBundle(pydantic) 或 dict")


def _valid_points(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for p in points:
        status = str(p.get("status") or "OK")
        flags = p.get("quality_flags") or []
        failed = ("legacy_failure" in flags) or status not in ("OK", "")
        if not failed:
            out.append(p)
    return out


def build_measurement_signals_from_bundle(
    bundle: Any,
    *,
    rb_act_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """把 Stage0 bundle 物化为 assess_use 可消费的 measurement_signals。

    rb_act_signals(可选):来自 `rb_act.analyze_spectrum(...).admission_signals`,提供
    `rb_method_spread_dex / rb_method_success / ecm_fallback / uncertainty_status`。
    缺省时这些保守留空(rb 方法分歧未评估 → WEAK,不进 BO)。
    """
    b = _as_dict(bundle)
    geom = b.get("geometry") or {}
    points = b.get("eis_points") or []
    valid = _valid_points(points)
    arr = b.get("arrhenius") or {}

    # 底层(M1-4)信号
    qa_failed = len(points) > 0 and len(valid) == 0
    kk_vals = [p.get("kk_residual") for p in valid if p.get("kk_residual") is not None]
    kk_mu_median = float(median(kk_vals)) if kk_vals else None
    kk_testable = len(kk_vals) > 0
    geometry_valid = bool((geom.get("area_cm2") or 0) > 0 and (geom.get("thickness_cm") or 0) > 0)
    rb_vals = [p for p in valid if p.get("rb_ohm") is not None]
    rb_method_success = len(rb_vals) > 0
    ecm_fallback = any(p.get("rb_method") == "equivalent_circuit" for p in rb_vals)
    n_series_points = len(rb_vals)

    # 断点是否与 Rb 方法切换温区重合(算法伪影风险) —— 用 bundle 真有的字段判
    t_break = arr.get("t_break_K")
    breakpoint_matches_method_switch = _breakpoint_coincides_method_switch(rb_vals, t_break)

    n_segments = int(arr.get("n_segments") or 0)

    signals: Dict[str, Any] = {
        "qa_failed": qa_failed,
        "kk_mu_median": kk_mu_median,
        "kk_testable": kk_testable,
        "uncertainty_status": "QUANTIFIED" if geometry_valid else "UNKNOWN",
        "geometry_valid": geometry_valid,
        "rb_method_success": rb_method_success,
        "ecm_fallback": ecm_fallback,
        "n_series_points": n_series_points,
        "breakpoint_matches_method_switch": breakpoint_matches_method_switch,
        # 下列高阶门缺 bundle 直接证据 → 保守留 False(对应用途降级/拒绝,绝不放行)
        "method_routing_sensitivity_passed": False,
        "synthetic_fpr_passed": False,
        "model_comparison_ok": n_segments >= 2,
        "identifiable": False,
        "independent_support": False,
        "alternatives_present": False,
    }

    # Rb-ACT 注入(§10.1):方法间分歧只能由 Rb-ACT 提供
    if rb_act_signals:
        for k in ("rb_method_spread_dex", "rb_method_success", "ecm_fallback", "uncertainty_status"):
            if k in rb_act_signals and rb_act_signals[k] is not None:
                signals[k] = rb_act_signals[k]
        # P13-E:Rb-ACT R4 预注册的**审计-only** 信号(留痕 R4 已预注册/门是否满足/翻转数),
        # 仅供事务审计,**绝不参与 assess_use 的用途裁决**(entered_bo / 数值链完全不受影响)。
        for k in ("rb_r4_preregistered", "rb_r4_active", "rb_r4_prereg_id",
                  "rb_r4_gates_pass", "rb_r4_unexplained_flips"):
            if k in rb_act_signals and rb_act_signals[k] is not None:
                signals[k] = rb_act_signals[k]
    return signals


def _breakpoint_coincides_method_switch(rb_points: List[Dict[str, Any]],
                                        t_break: Optional[float],
                                        window_K: float = 3.0) -> bool:
    """断点温度附近 Rb 方法是否发生切换(legacy 温区路由伪影风险)。"""
    if t_break is None or len(rb_points) < 2:
        return False
    pts = sorted([p for p in rb_points if p.get("T_K") is not None], key=lambda p: p["T_K"])
    below = [p.get("rb_method") for p in pts if p["T_K"] < t_break - 0.0]
    near_below = [p.get("rb_method") for p in pts if t_break - window_K <= p["T_K"] < t_break]
    near_above = [p.get("rb_method") for p in pts if t_break <= p["T_K"] <= t_break + window_K]
    if near_below and near_above:
        return set(near_below) != set(near_above)
    return False


class ReplayInstrument:
    """离线/历史回放仪器:用 bundle 的 file_hashes 作独立 RAW_FILE 见证。

    满足 EvidenceTransaction 需要的接口:dispatch / query_output_file /
    query_instrument_state / query_sample_id。语义=该测量已完成且原始文件在档。
    """

    def __init__(self, bundle: Any):
        b = _as_dict(bundle)
        self._sample_id = b.get("sample_id")
        self._file_hashes = b.get("file_hashes") or {}
        self._has_raw = len(self._file_hashes) > 0

    def dispatch(self, command_id: str):
        class _D:
            ack_received = True
            timed_out = False
        return _D()

    def query_output_file(self, command_id: str):
        # 有 file_hashes(sha256)→ 独立 RAW_FILE 见证存在
        return self._file_hashes if self._has_raw else None

    def query_instrument_state(self):
        return "DONE" if self._has_raw else "IDLE"

    def query_sample_id(self):
        return self._sample_id


def submit_measurement_offline(
    bundle: Any,
    *,
    expected_sample_id: Optional[str] = None,
    intended_uses: Optional[List[str]] = None,
    target_claims: Optional[List[ClaimRequest]] = None,
    rb_act_signals: Optional[Dict[str, Any]] = None,
    event_store: Optional[EventStore] = None,
    command_id: Optional[str] = None,
) -> TransactionResult:
    """从一份 Stage0 bundle 提交一次**离线测量事务**,返回 TransactionResult。

    expected_sample_id 缺省取 bundle.sample_id(匹配);传入不同值则触发样品错配 →
    C_P unknown → 全 REJECT(测量来源核对的安全演示)。
    """
    b = _as_dict(bundle)
    signals = build_measurement_signals_from_bundle(bundle, rb_act_signals=rb_act_signals)
    inst = ReplayInstrument(bundle)
    txn = EvidenceTransaction(event_store)
    return txn.process(
        command_id=command_id or f"replay-{uuid.uuid4().hex[:8]}",
        command="REPLAY_MEASUREMENT",
        instrument=inst,
        measurement_signals=signals,
        intended_uses=intended_uses or list(IntendedUse.ALL),
        target_claims=target_claims or [],
        expected_sample_id=expected_sample_id if expected_sample_id is not None else b.get("sample_id"),
    )
