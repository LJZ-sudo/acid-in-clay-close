# -*- coding: utf-8 -*-
"""HW-3 live 谱 Rb-ACT 双跑（§11.2-B）。

读取 HW-2 产出的 live 谱(raw_data_path,见 output/b_track_real/hw2_live_single_point.json),
跑 Rb-ACT analyze_spectrum vs legacy_rb_ohm,产 live delta + 决策。R1:仍采用 legacy 值。

诚实:单点 live;legacy 零改动;EIS-only C4。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "experiments").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage0_measurement"))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402
from rb_act import analyze_spectrum, ABSTAIN  # noqa: E402

OUT = MAIN / "output" / "b_track_real"
FLIP_DEX = 0.30


def main() -> int:
    hw2 = OUT / "hw2_live_single_point.json"
    if not hw2.exists():
        print("[HW-3] 未找到 hw2_live_single_point.json,请先运行 HW-2。")
        return 1
    meta = json.loads(hw2.read_text(encoding="utf-8"))
    raw = meta.get("raw_data_path")
    if not raw or not Path(raw).exists():
        print(f"[HW-3] live 谱文件不存在: {raw}")
        return 1

    parsed = parse_chi_file(raw)
    if not parsed.get("success"):
        print(f"[HW-3] 解析 live 谱失败: {raw}")
        return 1

    r = analyze_spectrum(parsed["frequencies"], parsed["z_real"], parsed["z_imag"],
                         thickness_cm=meta["thickness_cm"], area_cm2=meta["area_cm2"])
    legacy_rb = getattr(r, "legacy_rb_ohm", None)
    rbact_rb = getattr(r.posterior, "rb_ohm", None) if getattr(r, "posterior", None) else None
    delta = None
    if r.decision != ABSTAIN and legacy_rb and rbact_rb and legacy_rb > 0 and rbact_rb > 0:
        delta = abs(math.log10(rbact_rb) - math.log10(legacy_rb))

    out = {
        "task": "HW-3 live Rb-ACT double-run (R1; legacy adopted)",
        "at": datetime.now(timezone.utc).astimezone().isoformat(),
        "live_spectrum": raw,
        "decision": str(r.decision),
        "legacy_rb_ohm": legacy_rb,
        "rbact_rb_ohm": rbact_rb,
        "abs_dlog10_rb": delta,
        "flip_threshold_dex": FLIP_DEX,
        "unexplained_flip": bool(delta is not None and delta > FLIP_DEX),
        "admission_signals": dict(getattr(r, "admission_signals", {}) or {}),
        "note": "单点 live;R1 仍用 legacy 值;legacy rb_fitting 零改动;EIS-only C4。",
    }
    (OUT / "hw3_rb_act_live.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[HW-3] decision={out['decision']} legacy_rb={legacy_rb} rbact_rb={rbact_rb} "
          f"|Δlog10Rb|={delta} flip={out['unexplained_flip']}")
    print(f"[HW-3] 写出: {OUT/'hw3_rb_act_live.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
