# -*- coding: utf-8 -*-
"""P3 验证:measurement_txn 真门控(entered_bo)。用真实 run 的逐点 TXN_ADMISSION
(或从真机谱重算)切 committed/rejected 视图,并把门控真实作用到一个合成 Stage0 bundle 上:
  - committed 视图正确剔除 3 个深冷点(entered_bo=False);
  - filter_bundle_eis_points 据 rejected 温度真删 bundle 的 eis_points(下游 BO 不再吃这些点);
  - committed 数 + rejected 数 == 总点数(无重复/丢失)。

用法: python p3_commit_gate_verify.py [run_id]
默认 run = run_20260629_112156_9db536。
"""
import json
import sys
from pathlib import Path

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "run_20260629_112156_9db536"
REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "V1.0-qianduan-mainline").parent
MAIN = REPO / "V1.0-qianduan-mainline"
sys.path.insert(0, str(MAIN / "stage1_optimization"))

from scientific_harness.commit_gate import build_committed_view, filter_bundle_eis_points  # noqa: E402


def load_txn_rows(run_id):
    """从真实 run 事件读逐点 TXN_ADMISSION(entered_bo 为真机当时裁决)。"""
    ev = MAIN / "runs" / run_id / "events.jsonl"
    rows = []
    with ev.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (e.get("type") or e.get("event_type")) != "TXN_ADMISSION":
                continue
            pl = e.get("payload", {})
            rows.append({"step_idx": pl.get("step_idx"), "T_C": pl.get("temperature_C"),
                         "entered_bo": bool(pl.get("entered_bo")),
                         "admissions": pl.get("admissions", {})})
    rows.sort(key=lambda r: r.get("step_idx", 0))
    return rows


def main():
    rows = load_txn_rows(RUN_ID)
    print(f"== P3 commit-gate verify  run={RUN_ID} ==")
    print(f"TXN_ADMISSION rows: {len(rows)}")
    view = build_committed_view(rows)
    print(f"committed={view['n_committed']}  rejected={view['n_rejected']}  total={view['n_total']}")
    print(f"rejected_T_C: {view['rejected_T_C']}")

    # 用 committed 视图的真实温度构造一个 Stage0-bundle 形态,验证门控真删点。
    bundle = {"sample_id": "ATP-R0.186-N1.029-fulltemp-fe2",
              "eis_points": [{"T_C": r["T_C"], "rb_ohm": 1.0} for r in rows]}
    res = filter_bundle_eis_points(bundle, view["rejected_T_C"])
    print(f"bundle gate: before={res['n_before']} after={res['n_after']} "
          f"dropped={res['n_dropped']} dropped_T_C={res['dropped_T_C']}")

    n_total = len(rows)
    checks = {
        "rows_loaded": n_total > 0,
        "rejected_eq_3": view["n_rejected"] == 3,
        "committed_eq_total_minus_3": view["n_committed"] == n_total - 3,
        "partition_no_loss": view["n_committed"] + view["n_rejected"] == n_total,
        "rejected_are_deep_cryo": all((t is not None and t <= -50) for t in view["rejected_T_C"]),
        "bundle_dropped_eq_rejected": res["n_dropped"] == view["n_rejected"],
        "bundle_after_eq_committed": res["n_after"] == view["n_committed"],
    }
    print("-- checks --")
    all_ok = True
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        all_ok = all_ok and v
    print(f"== {'ALL PASS' if all_ok else 'FAILED'} ==")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
