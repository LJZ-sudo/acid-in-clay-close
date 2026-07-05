# -*- coding: utf-8 -*-
"""P1 验证:用真实 run 的逐点 MEASUREMENT_COMPLETED 事件,经 live_memory_bridge
(与 hardware_adapter live 回路同一组函数)喂入 R²-Memory,核验:
  - 每个真实点写门通过(ACTIVE),记忆点数 == 真实测量点数;
  - 跨域守卫:外域 transfer_reference 不进本域 training_labels,且显式企图作 training_label 被拦;
  - 多轮一致性 round_continuity.ok == True;
  - 决策保持压缩证书 ok == True(非恒等:每 regime 仅保留一条仍覆盖全部条件)。

用法: python p1_memory_verify.py [run_id]
默认 run = run_20260629_112156_9db536(前端驱动全温区 genuine live)。
"""
import json
import sys
from pathlib import Path

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "run_20260629_112156_9db536"
ROOT = Path(__file__).resolve().parents[1] / "V1.0-qianduan-mainline"
sys.path.insert(0, str(ROOT / "stage1_optimization"))

from scientific_memory import live_memory_bridge as bridge  # noqa: E402
from scientific_memory.agent_memory import Role, Use, UsageViolation  # noqa: E402


def load_points(run_id):
    ev_path = ROOT / "runs" / run_id / "events.jsonl"
    pts = []
    with ev_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (e.get("type") or e.get("event_type")) != "MEASUREMENT_COMPLETED":
                continue
            pl = e.get("payload", {})
            pts.append(pl)
    pts.sort(key=lambda p: p.get("step_idx", 0))
    return pts


def main():
    pts = load_points(RUN_ID)
    print(f"== P1 R2-Memory live-bridge verify  run={RUN_ID} ==")
    print(f"real measurement points: {len(pts)}")

    mem = bridge.new_campaign_memory()
    foreign = bridge.install_cross_domain_guard(mem)
    print(f"cross-domain guard installed: {foreign}")

    sample_id = pts[0].get("sample_id", "unknown") if pts else "unknown"
    accepted = 0
    for p in pts:
        res = bridge.record_point(
            mem,
            step_idx=p.get("step_idx", 0),
            sample_id=sample_id,
            T_C=p.get("temperature_C"),
            rb_ohm=p.get("rb_ohm"),
            sigma_S_cm=p.get("conductivity_S_cm"),
            qc_grade=p.get("qc_grade"),
            governance_verdict="replay",
        )
        if res["decision"] == "ACCEPT" and res["status"] == "ACTIVE":
            accepted += 1

    summary = bridge.finalize(mem, sample_id=sample_id, foreign_item_id=foreign)

    # 独立再断言一次跨域拦截(assert_use 必须抛)
    raised = False
    try:
        mem.assert_use(foreign, Use.TRAINING_LABEL)
    except UsageViolation:
        raised = True

    n_real = len(pts)
    cert = summary["compression_certificate"]
    checks = {
        "points_all_ACTIVE": accepted == n_real and n_real > 0,
        "n_memory_points==real": summary["n_memory_points"] == n_real,
        "n_training_labels==real": summary["n_training_labels"] == n_real,
        "foreign_excluded_from_labels": summary["foreign_excluded_from_labels"] is True,
        "cross_domain_guard_blocked": summary["cross_domain_guard_blocked"] is True,
        "cross_domain_assert_raised": raised,
        "round_continuity_ok": summary["round_continuity"]["ok"] is True,
        "compression_cert_ok": cert["ok"] is True,
        "compression_non_identity": len(cert["source_node_ids"]) < n_real,
    }

    print(f"accepted ACTIVE: {accepted}/{n_real}")
    print(f"training labels: {summary['n_training_labels']}  foreign_excluded={summary['foreign_excluded_from_labels']}")
    print(f"guard_blocked={summary['cross_domain_guard_blocked']}  assert_raised={raised}")
    print(f"round_continuity: {summary['round_continuity']}")
    print(f"compression cert: ok={cert['ok']}  kept={len(cert['source_node_ids'])}/{n_real}  "
          f"claim {cert['claim_level_before']}->{cert['claim_level_after']}  "
          f"div={cert['action_divergence']}  reasons={cert['reasons']}")
    print(f"kept conditions: {cert['preserved_conditions']}")
    print("-- checks --")
    all_ok = True
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        all_ok = all_ok and v
    print(f"== {'ALL PASS' if all_ok else 'FAILED'} ==")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
