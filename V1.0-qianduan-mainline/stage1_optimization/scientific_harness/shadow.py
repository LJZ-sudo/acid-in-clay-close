# -*- coding: utf-8 -*-
"""三重提交 Harness — shadow 旁路记录器（M5-A 真机落地,非侵入）。

用于 G1 真机测量:对每个测完的温点,把 Stage0 已算结果旁路喂给 CommitController,
记录"现有系统判定 vs 三重提交判定"的差异。**只记录、不夺仪器控制权、绝不影响真实流程**
(全程 fail-safe:任何异常都被吞掉,不向实时回路抛错)。

挂钩点:run_online.py 的 `create_eis_analyzer()` 回调 —— 在真实分析返回后追加一次 shadow 记录。
覆盖范围(诚实):
  - C_M/C_E:由 Stage0 的 QA/KK/Rb(+ 可选 fit_all_rb_methods 方法间一致性)真实驱动;
  - C_P:analyzer 层已拿到谱 ⇒ 物理效应已观测(EFFECT_OBSERVED);超时/重建路径需更深接 dispatch 层
    (后续闭环再做),本 shadow 不覆盖。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .commit_controller import CommitController
from .commits import PhysicalCommit


class ShadowInstrument:
    """post-hoc 适配器:analyzer 层已有谱 → 物理效应已观测(无超时/重建路径)。"""

    def __init__(self, sample_id: str = "G1",
                 temp_equilibrated: bool = True, calibration_valid: bool = True):
        self.sample_id = sample_id
        self.temp_equilibrated = temp_equilibrated
        self.calibration_valid = calibration_valid

    def dispatch(self, command_id: str):
        from .fault_injection import DispatchResult
        return DispatchResult(ack_received=True, timed_out=False)

    def query_output_file(self, command_id: str) -> bool:
        return True

    def query_instrument_state(self) -> str:
        return "DONE"

    def query_sample_id(self) -> str:
        return self.sample_id


def _build_measurement(eis_result: Dict[str, Any],
                       rb_spread_dex: Optional[float]) -> Dict[str, Any]:
    """从 analyze_eis_point 结果构造证据准入输入。"""
    status = eis_result.get("status")
    quality = eis_result.get("quality_result") or {}
    details = quality.get("details") or {}
    qa_failed = bool(status == "REJECTED_BY_QA"
                     or (quality.get("grade") == "F" and details.get("fatal_check")))
    kk = eis_result.get("kk_result") or {}
    kk_mu_median = kk.get("mu_median")
    return {
        "qa_failed": qa_failed,
        "kk_mu_median": kk_mu_median,
        "rb_method_spread_dex": rb_spread_dex,
        "uncertainty_status": "QUANTIFIED" if rb_spread_dex is not None else "PARTIAL",
    }


def _live_admissible(eis_result: Dict[str, Any]) -> bool:
    """现有系统在 analyzer 层的"可用"判定(success 且 status==OK)。"""
    return bool(eis_result.get("success")) and eis_result.get("status") == "OK"


def _per_use_admission(measurement: Dict[str, Any]) -> Dict[str, str]:
    """WP1 按用途准入(U1–U6)逐点旁路记录(fail-safe;失败返回空)。

    单温点只含 qa/kk/rb/uncertainty 信号 → U1(存观察)/U2(估单点电导)有意义;
    U3–U6 需序列级证据,单点下保守判 REJECT(诚实,非伪通过)。
    """
    try:
        from .admission import assess_all_uses
        signals = {
            "qa_failed": measurement.get("qa_failed", False),
            "kk_mu_median": measurement.get("kk_mu_median"),
            "rb_method_spread_dex": measurement.get("rb_method_spread_dex"),
            "uncertainty_status": measurement.get("uncertainty_status", "PARTIAL"),
            "rb_method_success": measurement.get("rb_method_spread_dex") is not None,
            "geometry_valid": True,
        }
        return {u: a.status for u, a in assess_all_uses(signals).items()}
    except Exception:
        return {}


class ShadowHarnessRecorder:
    """G1 旁路记录器。fail-safe:任何异常都不影响真实测量。"""

    def __init__(self, out_dir: str | Path, sample_id: str = "G1",
                 compute_rb_spread: bool = True):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.out_dir / "shadow_harness_log.jsonl"
        self.summary_path = self.out_dir / "shadow_harness_summary.json"
        self.sample_id = sample_id
        self.compute_rb_spread = compute_rb_spread
        self.controller = CommitController()
        self._n = 0
        self._n_agree = 0
        self._n_blind_retry = 0
        self._n_invalid_into_bo = 0
        self._seq = 0

    def _rb_spread(self, freq, z_real, z_imag, temperature_K) -> Optional[float]:
        if not self.compute_rb_spread:
            return None
        try:
            from modules.analysis.algorithms.rb_fitting import fit_all_rb_methods
            r = fit_all_rb_methods(freq, z_real, z_imag, thickness_cm=1.0, area_cm2=1.0,
                                   temperature_K=temperature_K)
            return r.get("ensemble", {}).get("method_spread_dex")
        except Exception:
            return None

    def record(self, eis_result: Dict[str, Any], freq=None, z_real=None, z_imag=None,
               temperature_K: Optional[float] = None,
               temp_equilibrated: bool = True, calibration_valid: bool = True) -> None:
        """旁路记录一个温点(永不抛错)。"""
        try:
            self._seq += 1
            spread = self._rb_spread(freq, z_real, z_imag, temperature_K) \
                if (freq is not None) else None
            measurement = _build_measurement(eis_result, spread)
            inst = ShadowInstrument(self.sample_id, temp_equilibrated, calibration_valid)
            res = self.controller.process(f"g1_pt_{self._seq:04d}", inst, measurement)
            live_ok = _live_admissible(eis_result)

            self._n += 1
            agree = (res.entered_bo == live_ok)
            if agree:
                self._n_agree += 1
            self._n_blind_retry += res.blind_retry_count
            if res.entered_bo and not live_ok:
                # shadow 比 live 更宽松不应发生(shadow 更严)。记为异常关注。
                self._n_invalid_into_bo += 1

            entry = {
                "seq": self._seq,
                "at": datetime.now(timezone.utc).astimezone().isoformat(),
                "temperature_K": temperature_K,
                "temperature_C": (temperature_K - 273.15) if temperature_K else None,
                "physical_commit": res.physical_commit,
                "metrological_commit": res.metrological_commit,
                "epistemic_commit": res.epistemic_commit,
                "shadow_entered_bo": res.entered_bo,
                "live_admissible": live_ok,
                "agree": agree,
                "rb_method_spread_dex": spread,
                "per_use_admission": _per_use_admission(measurement),  # WP1 U1–U6 逐点
                "reasons": res.reasons,
            }
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._write_summary()
        except Exception:
            # 绝不影响真实测量
            return

    def _write_summary(self) -> None:
        try:
            summary = {
                "sample_id": self.sample_id,
                "n_points": self._n,
                "n_agree_live_vs_shadow": self._n_agree,
                "agreement_rate": (self._n_agree / self._n) if self._n else None,
                "blind_retry_count": self._n_blind_retry,            # 应 = 0
                "shadow_looser_than_live_count": self._n_invalid_into_bo,  # 应 = 0
                "note": "shadow=record-only; C_E 比 live 更严属正常(更保守)。",
            }
            self.summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            return
