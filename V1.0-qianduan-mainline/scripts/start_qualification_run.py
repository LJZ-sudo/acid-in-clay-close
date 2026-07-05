# -*- coding: utf-8 -*-
"""资格 run（Run Q）一键启动器 —— 冻结的验收启动脚本，不再手工拼 payload。

用途：对旧样品做一次完整全温区资格 run，在**一次 run 内**验收全部创新点 + 三个验收动作：
  - 九个默认开的创新点（逐点 agent / 记忆 / 事务门控 enforce / C3 / 认知证书+阻抗 /
    active_design canary / stage3 推理 / 证伪市场 / 仪器见证）—— 后端默认即真实执行；
  - H2 协议故障注入：ACK_LOSS@3、CALIBRATION_EXPIRED@6（见证层验收）；
  - G-2 治理故障注入：SAMPLE_MISMATCH@9（准入层验收，被 commit gate 剔出 BO）；
  - H3 canary：active_design 真实微调 setpoint（±2 step 邻域 / 阶梯包络 / 回温≤15K 硬护栏）；
  - H4 R4：--signoff 提供人审签核 token 时评估激活替换态（缺 token 恒回退 legacy）。

普通 run（含新 R/N 前瞻 run）**不要用本脚本**——直接驾驶舱启动即可（创新点已默认全开，
但不注入人造故障，保持数据干净）。

用法（后端须已启动并已 /connect 真机）：
  python V1.0-qianduan-mainline/scripts/start_qualification_run.py \
      --sample-id Q-20260706 --signoff "LJZ-20260706-R4-QUALIFICATION"
可选：--no-faults 跳过故障注入；--t-start/--t-end/--coarse/--fine 覆盖温区。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser(description="Start the qualification run (Run Q)")
    ap.add_argument("--sample-id", required=True)
    ap.add_argument("--signoff", default=None,
                    help="H4 R4 人审签核 token；不给则 R4 评估照跑但恒回退 legacy")
    ap.add_argument("--t-start", type=float, default=19.0)
    ap.add_argument("--t-end", type=float, default=-85.0)
    ap.add_argument("--coarse", type=float, default=5.0)
    ap.add_argument("--fine", type=float, default=1.0)
    ap.add_argument("--thickness-m", type=float, default=None)
    ap.add_argument("--area-m2", type=float, default=None)
    ap.add_argument("--material-note", default="qualification run (old material)")
    ap.add_argument("--no-faults", action="store_true", help="跳过 H2/G-2 故障注入")
    ap.add_argument("--no-stage1", action="store_true",
                    help="只跑 Stage0 后处理,不跑 Stage1 BO(验证段/部分温区 run 用,避免污染优化历史)")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    payload = {
        "sample_id": args.sample_id,
        "t_start": args.t_start, "t_end": args.t_end,
        "coarse_step": args.coarse, "fine_step": args.fine,
        "thickness_m": args.thickness_m, "area_m2": args.area_m2,
        "material_note": args.material_note,
        "auto_postprocess": True, "run_stage1_after_stage0": not args.no_stage1,
        # 创新点后端已默认全开;这里显式写出以便 payload 自身可审计。
        "enable_agent_decision": True,
        "enable_active_design": True, "active_design_mode": "canary", "canary_max_steps": 2,
        "enable_stage3_reasoning": True, "enable_epistemic": True,
        "enable_falsification_market": True, "enable_instrument_witness": True,
        "commit_gate_mode": "enforce",
        # H4:flag 默认已开;签核 token 由人提供(唯一人审门)。
        "rb_r4_activate": True, "rb_r4_signoff": args.signoff,
    }
    if not args.no_faults:
        payload["inject_fault"] = [
            {"type": "ACK_LOSS", "at_step": 3},             # H2 协议级:ACK 丢失(应 confirmed、不盲重试)
            {"type": "CALIBRATION_EXPIRED", "at_step": 6},  # H2 见证级:校准过期(应不进 BO)
            {"type": "SAMPLE_MISMATCH", "at_step": 9},      # G-2 治理级:样品不符(应被 commit gate 剔出)
        ]

    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/api/control/start",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        print("START FAILED", file=sys.stderr)
        return 1
    print(f"\nRun Q started: run_id={result.get('run_id')}")
    print("验收产物(收尾后查 experiments/runs/<run_id>/):")
    print("  instrument_witness_summary.json / fault_injection_summary.json /")
    print("  rb_act_r4_activation.json / c3_convergence_certificate.json /")
    print("  action_gate_summary.json / stage3_mechanism/ / 认知证书+市场结算 JSON")
    if not args.signoff:
        print("注意:未提供 --signoff,H4 评估照跑但替换态恒回退 legacy。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
