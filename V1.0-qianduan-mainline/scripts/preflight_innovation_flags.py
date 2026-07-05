# -*- coding: utf-8 -*-
"""端到端验证：前端同款 payload → /api/control/start → 适配器运行时开关状态。

只在 simulate 模式跑，不碰任何真实硬件；start 后立即 stop。
"""
import sys
from pathlib import Path

MAIN = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline")
sys.path.insert(0, str(MAIN))

from fastapi.testclient import TestClient  # noqa: E402
from backend_api.main import fastapi_app  # noqa: E402
from backend_api.routers.control import StartExperimentRequest  # noqa: E402
from backend_api.services.hardware_adapter import get_hardware_adapter  # noqa: E402

# ---- 第 1 层：Pydantic 模型默认值（前端不发的字段将取这些值）----
req = StartExperimentRequest()
print("=== Layer 1: StartExperimentRequest defaults (frontend 不发送这些字段) ===")
model_flags = [
    "enable_agent_decision", "enable_active_design", "active_design_mode",
    "enable_stage3_reasoning", "enable_epistemic", "enable_falsification_market",
    "enable_instrument_witness", "commit_gate_mode", "canary_max_steps",
    "rb_r4_activate",
]
for f in model_flags:
    print(f"  {f} = {getattr(req, f)!r}")

# ---- 第 2 层：真实 API 调用链（前端 Control.jsx handleStart 的同款 payload 形状）----
client = TestClient(fastapi_app)
r = client.post("/api/control/connect", json={"port": "COM3", "simulate": True,
                                              "coarse_step": 5.0, "fine_step": 1.0,
                                              "t_start": 20.0, "t_end": 15.0})
assert r.json().get("ok"), f"connect failed: {r.text}"

frontend_payload = {
    # Control.jsx handleStart 实际发送的字段（无任何创新点开关）
    "sample_id": "FLAG-VERIFY-SMOKE",
    "t_start": 20.0, "t_end": 15.0,
    "coarse_step": 5.0, "fine_step": 1.0,
    "thickness_m": 0.001, "area_m2": 0.000196,
    "material_note": "flag verification smoke (simulate)",
    "auto_postprocess": False,          # 冒烟不触发后处理
    "run_stage1_after_stage0": False,
}
r = client.post("/api/control/start", json=frontend_payload)
assert r.json().get("ok"), f"start failed: {r.text}"
run_id = r.json()["run_id"]

hw = get_hardware_adapter()
print(f"\n=== Layer 2: 运行时适配器内部状态 (run_id={run_id}, simulate) ===")
runtime = {
    "逐点 LLM agent":        ("_enable_agent_decision", True),
    "R2-Memory live 注入":   ("_enable_memory", True),
    "C3 收敛证书+H1 证据":   ("_enable_c3", True),
    "提交门控(enforce)":     ("_commit_gate_mode", "enforce"),
    "commit gate 开":        ("_enable_commit_gate", True),
    "Epistemic 认知证书+阻抗": ("_enable_epistemic", True),
    "active_design 开":      ("_enable_active_design", True),
    "H3 canary 模式(默认执行)": ("_active_design_mode", "canary"),
    "H3 canary 邻域步数":    ("_canary_max_steps", 2),
    "Stage3 机理推理链":     ("_enable_stage3_reasoning", True),
    "LLM 证伪市场":          ("_enable_falsification_market", True),
    "H2 在线仪器见证":       ("_enable_instrument_witness", True),
    "H4 R4 评估链(flag 开)":  ("_rb_r4_activate", True),
    # 唯一的人审门:签核 token 必须由人提供,软件绝不自行替换数值链
    "H4 签核 token(须人给,应 None)": ("_rb_r4_signoff", None),
    "ActionGate 命令路径(应 shadow)": ("_harness_mode", "shadow"),
}
all_ok = True
for label, (attr, expected) in runtime.items():
    actual = getattr(hw, attr)
    ok = actual == expected
    all_ok &= ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:32s} {attr} = {actual!r} (期望 {expected!r})")

client.post("/api/control/stop")
client.post("/api/control/disconnect")

print(f"\n=== 结论: {'全部符合预期 — 创新点默认全开，治理门默认关' if all_ok else '存在不符合项！'} ===")
sys.exit(0 if all_ok else 1)
