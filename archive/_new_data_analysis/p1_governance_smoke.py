# -*- coding: utf-8 -*-
"""Phase 1 纯软件冒烟:喂历史 17 点真机谱,验证治理旁路逐点产
SHADOW_VERDICT / RBACT_DECISION / TXN_ADMISSION 事件,且 fail-safe(无异常逃逸)。
不连接任何硬件:只实例化 HardwareAdapter,直接喂解析后的谱给 _do_rb_fitting + _run_point_governance。"""
from __future__ import annotations
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN))  # 让 `stage0_measurement.modules...` 顶层可导入(同后端)
sys.path.insert(0, str(MAIN / "stage0_measurement"))
sys.path.insert(0, str(MAIN / "backend_api"))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from services.hardware_adapter import HardwareAdapter, RUNS_DIR  # noqa: E402

CHI_DIR = Path(r"E:\chi_data\b_track_fulltemp")
THICKNESS_CM = 0.0564
AREA_CM2 = 1.96
_T_RE = re.compile(r"_T(-?\d+(?:[.p]\d+)?)_")


def temp_from_name(name: str):
    m = _T_RE.search(name)
    return float(m.group(1).replace("p", ".")) if m else None


def main() -> int:
    a = HardwareAdapter()
    a._enable_harness = True
    a._sample_id = "ATP-R0.186-N1.029-live-fulltemp"
    a._run_id = "smoke_p1_governance"
    a._thickness_cm = THICKNESS_CM
    a._area_cm2 = AREA_CM2
    (RUNS_DIR / a._run_id).mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in CHI_DIR.glob("*.txt") if temp_from_name(p.name) is not None)
    print(f"[smoke] {len(files)} 个温点谱 from {CHI_DIR}")
    n_fed = 0
    for i, fp in enumerate(files):
        T_C = temp_from_name(fp.name)
        parsed = parse_chi_file(str(fp))
        if not parsed.get("success"):
            print(f"  - skip parse-fail {fp.name}")
            continue
        freq, zr, zi = parsed["frequencies"], parsed["z_real"], parsed["z_imag"]
        rb_result = a._do_rb_fitting(freq, zr, zi, T_C)
        a._run_point_governance(
            step_idx=i, T_C=T_C, freq=freq, zr=zr, zi=zi,
            eis_result=(rb_result.get("raw") if isinstance(rb_result, dict) else None),
            rb_result=rb_result,
        )
        n_fed += 1

    types = Counter(e["type"] for e in a._events)
    print(f"\n[smoke] 喂入 {n_fed} 点;事件类型计数:")
    for t in ("HARNESS_SHADOW_STARTED", "SHADOW_VERDICT", "RBACT_DECISION",
              "TXN_ADMISSION", "HARNESS_GOVERNANCE_ERROR", "HARNESS_UNAVAILABLE"):
        print(f"    {t:28s} = {types.get(t, 0)}")

    # 抽样打印 3 个治理事件的载荷
    for t in ("SHADOW_VERDICT", "RBACT_DECISION", "TXN_ADMISSION"):
        ev = next((e for e in a._events if e["type"] == t), None)
        if ev:
            print(f"\n  sample {t}: {ev['payload']}")

    shadow_log = RUNS_DIR / a._run_id / "shadow_harness" / "shadow_harness_log.jsonl"
    print(f"\n[smoke] shadow log 存在={shadow_log.exists()} -> {shadow_log}")

    ok = (types.get("SHADOW_VERDICT", 0) > 0 and types.get("RBACT_DECISION", 0) > 0
          and types.get("TXN_ADMISSION", 0) > 0 and types.get("HARNESS_GOVERNANCE_ERROR", 0) == 0)
    print(f"\n[smoke] RESULT = {'PASS' if ok else 'CHECK'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
