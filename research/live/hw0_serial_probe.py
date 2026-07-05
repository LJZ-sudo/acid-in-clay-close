# -*- coding: utf-8 -*-
"""HW-0 只读串口探针（§11.2-B,安全护栏 §11.1-4）。

只做一件事:开 COM3 → 多次 read_temperature(只读、不下发任何 set_temperature/降温)→ close。
确认温控器在线且能读到合法室温。绝不写温度、绝不降温。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage0_measurement"))

from modules.hardware import TemperatureDriver  # noqa: E402

PORT = "COM3"
OUT = MAIN / "output" / "b_track_real"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"task": "HW-0 read-only serial probe", "port": PORT,
           "at": datetime.now(timezone.utc).astimezone().isoformat(),
           "wrote_any_command": False, "reads": []}
    drv = None
    try:
        drv = TemperatureDriver(port=PORT, baudrate=19200, temp_min=-120.0, temp_max=40.0)
        print(f"[HW-0] 串口 {PORT} 打开成功 (read-only)")
        for i in range(3):
            r = drv.read_temperature()  # 只读
            rec["reads"].append(r)
            print(f"  read {i+1}: success={r['success']} temp={r['temperature']} err={r.get('error')}")
            time.sleep(1.0)
        ok = any(r.get("success") for r in rec["reads"])
        temps = [r["temperature"] for r in rec["reads"] if r.get("success")]
        rec["controller_online"] = bool(ok)
        rec["ambient_temp_C"] = (temps[-1] if temps else None)
        print(f"[HW-0] controller_online={ok} ambient_temp_C={rec['ambient_temp_C']}")
    except Exception as e:
        rec["error"] = repr(e)
        rec["controller_online"] = False
        print(f"[HW-0] 探针异常: {e!r}")
    finally:
        if drv is not None:
            try:
                drv.close()
                print("[HW-0] 串口已关闭")
            except Exception:
                pass
    (OUT / "hw0_serial_probe.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
