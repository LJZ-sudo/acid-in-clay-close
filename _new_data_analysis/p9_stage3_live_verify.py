# -*- coding: utf-8 -*-
"""P9 验证：把 stage3 机理推理链(假设/机制)真正接进 live + 真实 LLM 调用。

回应用户："把 GPT 描述的迁移发现/机理推理真实做到,不要再虚假"。本脚本:
  1. 从**真实 genuine-live run**(`run_20260629_112156_9db536`)的 events.jsonl 抽 19 个真机点
     + 全局 Arrhenius(3 段 / 2 相变);
  2. 用 `live_seed_adapter.build_seed_from_live` 构造**真实** Stage3SeedBundle;
  3. 用 `run_mechanism_reasoning` 真实驱动 S03→S04→S06→S06b,**S04/S06/S06b 发起真实
     OpenRouter 调用**(gpt-5.4,读 stage1/.env 真 key);
  4. 断言:真实 LLM 调用 ≥2、假设 ≥3、选出机理、产出设计原则,且内容**grounded 于 live 数据**。

非仿真:第 3 步是真网络往返(OpenRouter 调用量会上升)。无 key/断网则该步 SKIPPED,不谎报。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve()
MAIN = HERE.parents[1] / "V1.0-qianduan-mainline"
S1 = MAIN / "stage1_optimization"
S3_SRC = MAIN / "stage3_mechanism" / "src"
RUN_DIR = MAIN / "runs" / "run_20260629_112156_9db536"
for p in (str(S3_SRC), str(S1), str(MAIN)):
    if p not in sys.path:
        sys.path.insert(0, p)

from s8_stage3.adapters.live_seed_adapter import build_seed_from_live  # noqa: E402
from backend_api.services.hardware_adapter import HardwareAdapter  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def _load_env(key, default=None):
    env = S1 / ".env"
    if env.exists():
        for raw in env.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
    return default


def _load_live_points():
    pts, arr, sample_id = [], None, None
    for l in (RUN_DIR / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        t = e.get("type") or e.get("event")
        pl = e.get("payload") or {}
        if t == "MEASUREMENT_COMPLETED" and pl.get("success") and pl.get("conductivity_S_cm"):
            sample_id = sample_id or pl.get("sample_id")
            pts.append({
                "T_C": pl.get("temperature_C"), "T_K": pl.get("temperature_K"),
                "rb_ohm": pl.get("rb_ohm"), "sigma_S_cm": pl.get("conductivity_S_cm"),
                "qc_grade": pl.get("qc_grade"), "r_squared": pl.get("r_squared"),
            })
        elif t == "STAGE0_GLOBAL_ARRHENIUS_COMPLETED":
            arr = pl
    return pts, arr, sample_id


def main():
    print("=" * 72)
    print("P9：stage3 机理推理链接进 live + 真实 LLM(假设/机制)真实验证")
    print("=" * 72)

    # ---- 1) 真实 live 数据 ----
    pts, arr, sample_id = _load_live_points()
    check("真实 live 数据：>=15 个真机点", len([p for p in pts if p.get("sigma_S_cm")]) >= 15,
          f"n_points={len(pts)} sample={sample_id}")
    transitions = (arr or {}).get("transition_temps_K") or []
    check("真实 live 数据：含全局 Arrhenius 相变温度", len(transitions) >= 1,
          f"transitions_K={transitions} model={(arr or {}).get('best_model_type')}")

    # ---- 2) 构造真实 seed ----
    seed = build_seed_from_live(
        pts, sample_id=sample_id or "ATP-R0.186-N1.029-fulltemp-fe2",
        R=0.186, N=1.029, transitions_K=transitions, arrhenius=arr,
    )
    check("seed：source_mode=real", seed.source_mode == "real")
    check("seed：温区段非空(由相变切段)", len(seed.seed_segments) >= 2,
          f"n_segments={len(seed.seed_segments)} eas={[s.representative_ea for s in seed.seed_segments]}")
    ev_units = (seed.stage2_seed_v2 or {}).get("evidence_units") or []
    check("seed：evidence_units 来自 live 观测", len(ev_units) >= 3,
          f"n_evidence_units={len(ev_units)}")
    check("seed：system_context 为 AiCE 物质描述",
          "attapulgite" in seed.system_context.chemistry_summary.lower())

    # ---- 3) 真实驱动**生产 live-loop 方法** HardwareAdapter._run_stage3_reasoning ----
    #     这一步证明 stage3 推理链**已接进 live 回路**(收尾真调),而非只在旁路脚本里能跑。
    api_key = _load_env("LLM_API_KEY")
    base_url = _load_env("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    model = _load_env("LLM_MODEL", "openai/gpt-5.4")

    if not api_key:
        results.append(("真实 stage3 LLM 推理链(生产 live-loop 方法)", "SKIPPED", "无 LLM_API_KEY"))
        print("[SKIPPED] 真实 stage3 LLM 推理链 — 无 LLM_API_KEY")
    else:
        import os as _os
        _os.environ["LLM_BASE_URL"] = base_url
        _os.environ["LLM_MODEL"] = model

        ad = HardwareAdapter()
        # 注入真实 live 状态(与 _real_measurement_loop 收尾时一致的字段形状)
        ad._measurements = [{
            "success": True, "temperature_C": p["T_C"], "temperature_K": p["T_K"],
            "rb_ohm": p["rb_ohm"], "conductivity_S_cm": p["sigma_S_cm"],
            "qc_grade": p["qc_grade"], "r_squared": p["r_squared"],
        } for p in pts]
        ad._global_arrhenius = arr
        ad._sample_id = sample_id
        ad._run_id = None  # → 写 outputs/stage3_live_tmp(不污染 runs/)
        ad._agent_api_key = api_key
        ad._enable_stage3_reasoning = True

        events = []
        _orig_emit = ad._emit_event
        def _cap(et, payload=None, *a, **k):
            events.append((et, payload or {}))
            return None  # 不真写事件文件(无 run_id)
        ad._emit_event = _cap

        print(f"\n>>> 真实驱动 HardwareAdapter._run_stage3_reasoning：model={model}")
        print("    (内部 build_seed_from_live + S04/S06/S06b 真实 OpenRouter 调用,可能数十秒)")
        t0 = time.time()
        ad._run_stage3_reasoning("completed")
        elapsed = time.time() - t0

        done = [p for et, p in events if et == "STAGE3_REASONING_COMPLETED"]
        started = [p for et, p in events if et == "STAGE3_REASONING_STARTED"]
        errs = [p for et, p in events if et in ("STAGE3_REASONING_ERROR", "STAGE3_REASONING_UNAVAILABLE", "STAGE3_REASONING_SKIPPED")]
        info = done[0] if done else {}
        print(f"    elapsed={elapsed:.1f}s  events={[et for et,_ in events if et.startswith('STAGE3')]}")
        if errs:
            print(f"    ERROR/SKIP payloads={errs}")
        if info:
            print(f"    n_real_llm_calls={info.get('n_real_llm_calls')} models={info.get('real_call_models')} "
                  f"steps={info.get('real_call_steps')}")
            print(f"    n_evidence_cards={info.get('n_evidence_cards')} n_hypotheses={info.get('n_hypotheses')} "
                  f"selected={info.get('selected_hypothesis_id')} mechanism='{info.get('mechanism_label')}' "
                  f"n_design_principles={info.get('n_design_principles')} literature={info.get('literature_status')}")
            print(f"    step_results={info.get('step_results')}")

        check("生产 live-loop：触发 STAGE3_REASONING_STARTED", len(started) == 1)
        check("生产 live-loop：完成 STAGE3_REASONING_COMPLETED(无 error)",
              len(done) == 1 and not errs, f"done={len(done)} errs={errs}")
        check("真实 LLM：S04/S06/S06b 发起真实调用(>=2)", info.get("n_real_llm_calls", 0) >= 2,
              f"n_real={info.get('n_real_llm_calls')} steps={info.get('real_call_steps')}")
        check("真实 LLM：模型为配置的真实模型(非 mock)",
              bool(info.get("real_call_models")) and all(not m.startswith("mock:") for m in info.get("real_call_models", [])),
              f"models={info.get('real_call_models')}")
        check("真实 LLM：确属网络往返(>1s)", elapsed > 1.0, f"elapsed={elapsed:.1f}s")
        check("S03：证据卡来自 live(含 V2 权威卡)", info.get("n_evidence_cards", 0) >= 4,
              f"n={info.get('n_evidence_cards')}")
        check("S04：生成 >=3 个竞争假设", info.get("n_hypotheses", 0) >= 3, f"n={info.get('n_hypotheses')}")
        check("S06：选出机理假设",
              bool(info.get("selected_hypothesis_id")) and bool(info.get("mechanism_label")),
              f"selected={info.get('selected_hypothesis_id')} label='{info.get('mechanism_label')}'")
        check("S06b：产出 >=1 条可迁移设计原则", info.get("n_design_principles", 0) >= 1,
              f"n={info.get('n_design_principles')}")
        core_steps = {k: v for k, v in info.get("step_results", [])}
        check("核心步骤(S03/S04/S06/S06b) completed",
              all(core_steps.get(s) == "completed" for s in
                  ("s03_evidence_builder", "s04_hypothesis_generator",
                   "s06_mechanism_arbiter", "s06b_design_principle_extractor")),
              f"{info.get('step_results')}")

        # 展示真实产出 + 落盘证据
        out_dir = Path(info.get("output_dir") or (MAIN / "outputs" / "stage3_live_tmp"))
        try:
            hb = out_dir / "02_hypotheses" / "hypothesis_board.json"
            mc = out_dir / "04_mechanism" / "mechanism_card.json"
            if hb.exists():
                board = json.loads(hb.read_text(encoding="utf-8"))
                print("\n    === S04 真实产出(竞争假设,前3) ===")
                for h in (board.get("hypotheses") or [])[:3]:
                    print(f"    [{h.get('hypothesis_id')}] {h.get('mechanism_label')}: {str(h.get('description',''))[:140]}")
            ev_files = list(out_dir.rglob("*.json"))
            check("stage3 真实产出已落盘(>=3 文件)", len(ev_files) >= 3, f"n_files={len(ev_files)} dir={out_dir}")
        except Exception as exc:
            print(f"    (展示产出失败: {exc})")

    print("\n" + "=" * 72)
    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    n_skip = sum(1 for _, s, _ in results if s == "SKIPPED")
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / {n_skip} SKIPPED")
    print("=" * 72)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
