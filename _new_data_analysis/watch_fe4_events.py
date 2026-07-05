# -*- coding: utf-8 -*-
"""fe4 真机长跑事件监控:轮询 events.jsonl,打印治理/注入/门控/完成等关键事件。"""
import json
import time

P = (r"C:\Users\LBM\Desktop\new\acid-in-clay-close\V1.0-qianduan-mainline"
     r"\runs\run_20260702_144507_52a878\events.jsonl")
NOTABLE = ("FAULT_INJECTED", "FAULT_INJECTION_RESULT", "FAULT_INJECTION_SUMMARY",
           "TXN_ADMISSION", "COMMIT_GATE", "COMMIT_GATE_SHADOW", "ACTIVE_DESIGN",
           "MEASUREMENT_DONE", "MEASUREMENT_FAILED", "EXPERIMENT_COMPLETED",
           "EXPERIMENT_FAILED", "RUN_ERROR", "HARNESS_GOVERNANCE_ERROR",
           "AGENT_DECISION", "EPISTEMIC_SUMMARY", "FALSIFICATION_MARKET")
TERMINAL = ("EXPERIMENT_COMPLETED", "EXPERIMENT_FAILED", "RUN_ERROR")

seen = 0
done = False
while not done:
    try:
        with open(P, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    for line in lines[seen:]:
        try:
            j = json.loads(line)
        except Exception:
            continue
        t = j.get("type", "")
        if any(t.startswith(n) for n in NOTABLE):
            pl = json.dumps(j.get("payload", {}), ensure_ascii=False)[:300]
            print(f"NOTABLE {j.get('seq')} {t} {pl}", flush=True)
        if t in TERMINAL:
            print("RUN_FINISHED_SENTINEL", t, flush=True)
            done = True
    seen = len(lines)
    if not done:
        time.sleep(60)
