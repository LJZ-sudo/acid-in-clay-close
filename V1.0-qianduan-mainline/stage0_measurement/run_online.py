#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在线实验启动程序

职责：
1. 解析命令行参数
2. 组装依赖（TemperatureDriver, ChiExecutor, StateController）
3. 启动 OnlineExperimentWorkflow

用法：
    python run_online.py --material LLZO --port COM3 --T_start 25 --T_end -120
    python run_online.py --resume   # 从 online_experiment_state.json 断点续测
    
版本：2.1.0 (几何/σ 阈值/断点续测)
"""

import argparse
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from controllers import (
    OnlineExperimentWorkflow,
    StateController,
    ExperimentConfig,
    CoolingConfig,
    ChiConfig,
)
from modules.hardware import TemperatureDriver
from modules.automation import ChiExecutor
from modules.io_utils.run_manifest import write_run_manifest, sha256_file
import config


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="在线实验控制程序",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # 基本参数
    parser.add_argument(
        "--material",
        type=str,
        default="Sample",
        help="材料名称"
    )
    
    # 硬件参数
    parser.add_argument(
        "--port",
        type=str,
        default=config.DEFAULT_SERIAL_PORT,
        help="串口端口"
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=config.DEFAULT_BAUDRATE,
        help="波特率"
    )
    
    # 温度参数
    parser.add_argument(
        "--T_start",
        type=float,
        default=config.DEFAULT_COOLING_T_START,
        help="起始温度 (°C)"
    )
    parser.add_argument(
        "--T_end",
        type=float,
        default=config.DEFAULT_COOLING_T_END,
        help="结束温度 (°C)"
    )
    parser.add_argument(
        "--coarse_step",
        type=float,
        default=config.DEFAULT_COARSE_STEP,
        help="粗扫步长 (°C)"
    )
    parser.add_argument(
        "--fine_step",
        type=float,
        default=config.DEFAULT_FINE_STEP,
        help="细扫步长 (°C)"
    )
    parser.add_argument(
        "--eps",
        type=float,
        default=config.DEFAULT_TEMP_EPS,
        help="温度容差 (°C)"
    )
    
    # CHI 参数
    parser.add_argument(
        "--highf",
        type=str,
        default=config.DEFAULT_CHI_HIGHF,
        help="高频 (Hz)"
    )
    parser.add_argument(
        "--lowf",
        type=str,
        default=config.DEFAULT_CHI_LOWF,
        help="低频 (Hz)"
    )
    parser.add_argument(
        "--initV",
        type=str,
        default=config.DEFAULT_CHI_INITV,
        help="初始电位 (V)"
    )
    parser.add_argument(
        "--chi_data_dir",
        type=str,
        default=config.DEFAULT_CHI_DATA_DIR,
        help="CHI 数据保存目录"
    )
    parser.add_argument(
        "--chi_template_dir",
        type=str,
        default=config.DEFAULT_CHI_TEMPLATE_DIR,
        help="CHI 模板目录"
    )
    
    # 样品参数
    parser.add_argument(
        "--thickness",
        type=float,
        default=config.DEFAULT_THICKNESS_CM,
        help="样品厚度 (cm)"
    )
    parser.add_argument(
        "--area",
        type=float,
        default=config.DEFAULT_AREA_CM2,
        help="样品面积 (cm²)"
    )
    parser.add_argument(
        "--min_cond",
        type=float,
        default=config.DEFAULT_MIN_CONDUCTIVITY_THRESHOLD,
        help="电导率硬熔断阈值 (S/cm)，低于则自动停止"
    )
    
    # 功能开关
    parser.add_argument(
        "--disable_phase_detection",
        action="store_true",
        help="禁用相变检测"
    )
    parser.add_argument(
        "--disable_auto_stop",
        action="store_true",
        help="禁用自动停止"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从默认状态文件断点续测（需存在 online_experiment_state.json）"
    )

    # M5-A / SciTX 三重提交 Harness（默认关，开启则只记录不影响真实测量）
    parser.add_argument(
        "--shadow_harness",
        action="store_true",
        help="[兼容别名] 等价于 --harness_mode shadow（只记录、不夺仪器控制权、fail-safe）"
    )
    parser.add_argument(
        "--harness_mode",
        type=str,
        choices=["off", "shadow", "canary", "enforce"],
        default=None,
        help=("Harness 模式。P13-D:canary/enforce **不再降级**,其真实语义 = 仅作用于"
              "测量提交路径(被拒点挡出 BO,由 mode 感知 commit gate 执行);温控/CHI 物理命令"
              "永不门控(安全)。三重提交 harness 在 shadow/canary/enforce 下均记录;off 不记录。")
    )
    parser.add_argument(
        "--shadow_harness_dir",
        type=str,
        default=None,
        help="shadow 记录输出目录（默认 <chi_data_dir>/shadow_harness）"
    )

    return parser.parse_args()


def create_experiment_config(args, state_path: str):
    """创建实验配置"""
    cooling_config = CoolingConfig(
        T_start=args.T_start,
        T_end=args.T_end,
        coarse_step=args.coarse_step,
        fine_step=args.fine_step,
        eps=args.eps,
        stability_duration=config.DEFAULT_STABILITY_DURATION,
        stability_check_interval=config.DEFAULT_STABILITY_CHECK_INTERVAL,
        stability_max_retry=config.DEFAULT_STABILITY_MAX_RETRY,
        measurement_max_retry=config.DEFAULT_MEASUREMENT_MAX_RETRY,
    )
    
    chi_config = ChiConfig(
        material=args.material,
        highf=args.highf,
        lowf=args.lowf,
        initV=args.initV,
        your_position=args.chi_data_dir,
        template_dir=args.chi_template_dir,
        thickness_cm=args.thickness,
        area_cm2=args.area,
    )
    
    experiment_config = ExperimentConfig(
        cooling=cooling_config,
        chi=chi_config,
        enable_phase_detection=not args.disable_phase_detection,
        enable_auto_stop=not args.disable_auto_stop,
        enable_fine_scan=True,
        thickness_cm=args.thickness,
        area_cm2=args.area,
        min_conductivity_threshold=args.min_cond,
        state_persistence_path=state_path,
    )
    
    return experiment_config


def create_eis_analyzer(shadow_recorder=None):
    """创建 EIS 分析器。

    shadow_recorder 非空时,在真实分析返回后**旁路**喂给三重提交 Harness(M5-A)记录,
    完全 fail-safe:不改变返回值、不向实时回路抛错。
    """
    from modules.analysis import eis_pipeline
    
    def analyzer(frequencies, z_real, z_imag, temperature_K, thickness_cm, area_cm2):
        # 注意：eis_pipeline.analyze_eis_point 使用 temperature_C 参数
        temperature_C = temperature_K - 273.15
        result = eis_pipeline.analyze_eis_point(
            frequencies=frequencies,
            z_real=z_real,
            z_imag=z_imag,
            temperature_C=temperature_C,
            thickness_cm=thickness_cm,
            area_cm2=area_cm2,
        )
        # —— M5-A shadow 旁路（只记录，永不影响真实流程）——
        if shadow_recorder is not None:
            try:
                shadow_recorder.record(
                    result, freq=frequencies, z_real=z_real, z_imag=z_imag,
                    temperature_K=temperature_K)
            except Exception:
                pass
        return result
    
    return analyzer


def _resolve_harness_mode(args) -> str:
    """归一 --harness_mode 与兼容别名 --shadow_harness。

    P13-D:**不再把 canary/enforce 硬降级为 shadow**。canary/enforce 在本脚本的
    真实语义 = **仅作用于测量提交路径**(被拒点是否挡出 BO,由 mode 感知的 commit gate 执行,
    见 `hardware_adapter._commit_gate_mode` + `commit_gate.filter_bundle_eis_points`);
    **绝不门控温控/CHI 物理命令**(安全)。run_online 自身无自主硬件命令路径,故此处只做:
    三重提交 harness 照常记录 + 打印真实作用域;命令路径 enforce 的真机灰度属 §13.B G-4。
    """
    mode = getattr(args, "harness_mode", None)
    if mode is None:
        mode = "shadow" if getattr(args, "shadow_harness", False) else "off"
    if mode in ("canary", "enforce"):
        print(f"   🔒 harness_mode={mode}:仅作用于**测量提交路径**(被拒点挡出 BO,"
              f"由 mode 感知 commit gate 执行);**温控/CHI 物理命令永不门控**(安全)。"
              f"三重提交 harness 照常记录;命令路径 enforce 真机灰度见 G-4。")
    return mode


def _maybe_build_shadow_recorder(args):
    """按 harness_mode 构造三重提交记录器;任何失败都返回 None(不影响主流程)。
    P13-D:shadow/canary/enforce 均记录(记录器本身只观测);off 不记录。"""
    if _resolve_harness_mode(args) not in ("shadow", "canary", "enforce"):
        return None
    try:
        # 把 stage1_optimization 加到 path,按 scientific_harness.* 顶层导入,
        # 避免触发 stage1_optimization/__init__.py(其内有 canonical_input/optimizers 等重依赖绝对导入,
        # 任一失败都会让 shadow 被 try/except 静默禁用)。
        stage1_dir = Path(__file__).resolve().parent.parent / "stage1_optimization"
        if str(stage1_dir) not in sys.path:
            sys.path.insert(0, str(stage1_dir))
        from scientific_harness.shadow import ShadowHarnessRecorder
        out_dir = args.shadow_harness_dir or str(Path(args.chi_data_dir) / "shadow_harness")
        rec = ShadowHarnessRecorder(out_dir=out_dir, sample_id=args.material)
        print(f"   🛰️ 三重提交 Harness shadow 已开启 → {out_dir}（只记录，不接管仪器）")
        return rec
    except Exception as e:
        print(f"   ⚠️ shadow Harness 初始化失败（不影响主流程）: {e}")
        return None


def create_phase_detector():
    """创建相变检测器。

    DEPRECATED / PLACEHOLDER (Tier1 note 2026-06-01):
        This factory currently returns a NO-OP detector that always reports
        ``{'phase_detected': False}``. It does NOT call the real Rb-growth /
        LLM phase-detection logic in ``modules.analysis.phase_detect``
        (``analyze_experiment_state``). The web online-closed-loop path
        (``backend_api`` / ``controllers/online_workflow.py``) is the wired,
        functional phase-detection entry point; this CLI factory is a leftover
        stub kept only so ``run_online.py`` stays runnable for bench bring-up.

        Behavior intentionally left unchanged in Tier1 (it is on a live-hardware
        path that is not exercised by tests and not part of any frozen result).
        Wiring this to ``analyze_experiment_state`` is deferred to a future
        upgrade; do NOT mistake the False return for "no phase transition".
    """
    def detector(recent_measurements):
        if len(recent_measurements) < 3:
            return {'phase_detected': False}
        # NOTE: placeholder — always reports no phase; see docstring above.
        return {
            'phase_detected': False,
            'temperature_range': None,
            'scores': {}
        }
    
    return detector


def main():
    """主函数"""
    experiment_config = None
    workflow = None
    result = None
    
    print("=" * 60)
    print("🚀 在线实验控制程序")
    print("=" * 60)
    
    # 1. 解析参数
    args = parse_arguments()
    
    root = Path(__file__).parent.resolve()
    state_path = str(root / config.ONLINE_EXPERIMENT_STATE_FILENAME)
    
    print(f"\n📋 实验配置:")
    print(f"   材料: {args.material}")
    print(f"   温度范围: {args.T_start}°C → {args.T_end}°C")
    print(f"   粗扫步长: {args.coarse_step}°C")
    print(f"   串口: {args.port} ({args.baudrate} baud)")
    print(f"   CHI 频率: {args.lowf} - {args.highf} Hz")
    print(f"   样品: 厚度 {args.thickness} cm, 面积 {args.area} cm²")
    print(f"   σ 硬熔断阈值: {args.min_cond} S/cm")
    print(f"   状态文件: {state_path}")
    
    # 2. 创建配置
    experiment_config = create_experiment_config(args, state_path)
    
    # 3. 初始化依赖
    print(f"\n🔧 初始化组件...")
    
    # 3.1 温度驱动器
    print(f"   - 温度驱动器 ({args.port})...")
    try:
        temp_driver = TemperatureDriver(
            port=args.port,
            baudrate=args.baudrate,
            temp_min=config.DEFAULT_TEMP_MIN,
            temp_max=config.DEFAULT_TEMP_MAX,
        )
        print(f"     ✅ 温度驱动器初始化成功")
    except Exception as e:
        print(f"     ❌ 温度驱动器初始化失败: {str(e)}")
        return 1
    
    # 3.2 CHI 执行器
    print(f"   - CHI 执行器...")
    try:
        chi_executor = ChiExecutor()
        print(f"     ✅ CHI 执行器初始化成功")
    except Exception as e:
        print(f"     ❌ CHI 执行器初始化失败: {str(e)}")
        return 1
    
    # 3.3 状态控制器
    print(f"   - 状态控制器...")
    state_controller = StateController()
    if args.resume:
        if state_controller.load_state(state_path):
            n = state_controller.get_measurement_count()
            print(f"     ✅ 已从断点恢复状态（已有 {n} 条测量记录）")
        else:
            print(f"     ⚠️ 未找到有效状态文件，将从头开始实验")
    else:
        print(f"     ✅ 状态控制器初始化成功")
    
    # 3.4 分析器（可选挂 M5-A shadow 旁路）
    print(f"   - EIS 分析器...")
    shadow_recorder = _maybe_build_shadow_recorder(args)
    eis_analyzer = create_eis_analyzer(shadow_recorder=shadow_recorder)
    print(f"     ✅ EIS 分析器创建成功")
    
    # 3.5 相变检测器（可选）
    phase_detector = None
    if experiment_config.enable_phase_detection:
        print(f"   - 相变检测器...")
        phase_detector = create_phase_detector()
        print(f"     ✅ 相变检测器创建成功")
    
    # 4. 创建工作流
    print(f"\n🎯 创建在线实验工作流...")
    workflow = OnlineExperimentWorkflow(
        temp_driver=temp_driver,
        chi_executor=chi_executor,
        state_controller=state_controller,
        config=experiment_config,
        eis_analyzer=eis_analyzer,
        phase_detector=phase_detector,
    )
    print(f"   ✅ 工作流创建成功")
    
    # 5. 运行实验
    print(f"\n" + "=" * 60)
    print(f"▶️ 开始实验")
    print(f"=" * 60)
    
    try:
        result = workflow.run_cooling_loop()
        
        # 6. 输出结果
        print(f"\n" + "=" * 60)
        print(f"✅ 实验完成")
        print(f"=" * 60)
        print(f"   测量次数: {result['measurement_count']}")
        print(f"   检测相变: {result['phase_count']} 个")
        
        if result.get('stop_reason'):
            print(f"   停止原因: {result['stop_reason']}")
        
        if result['success']:
            print(f"\n🎉 实验成功完成！")
            return 0
        else:
            print(f"\n⚠️ 实验完成但有异常")
            print(f"   错误: {result.get('error')}")
            return 1
    
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 用户中断实验")
        workflow.stop(reason="用户中断")
        return 130
    
    except Exception as e:
        print(f"\n\n❌ 实验异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        try:
            manifest_path = root / "online_run_manifest.json"
            write_run_manifest(manifest_path, {
                "mode": "online",
                "material": args.material,
                "serial_port": args.port,
                "baudrate": args.baudrate,
                "temperature_range_C": [args.T_start, args.T_end],
                "coarse_step_C": args.coarse_step,
                "fine_step_C": args.fine_step,
                "chi_data_dir": args.chi_data_dir,
                "chi_template_dir": args.chi_template_dir,
                "state_path": state_path,
                "state_sha256": sha256_file(state_path),
                "phase_detection_enabled": experiment_config.enable_phase_detection if experiment_config else None,
                "phase_prompt_sha256": (
                    __import__("modules.analysis.phase_detect", fromlist=["get_system_prompt_sha256"])
                    .get_system_prompt_sha256()
                    if experiment_config and experiment_config.enable_phase_detection
                    else None
                ),
                "result": result,
            })
            print(f"\n🧾 已写入运行清单: {manifest_path}")
        except Exception as e:
            print(f"\n⚠️ 写入运行清单失败: {e}")

        if (
            experiment_config is not None
            and experiment_config.state_persistence_path
            and workflow is not None
        ):
            try:
                workflow.persist_checkpoint()
                print(f"\n💾 已保存实验状态: {experiment_config.state_persistence_path}")
            except Exception as e:
                print(f"\n⚠️ 退出时保存状态失败: {e}")
        # 清理资源
        print(f"\n🧹 清理资源...")
        try:
            temp_driver.close()
            print(f"   ✅ 温度驱动器已关闭")
        except Exception as e:
            print(f"   ⚠️ 关闭温度驱动器失败: {str(e)}")


if __name__ == "__main__":
    sys.exit(main())
