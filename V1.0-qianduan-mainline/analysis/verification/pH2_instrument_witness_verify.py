# -*- coding: utf-8 -*-
"""pH2 验证(H2):在线仪器见证路径 + 协议级故障注入 —— 驱动真事务机器 + 真文件。

`measurement_txn.ReplayInstrument` 恒把 ack/state/file 判成"已完成",无法演示在线仪器失败。
H2 的 `OnlineInstrumentWitness` 见证全部来自**一次真实在线步**(真 EIS .txt 落盘文件的 sha256 +
温控稳定 + 仪器态),并支持协议/见证级故障注入(非物理破坏性)。

用一条**真实凹凸棒 EIS .txt** 作独立 RAW_FILE 见证,直接调**生产函数** `submit_measurement_online`:
  0. 干净在线步:C_P=confirmed、blind_retry=0、见证含独立 TEMP_TRACE、entered_bo=True(基线);
  1. ACK_LOSS   :ACK 丢失(看似超时)→ reconciled=True、blind_retry=0、文件在仍 confirmed、entered_bo 不变;
  2. INSTRUMENT_STUCK:仪器 RUNNING → 至多 possible → 不进 BO;
  3. FILE_MISSING:文件未写(IDLE)→ not_occurred → 拒;
  4. FILE_DELAY :文件延迟(RUNNING、查不到)→ unknown → 拒;
  5. SAMPLE_SWAP:在线条码错配 → unknown(SAMPLE_ID_MISMATCH)→ 拒;
  6. CALIBRATION_EXPIRED:校准过期 → 物理仍 confirmed 但计量 UNKNOWN → U5 拒(不进 BO);
  7. 全程 blind_retry=0(不变量①:核对前绝不重试)。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve()
NDA = (next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline").parent / "experiments")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
for p in (str(MAIN), str(MAIN / "stage1_optimization")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scientific_harness.instrument_witness import (  # noqa: E402
    submit_measurement_online, ProtocolFault, OnlineInstrumentWitness)
from scientific_harness.witness import witnesses_from_instrument, WitnessKind  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


REAL_EIS = (MAIN / "data" / "ao" / "2026.5.11"
            / "凹-R0.23-N1.03-2_T18_f0.1_1000000_V0.txt")

SAMPLE = "ATA-2026-5-11-R0.186-N1.029"

# 干净信号(达 PRIMARY,U5 可进 BO);对齐 admission.py 的 clean 示例。
CLEAN_SIGNALS = dict(
    qa_failed=False, kk_mu_median=0.05, kk_testable=True,
    rb_method_spread_dex=0.02, uncertainty_status="QUANTIFIED",
    geometry_valid=True, rb_method_success=True, ecm_fallback=False,
    n_series_points=37, method_routing_sensitivity_passed=True,
    synthetic_fpr_passed=True, model_comparison_ok=True, identifiable=False,
    independent_support=True, alternatives_present=True,
)


def _submit(fault=None, actual=18.0, setpoint=18.0):
    return submit_measurement_online(
        sample_id=SAMPLE, output_file=str(REAL_EIS),
        measurement_signals=CLEAN_SIGNALS, chi_success=True,
        chamber_actual_C=actual, setpoint_C=setpoint, settle_tol_C=1.5,
        protocol_fault=fault)


def main():
    print("=" * 74)
    print("pH2:在线仪器见证 + 协议级故障注入 —— 驱动 submit_measurement_online + 真 EIS 文件")
    print("=" * 74)
    check("前置:真实 EIS .txt 存在(独立 RAW_FILE 见证源)", REAL_EIS.exists(), str(REAL_EIS))
    if not REAL_EIS.exists():
        return 1

    # 见证列表:确认独立 TEMP_TRACE 真被采集
    inst = OnlineInstrumentWitness(sample_id=SAMPLE, output_file=str(REAL_EIS),
                                   chamber_actual_C=18.0, setpoint_C=18.0)
    ws = witnesses_from_instrument(inst, "cmd0", ack_received=True)
    kinds = {w.kind for w in ws if w.present}
    check("在线见证含独立 RAW_FILE + TEMP_TRACE(仅在线可得)",
          WitnessKind.RAW_FILE in kinds and WitnessKind.TEMP_TRACE in kinds,
          f"present={sorted(kinds)}")

    # 0. 干净在线步
    r0 = _submit()
    base_bo = r0.entered_bo
    check("0 干净在线步:C_P=confirmed 且 blind_retry=0",
          r0.physical_occurred == "confirmed" and r0.blind_retry_count == 0,
          f"c_p={r0.physical_occurred} bo={r0.entered_bo}")
    check("0 干净在线步:见证含 TEMP_TRACE(独立温控见证进入 C_P 推断)",
          any("TEMP_TRACE" in str(x) for x in r0.reasons), f"reasons={r0.reasons}")
    check("0 干净在线步:entered_bo=True(达 PRIMARY 基线)", base_bo is True,
          f"entered_bo={base_bo} reasons={r0.reasons}")

    # 1. ACK_LOSS
    r1 = _submit(ProtocolFault.ACK_LOSS)
    check("1 ACK_LOSS:reconciled=True 且 blind_retry=0(先核对、禁盲目重试)",
          r1.reconciled is True and r1.blind_retry_count == 0,
          f"reconciled={r1.reconciled} blind_retry={r1.blind_retry_count}")
    check("1 ACK_LOSS:文件在 → 仍 confirmed、entered_bo 不变(ACK 丢失本身不该拒)",
          r1.physical_occurred == "confirmed" and r1.entered_bo == base_bo,
          f"c_p={r1.physical_occurred} bo={r1.entered_bo}")

    # 2. INSTRUMENT_STUCK
    r2 = _submit(ProtocolFault.INSTRUMENT_STUCK)
    check("2 INSTRUMENT_STUCK:RUNNING → 至多 possible、不进 BO",
          r2.physical_occurred == "possible" and r2.entered_bo is False,
          f"c_p={r2.physical_occurred} bo={r2.entered_bo}")

    # 3. FILE_MISSING
    r3 = _submit(ProtocolFault.FILE_MISSING)
    check("3 FILE_MISSING:IDLE 无文件 → not_occurred、不进 BO",
          r3.physical_occurred == "not_occurred" and r3.entered_bo is False,
          f"c_p={r3.physical_occurred} bo={r3.entered_bo}")

    # 4. FILE_DELAY
    r4 = _submit(ProtocolFault.FILE_DELAY)
    check("4 FILE_DELAY:RUNNING 查不到文件 → unknown、不进 BO(不盲目当成功)",
          r4.physical_occurred == "unknown" and r4.entered_bo is False,
          f"c_p={r4.physical_occurred} bo={r4.entered_bo}")

    # 5. SAMPLE_SWAP
    r5 = _submit(ProtocolFault.SAMPLE_SWAP)
    check("5 SAMPLE_SWAP:在线条码错配 → unknown、不进 BO,含 SAMPLE_ID_MISMATCH",
          r5.physical_occurred == "unknown" and r5.entered_bo is False
          and any("SAMPLE_ID_MISMATCH" in str(x) for x in r5.reasons),
          f"c_p={r5.physical_occurred} bo={r5.entered_bo}")

    # 6. CALIBRATION_EXPIRED
    r6 = _submit(ProtocolFault.CALIBRATION_EXPIRED)
    bo_use6 = r6.use_admissions.get("U5", {})
    check("6 CALIBRATION_EXPIRED:物理仍 confirmed 但计量拒 → 不进 BO",
          r6.physical_occurred == "confirmed" and r6.entered_bo is False,
          f"c_p={r6.physical_occurred} bo={r6.entered_bo} U5={bo_use6.get('status')}")

    # 7. 全程 blind_retry=0
    all_zero = all(r.blind_retry_count == 0 for r in (r0, r1, r2, r3, r4, r5, r6))
    check("7 全程 blind_retry=0(不变量①:核对前绝不盲目重试)", all_zero)

    # 8. 驱动**适配器生产方法** _run_instrument_witness + _finalize_instrument_witness(loop 接线)
    from backend_api.services import hardware_adapter as HA  # noqa: E402
    a = HA.HardwareAdapter.__new__(HA.HardwareAdapter)
    a._enable_instrument_witness = True
    a._instrument_witness_rows = []
    a._protocol_faults = [{"type": "INSTRUMENT_STUCK", "at_step": 1},
                          {"type": "ACK_LOSS", "at_step": 2}]
    a._sample_id = SAMPLE
    a._thickness_cm = 0.088
    a._area_cm2 = 1.96
    a._run_id = None
    a._events = []
    a._emit_event = lambda etype, payload=None: a._events.append((etype, payload or {}))
    rb_ok = {"status": "OK", "rb_ohm": 1234.0, "rb_method": "semicircle",
             "raw": {"kk_result": {"mu_median": 0.05}}}
    for si in (0, 1, 2):
        a._run_instrument_witness(
            step_idx=si, T_C=18.0 - si, admission_signals=dict(rb_method_spread_dex=0.02,
                                                               uncertainty_status="QUANTIFIED"),
            output_file=str(REAL_EIS), chamber_actual_C=18.0 - si, setpoint_C=18.0 - si,
            rb_result=rb_ok)
    rows = {r["step_idx"]: r for r in a._instrument_witness_rows}
    check("8 适配器 _run_instrument_witness:干净点(step0)C_P=confirmed",
          rows.get(0, {}).get("c_p") == "confirmed",
          f"row0={rows.get(0)}")
    check("8 适配器:INSTRUMENT_STUCK@step1 → 不进 BO",
          rows.get(1, {}).get("entered_bo") is False and rows.get(1, {}).get("protocol_fault") == "INSTRUMENT_STUCK",
          f"row1={rows.get(1)}")
    check("8 适配器:ACK_LOSS@step2 → 仍 confirmed、blind_retry=0",
          rows.get(2, {}).get("c_p") == "confirmed" and rows.get(2, {}).get("blind_retry_count") == 0,
          f"row2={rows.get(2)}")
    # finalize 验收锚点
    a._finalize_instrument_witness()
    fin = next((p for t, p in a._events if t == "INSTRUMENT_WITNESS_SUMMARY"), None)
    check("9 适配器 _finalize_instrument_witness:故障全被正确处理、无盲目重试",
          fin is not None and fin.get("all_faults_handled") is True and fin.get("any_blind_retry") is False,
          f"summary={fin}")

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   (生产函数 submit_measurement_online + 真 EIS 文件)")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
