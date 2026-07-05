# -*- coding: utf-8 -*-
"""P8 验证：把 "agent 大脑" 真正接进闭环（R²-Memory + C³ → LLM 决策 prompt）。

回应用户核心质疑："在做 agent 却几乎不调模型"。本脚本用**生产模块本身**：
  1. 用 live_memory_bridge 建真实治理记忆（含跨域守卫），取 read_projection；
  2. 用 scientific_convergence 出 C³ 收敛证书快照；
  3. 用 phase_detect.build_decision_user_message 证明两者**真的进了 LLM prompt**；
  4. 用 phase_detect.analyze_experiment_state 发起**一次真实 OpenRouter 调用**
     （读 stage1_optimization/.env 里的真 key + gpt-5.4），证明 agent 大脑被真正调用。

非仿真：第 4 步是真网络请求；OpenRouter 调用量会因此 +1。无 key 或断网则该步标记为
SKIPPED（其余结构性校验仍跑），脚本不谎报成功。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK，强制 UTF-8
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve()
MAIN = next(_p for _p in HERE.parents if _p.name == "V1.0-qianduan-mainline")
S1 = MAIN / "stage1_optimization"
S0_ANALYSIS = MAIN / "stage0_measurement" / "modules" / "analysis"
for p in (str(S1), str(S0_ANALYSIS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from scientific_memory import live_memory_bridge as bridge  # noqa: E402
from scientific_memory.agent_memory import Use  # noqa: E402
from scientific_convergence import shadow_convergence  # noqa: E402
import phase_detect  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def _load_env_key():
    """从 stage1_optimization/.env 读 LLM key/base_url/model（与后端兜底同源）。"""
    env = S1 / ".env"
    cfg = {}
    if env.exists():
        for raw in env.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return (
        cfg.get("LLM_API_KEY") or os.environ.get("LLM_API_KEY") or os.environ.get("POLOAPI_KEY"),
        cfg.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        cfg.get("LLM_MODEL", "openai/gpt-5.2"),
    )


def main():
    print("=" * 72)
    print("P8：agent 大脑接进闭环（R²-Memory + C³ → LLM 决策）真实验证")
    print("=" * 72)

    # ---- 1) 治理记忆：建本域测量记忆 + 外域守卫，取投影 ----
    mem = bridge.new_campaign_memory()
    foreign_id = bridge.install_cross_domain_guard(mem)
    sample = "ATP-R0.186-N1.029-fulltemp-fe2"
    temps_C = [25.0, 15.0, 5.0, -5.0, -15.0, -25.0]
    rb = [1.0e3, 1.4e3, 2.0e3, 3.0e3, 4.6e3, 7.2e3]
    sig = [1.0e-4, 7.0e-5, 5.0e-5, 3.3e-5, 2.2e-5, 1.4e-5]
    for i, (tc, r, s) in enumerate(zip(temps_C, rb, sig)):
        bridge.record_point(
            mem, step_idx=i, sample_id=sample, T_C=tc, rb_ohm=r, sigma_S_cm=s,
            qc_grade="A", governance_verdict="ADMITTED",
        )

    proj = bridge.read_projection(mem, max_items=10)
    check("记忆投影：本域记忆非空", proj["n_in_domain_memory"] >= len(temps_C),
          f"n_in_domain={proj['n_in_domain_memory']}")
    check("记忆投影：含外域迁移参照", len(proj["cross_domain_refs"]) >= 1,
          f"refs={[r['item_id'] for r in proj['cross_domain_refs']]}")
    ref = proj["cross_domain_refs"][0] if proj["cross_domain_refs"] else {}
    check("跨域守卫：外域参照禁作本域训练标签",
          ref.get("usable_as_training_label") is False,
          f"usable_as_training_label={ref.get('usable_as_training_label')}")
    check("用途门：外域项 can_use(TRAINING_LABEL)=False",
          (foreign_id is not None) and (not mem.can_use(foreign_id, Use.TRAINING_LABEL)))

    # ---- 2) C³ 收敛证书快照（mid-run：legacy 继续）----
    metro_med = 0.18  # 取本材料 Rb-ACT 实测量级
    term_mid = {"verdict": "continue", "triggered_by": [], "convergence": {}, "progress": {}, "budget": {}}
    cert_mid = shadow_convergence(
        term_mid, metrological_uncertainty_dex=metro_med,
        repro_replicates_have=1, repro_replicates_required=3, claim_stability=1.0,
    )
    conv_snapshot = {
        "recommended_action": cert_mid.to_dict()["recommended_action"],
        "delta_vs_legacy": cert_mid.to_dict()["delta_vs_legacy"],
        "reasons": cert_mid.to_dict()["reasons"],
        "metrological_uncertainty_dex_median": metro_med,
        "reproducibility": {"have": 1, "required": 3},
    }
    check("C³ 快照：mid-run 不建议停止",
          conv_snapshot["recommended_action"] != "STOP",
          f"recommended={conv_snapshot['recommended_action']}")

    # ---- 2b) C³ 真价值：legacy 想停但复现地板未满 → 推迟停止 ----
    term_end = {"verdict": "loop_can_end", "triggered_by": ["sweep_complete"],
                "convergence": {}, "progress": {}, "budget": {}}
    cert_defer = shadow_convergence(
        term_end, metrological_uncertainty_dex=metro_med,
        repro_replicates_have=1, repro_replicates_required=3, claim_stability=1.0,
    )
    check("C³ 真价值：legacy 想停 + 复现未满 → c3_defers_stop",
          cert_defer.to_dict()["delta_vs_legacy"] == "c3_defers_stop",
          f"delta={cert_defer.to_dict()['delta_vs_legacy']}")

    # ---- 3) 证明 memory + convergence 真的进了 LLM prompt ----
    history = []
    for tc, r in zip(temps_C, rb):
        history.append(SimpleNamespace(
            success=True, rb_ohm=r, temperature_C=tc, temperature_K=tc + 273.15,
            fit_quality=0.999, kk_warning=False, conductivity_S_per_cm=None,
        ))
    ctx = phase_detect._prepare_agent_context(history)
    check("prompt 上下文：ready（>=5 有效点）", ctx.get("status") == "ready",
          f"status={ctx.get('status')}")
    user_msg = phase_detect.build_decision_user_message(ctx, memory_projection=proj, convergence=conv_snapshot)
    check("prompt 注入：含 R²-Memory 块", "治理记忆（R²-Memory" in user_msg)
    check("prompt 注入：含外域守卫提示", "usable_as_training_label" in user_msg)
    check("prompt 注入：含 C³ 收敛证据块", "C³-Harness" in user_msg)
    check("prompt 注入：含外域参照 item_id",
          (ref.get("item_id", "__none__") in user_msg))

    # ---- 4) 真实 OpenRouter 调用 ----
    api_key, base_url, model = _load_env_key()
    if not api_key:
        results.append(("真实 LLM 调用（OpenRouter）", "SKIPPED", "无 LLM_API_KEY"))
        print("[SKIPPED] 真实 LLM 调用（OpenRouter）— 无 LLM_API_KEY")
    else:
        print(f"\n>>> 发起真实 OpenRouter 调用：model={model} base_url={base_url} ...")
        t0 = time.time()
        decision = phase_detect.analyze_experiment_state(
            agent_context={
                "measurement_history": history,
                "memory_projection": proj,
                "convergence": conv_snapshot,
            },
            api_key=api_key, base_url=base_url, model=model,
            use_hardcoded_triggers=False,
        )
        elapsed = time.time() - t0
        err = decision.get("error")
        action = decision.get("action")
        reasoning = (decision.get("reasoning") or "").strip()
        print(f"    elapsed={elapsed:.2f}s  action={action}  error={err}")
        print(f"    reasoning={reasoning[:200]}")
        check("真实 LLM 调用：无 API 错误返回", err is None, f"error={err}")
        check("真实 LLM 调用：返回合法动作",
              action in ("CONTINUE", "FINE_GRAINED_SCAN", "ABORT"), f"action={action}")
        check("真实 LLM 调用：返回非空推理", len(reasoning) > 0)
        check("真实 LLM 调用：确属网络往返（耗时>0.3s）", elapsed > 0.3,
              f"elapsed={elapsed:.2f}s")

    # ---- 汇总 ----
    print("\n" + "=" * 72)
    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    n_skip = sum(1 for _, s, _ in results if s == "SKIPPED")
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / {n_skip} SKIPPED")
    print("=" * 72)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
