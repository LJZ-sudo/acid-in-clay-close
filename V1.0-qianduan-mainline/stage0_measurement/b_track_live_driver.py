# -*- coding: utf-8 -*-
"""全温区 live 驱动 —— 精简"直接单点"路径(§12,B 轨/ESAS-OS 2.0 真机收口)。

**为什么不用 run_online?** 2026-06-28 实测:run_online 的 run_cooling_loop 路径首点
未起新扫描(rescue 抓到旧谱→被新鲜度护栏拒收);而 hw2 的"直接调 _perform_single_measurement"
路径起扫描成功(16:08 新鲜点)。本脚本沿用后者:每个设定点 = 精确控温 → 稳定 → 直接单点测量,
不引入冷却循环的相位/状态机。

三道防线全程生效(均在 hardened ChiExecutor 内):
  1. 点 Run 前窗口守卫置前台(_focus_chi)→ 让"开始测量"真正落在 CHI、触发新扫描;
  2. save_as 脆 → 宏救援 tsave 救回内存谱;
  3. 新鲜度护栏 → 采集时间戳过旧的谱一律拒收(返回失败),绝不把旧谱当新点。

每点失败(多为 start 未起扫描→护栏拒收)自动重试 --retries 次。每测完一点立即写
进度 JSON(--progress),便于不接管 GUI 时远程监看。

本文件已从 research/ 收编进 stage0_measurement/（入口收敛,2026-07-05）,
定为唯一 CLI 全温区 live driver;run_online.py 的 run_cooling_loop 路径仍保留但
其首点起扫描 bug 未修复前不作为 live 入口。

用法(先小步验证 2–3 点,稳了再无人值守全温区):
  # 验证:从当前温起,最多 3 点(在 stage0_measurement/ 下运行)
  python b_track_live_driver.py --thickness 0.0564 --T_start 11 --T_end -80 \
      --coarse_step 5 --max_points 3 --chi_data_dir E:\\chi_data\\b_track_fulltemp
  # 全程:
  python b_track_live_driver.py --thickness 0.0564 --T_start 11 --T_end -80 \
      --coarse_step 5 --chi_data_dir E:\\chi_data\\b_track_fulltemp
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STAGE0 = Path(__file__).resolve().parent
MAIN = STAGE0.parent
REPO = MAIN.parent
sys.path.insert(0, str(STAGE0))

import config  # noqa: E402
from controllers import (OnlineExperimentWorkflow, StateController,  # noqa: E402
                         ExperimentConfig, CoolingConfig, ChiConfig)
from modules.hardware import TemperatureDriver  # noqa: E402
from modules.automation import ChiExecutor  # noqa: E402
from run_online import create_eis_analyzer  # noqa: E402

OUT = MAIN.parent / "experiments" / "output" / "b_track_real"


def build_shadow_recorder(out_dir: str, sample_id: str):
    sys.path.insert(0, str(MAIN / "stage1_optimization"))
    from scientific_harness.shadow import ShadowHarnessRecorder
    return ShadowHarnessRecorder(out_dir=out_dir, sample_id=sample_id)


def build_ladder(t_start: float, t_end: float, step: float):
    """降序温度阶梯 [t_start, t_start-step, ... >= t_end]，末尾确保含 t_end。"""
    ladder = []
    t = float(t_start)
    while t >= t_end - 1e-9:
        ladder.append(round(t, 2))
        t -= step
    if abs(ladder[-1] - t_end) > 1e-6:
        ladder.append(round(float(t_end), 2))
    return ladder


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM3")
    ap.add_argument("--material", default="ATP-R0.186-N1.029-live-fulltemp")
    ap.add_argument("--thickness", type=float, required=True)
    ap.add_argument("--area", type=float, default=1.96)
    ap.add_argument("--chi_data_dir", default=str(Path("E:/chi_data/b_track_fulltemp")))
    ap.add_argument("--T_start", type=float, default=11.0)
    ap.add_argument("--T_end", type=float, default=-80.0)
    ap.add_argument("--coarse_step", type=float, default=5.0)
    ap.add_argument("--max_points", type=int, default=0, help=">0 时只跑前 N 点(小步验证)")
    ap.add_argument("--retries", type=int, default=2, help="每点失败(护栏拒收等)重试次数")
    ap.add_argument("--gui_confidence", type=float, default=0.45)
    ap.add_argument("--highf", default=config.DEFAULT_CHI_HIGHF)
    ap.add_argument("--lowf", default=config.DEFAULT_CHI_LOWF)
    ap.add_argument("--initV", default=config.DEFAULT_CHI_INITV)
    ap.add_argument("--reheat_at_end", type=int, default=1, help="结束后回温到 18°C(安全)")
    ap.add_argument("--progress", default=str(OUT / "fulltemp_progress.json"))
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    Path(args.chi_data_dir).mkdir(parents=True, exist_ok=True)
    shadow_dir = str(OUT / "fulltemp_shadow")

    ladder = build_ladder(args.T_start, args.T_end, args.coarse_step)
    if args.max_points and args.max_points > 0:
        ladder = ladder[:args.max_points]

    print("=" * 60)
    print("全温区 live 驱动（直接单点路径，沿用 hw2 起扫描成功的方式）")
    print(f"温度阶梯({len(ladder)}点): {ladder}")
    print("=" * 60)

    drv = TemperatureDriver(port=args.port, baudrate=19200, temp_min=-120.0, temp_max=40.0)

    _cfg = ChiExecutor()._get_default_config()
    _cfg["confidence"] = args.gui_confidence
    chi = ChiExecutor(config=_cfg)
    state = StateController()
    cooling = CoolingConfig(T_start=args.T_start, T_end=args.T_end, coarse_step=args.coarse_step,
                            stability_duration=config.DEFAULT_STABILITY_DURATION,
                            stability_check_interval=config.DEFAULT_STABILITY_CHECK_INTERVAL,
                            stability_max_retry=config.DEFAULT_STABILITY_MAX_RETRY,
                            measurement_max_retry=1, enable_agent_decision=False)
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
    wf._current_scan_mode = 'coarse'

    points = []

    def flush():
        Path(args.progress).write_text(json.dumps({
            "task": "full-temp live driver (direct single-point path)",
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "material": args.material, "thickness_cm": args.thickness, "area_cm2": args.area,
            "ladder": ladder, "shadow_dir": shadow_dir, "chi_data_dir": args.chi_data_dir,
            "points": points,
            "n_done": sum(1 for p in points if p["success"]),
            "n_attempted": len(points),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        state.start_experiment(metadata={"material": args.material, "mode": "fulltemp_direct",
                                         "ladder": ladder})
        for idx, T in enumerate(ladder):
            print(f"\n{'='*60}\n[点 {idx+1}/{len(ladder)}] 目标 T={T}°C")
            entry = {"idx": idx, "target_C": T, "success": False, "attempts": 0,
                     "rb_ohm": None, "conductivity_S_per_cm": None, "raw_data_path": None,
                     "t_start": datetime.now(timezone.utc).astimezone().isoformat()}
            points.append(entry)
            flush()

            cooled = wf._precise_cool_to_target(T)
            if not cooled:
                print(f"[点 {idx+1}] 控温未达标，跳过该点")
                entry["note"] = "cool_failed"
                flush()
                continue

            for attempt in range(1, args.retries + 2):
                entry["attempts"] = attempt
                print(f"[点 {idx+1}] 测量尝试 {attempt}/{args.retries + 1} ...")
                ok = False
                try:
                    ok = wf._perform_single_measurement(T, step_type="coarse")
                except Exception as e:  # noqa: BLE001
                    print(f"[点 {idx+1}] 测量异常: {e!r}")
                if ok:
                    last = state.get_last_measurement()
                    entry["success"] = True
                    entry["rb_ohm"] = getattr(last, "rb_ohm", None) if last else None
                    entry["conductivity_S_per_cm"] = (
                        getattr(last, "conductivity_S_per_cm", None) if last else None)
                    entry["raw_data_path"] = (
                        getattr(last, "raw_data_path", None) if last else None)
                    print(f"[点 {idx+1}] ✅ 成功 Rb={entry['rb_ohm']} σ={entry['conductivity_S_per_cm']}")
                    break
                print(f"[点 {idx+1}] ✗ 失败(多为 start 未起扫描→护栏拒收)，{'重试' if attempt <= args.retries else '放弃该点'}")
                time.sleep(3)
            entry["t_end"] = datetime.now(timezone.utc).astimezone().isoformat()
            flush()
    except KeyboardInterrupt:
        print("\n[中断] 收到 Ctrl-C，安全退出")
    except Exception as e:  # noqa: BLE001
        print(f"\n[异常] {e!r}")
    finally:
        if args.reheat_at_end:
            try:
                print("[安全] 结束回温到 18°C ...")
                drv.set_temperature(18.0, is_cooling=False)
            except Exception as e:  # noqa: BLE001
                print(f"[安全] 回温设定失败(忽略): {e!r}")
        drv.close()

    flush()
    n_ok = sum(1 for p in points if p["success"])
    print(f"\n{'='*60}\n全温区驱动结束: {n_ok}/{len(points)} 点成功")
    print(f"进度: {args.progress}")
    print(f"shadow: {shadow_dir}")
    print(f"raw: {args.chi_data_dir}")
    print("后处理: python V1.0-qianduan-mainline/analysis/analysis_scripts/b_track_live_fulltemp.py (FT-1..FT-4, 仓库根目录下)")
    return 0 if n_ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
