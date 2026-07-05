# -*- coding: utf-8 -*-
"""短跑复验监控:逐条打印 AGENT_DECISION 的 llm_called/reasoning,序列化失败即刻标红。"""
import json
import time

P = (r"C:\Users\LBM\Desktop\new\acid-in-clay-close\V1.0-qianduan-mainline"
     r"\runs\run_20260703_193436_ba1b26\events.jsonl")
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
        p = j.get("payload", {})
        if t == "AGENT_DECISION":
            reason = str(p.get("reasoning", ""))[:60]
            ser = "序列化失败" in reason or any("serialize" in str(w) for w in (p.get("warnings") or []))
            tag = "SERIALIZE_FAIL" if ser else ("LLM_OK" if p.get("llm_called") else "RULE")
            print(f"DECISION step={p.get('step_idx')} n={p.get('n_points')} {tag} "
                  f"llm_called={p.get('llm_called')} reason={reason}", flush=True)
        elif t in ("MEASUREMENT_FAILED", "HARNESS_GOVERNANCE_ERROR", "SAFETY_CONSECUTIVE_FAIL_FUSE"):
            print(f"WARN {t} {json.dumps(p, ensure_ascii=False)[:150]}", flush=True)
        if t in TERMINAL:
            print("RUN_FINISHED_SENTINEL", t, json.dumps(p, ensure_ascii=False)[:150], flush=True)
            done = True
    seen = len(lines)
    if not done:
        time.sleep(60)
