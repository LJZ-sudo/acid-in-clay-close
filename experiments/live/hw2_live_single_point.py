# -*- coding: utf-8 -*-
"""HW-2 常温单点 live shadow EIS（§11.2-B,安全护栏 §11.1）。

**只测 1 个点、就在当前室温、绝不下发降温命令**(直接调用单点测量事务,
不走会逐步降温的 run_cooling_loop)。目的:产 genuine live `shadow_harness_log.jsonl`
+ 1 条 live 谱,作为 B 轨"真机 live shadow"硬证据。

前置(运行前务必满足):
  1. CHI 软件已打开并在前台(ChiExecutor 用屏幕模板匹配点击,需要能看到 CHI 窗口);
  2. 操作者 hands-off(脚本会接管鼠标/键盘约 3–4 分钟做一次 EIS,期间勿操作电脑);
  3. 在机样品为 R=0.186/N=1.029,传入其真实厚度 --thickness。

用法:
  python hw2_live_single_point.py --thickness 0.0654 --area 1.96 \
      --material ATP-R0.186-N1.029-live --chi_data_dir E:\\chi_data\\b_track_live

不降温:目标温=开测时读到的当前温(±0),_wait_for_stable 立即通过。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "experiments").parent
MAIN = REPO / "V1.0-qianduan-mainline"
STAGE0 = MAIN / "stage0_measurement"
sys.path.insert(0, str(STAGE0))

import config  # noqa: E402
from controllers import (OnlineExperimentWorkflow, StateController,  # noqa: E402
                         ExperimentConfig, CoolingConfig, ChiConfig)
from modules.hardware import TemperatureDriver  # noqa: E402
from modules.automation import ChiExecutor  # noqa: E402

# run_online 的 shadow + analyzer 构造复用
sys.path.insert(0, str(STAGE0))
from run_online import create_eis_analyzer  # noqa: E402

OUT = MAIN / "output" / "b_track_real"


def build_shadow_recorder(out_dir: str, sample_id: str):
    sys.path.insert(0, str(MAIN / "stage1_optimization"))
    from scientific_harness.shadow import ShadowHarnessRecorder
    return ShadowHarnessRecorder(out_dir=out_dir, sample_id=sample_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--material", default="ATP-R0.186-N1.029-live")
    ap.add_argument("--thickness", type=float, required=True, help="在机样品真实厚度(cm)")
    ap.add_argument("--area", type=float, default=1.96)
    ap.add_argument("--chi_data_dir", default=str(Path("E:/chi_data/b_track_live")))
    ap.add_argument("--highf", default=config.DEFAULT_CHI_HIGHF)
    ap.add_argument("--lowf", default=config.DEFAULT_CHI_LOWF)
    ap.add_argument("--initV", default=config.DEFAULT_CHI_INITV)
    ap.add_argument("--gui_confidence", type=float, default=0.45,
                    help="CHI 模板匹配阈值(默认 0.45;save_as 实测~0.476,需略低于它)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    Path(args.chi_data_dir).mkdir(parents=True, exist_ok=True)
    shadow_dir = str(OUT / "live_shadow")

    print("=" * 60)
    print("HW-2 常温单点 live shadow EIS（不降温）")
    print("=" * 60)

    # 1. 温度驱动 + 读当前温(只读)
    drv = TemperatureDriver(port=args.port, baudrate=19200, temp_min=-120.0, temp_max=40.0)
    t = drv.read_temperature()
    if not t.get("success"):
        print(f"[HW-2] 无法读取温度: {t.get('error')}; 退出")
        drv.close()
        return 1
    ambient = float(t["temperature"])
    print(f"[HW-2] 当前室温 = {ambient}°C → 目标温=室温(不降温)")

    # 2. 组件（给 ChiExecutor 传 config:把整体匹配阈值降到 gui_confidence,
    #    使 save_as(~0.476) 能过,而 open_CHI/start(>0.99) 仍远高于阈值;不改 legacy 代码）
    _cfg = ChiExecutor()._get_default_config()
    _cfg["confidence"] = args.gui_confidence
    chi = ChiExecutor(config=_cfg)
    print(f"[HW-2] CHI 模板匹配阈值 = {args.gui_confidence}")
    state = StateController()
    cooling = CoolingConfig(T_start=ambient, T_end=ambient, coarse_step=3.0,
                            stability_duration=config.DEFAULT_STABILITY_DURATION,
                            stability_check_interval=config.DEFAULT_STABILITY_CHECK_INTERVAL,
                            stability_max_retry=config.DEFAULT_STABILITY_MAX_RETRY,
                            measurement_max_retry=2, enable_agent_decision=False)
    chi_cfg = ChiConfig(material=args.material, highf=args.highf, lowf=args.lowf,
                        initV=args.initV, your_position=args.chi_data_dir,
                        template_dir=str(STAGE0 / "controllers" / "templates"),
                        thickness_cm=args.thickness, area_cm2=args.area)
    exp = ExperimentConfig(cooling=cooling, chi=chi_cfg, enable_phase_detection=False,
                           enable_auto_stop=False, enable_fine_scan=False,
                           thickness_cm=args.thickness, area_cm2=args.area,
                           state_persistence_path=None)

    rec = build_shadow_recorder(shadow_dir, sample_id=args.material)
    analyzer = create_eis_analyzer(shadow_recorder=rec)
    wf = OnlineExperimentWorkflow(temp_driver=drv, chi_executor=chi, state_controller=state,
                                  config=exp, eis_analyzer=analyzer, phase_detector=None)
    wf._is_running = True

    # 3. 单点测量(就地常温,不降温)
    ok = False
    try:
        state.start_experiment(metadata={"material": args.material, "mode": "hw2_single_point",
                                         "ambient_C": ambient})
        print("[HW-2] 触发单点 CHI 测量 + shadow 旁路记录（接管鼠标约 3–4 分钟，请勿操作电脑）...")
        ok = wf._perform_single_measurement(ambient, step_type="coarse")
    except Exception as e:
        print(f"[HW-2] 单点测量异常: {e!r}")
    finally:
        # 安全护栏 §11.1-1/5:全程不下发任何温度/降温设定,温控只读;仅关闭串口。
        drv.close()

    last = state.get_last_measurement()
    summary = {
        "task": "HW-2 ambient single-point live shadow EIS (no cooling)",
        "at": datetime.now(timezone.utc).astimezone().isoformat(),
        "ambient_C": ambient, "material": args.material,
        "thickness_cm": args.thickness, "area_cm2": args.area,
        "measurement_success": bool(ok),
        "raw_data_path": (getattr(last, "raw_data_path", None) if last else None),
        "rb_ohm": (getattr(last, "rb_ohm", None) if last else None),
        "conductivity_S_per_cm": (getattr(last, "conductivity_S_per_cm", None) if last else None),
        "shadow_dir": shadow_dir,
        "chi_data_dir": args.chi_data_dir,
    }
    (OUT / "hw2_live_single_point.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[HW-2] success={ok} raw={summary['raw_data_path']} "
          f"Rb={summary['rb_ohm']} sigma={summary['conductivity_S_per_cm']}")
    print(f"[HW-2] live shadow → {shadow_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
