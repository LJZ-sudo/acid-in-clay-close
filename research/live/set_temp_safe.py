# -*- coding: utf-8 -*-
"""把温控设回安全温度(默认 18°C),避免设备长期低温。读当前温→设目标→确认。"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

STAGE0 = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent / "V1.0-qianduan-mainline" / "stage0_measurement"
sys.path.insert(0, str(STAGE0))
from modules.hardware import TemperatureDriver  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--target", type=float, default=18.0)
    args = ap.parse_args()

    drv = TemperatureDriver(port=args.port, baudrate=19200, temp_min=-120.0, temp_max=40.0)
    try:
        t0 = drv.read_temperature()
        print(f"[set_temp] 当前温度 = {t0.get('temperature')}°C (success={t0.get('success')})")
        res = drv.set_temperature(args.target, is_cooling=False)
        print(f"[set_temp] 设定 {args.target}°C → success={res.get('success')} err={res.get('error')}")
        time.sleep(2)
        t1 = drv.read_temperature()
        print(f"[set_temp] 设定后回读 = {t1.get('temperature')}°C")
    finally:
        drv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
