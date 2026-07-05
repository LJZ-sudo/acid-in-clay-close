# -*- coding: utf-8 -*-
"""P3 全温区真跑监控：拉 run 事件，打印关键时间线 + 治理逐点裁决 + 新鲜性核验。"""
import json
import sys
import urllib.request

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else None
BASE = "http://127.0.0.1:8000/api"

KEY = {
    "COOL_TO_START_STARTED", "COOL_TO_START_DONE", "COOL_TO_START_FAILED",
    "SET_T", "WAIT_STABLE_ARRIVAL_START", "EIS_RUN",
    "CHI_MEASUREMENT_STARTED", "CHI_MEASUREMENT_COMPLETED", "CHI_MEASUREMENT_FAILED",
    "MEASUREMENT_SKIPPED", "Rb_FIT", "QC_GRADE",
    "SHADOW_VERDICT", "RBACT_DECISION", "TXN_ADMISSION",
    "MEASUREMENT_COMPLETED", "HARNESS_GOVERNANCE_ERROR", "HARNESS_SHADOW_STARTED",
    "SAFETY_CONSECUTIVE_FAIL_FUSE", "SAFETY_RB_FUSE", "SAFETY_CONDUCTIVITY_FUSE",
    "FINALIZE_REHEAT_STARTED", "REHEAT_SETTLE_STARTED", "EXPERIMENT_COMPLETED",
    "EXPERIMENT_FINISHED", "EXPERIMENT_FAILED", "STREAM_END",
}


def jget(url):
    return json.load(urllib.request.urlopen(url, timeout=30))


def main():
    rid = RUN_ID
    if not rid:
        st = jget(f"{BASE}/control/status")
        rid = st.get("run_id")
    print(f"== run {rid} ==")
    st = jget(f"{BASE}/control/status")
    print(f"status: running={st.get('running')} temp={st.get('current_temperature')} target={st.get('target_temperature')} measurements={st.get('measurement_count')}")

    events = jget(f"{BASE}/runs/{rid}/events?limit=5000").get("events", [])
    print(f"total events: {len(events)}")
    for e in events:
        t = (e.get("type") or e.get("event_type") or "").upper()
        if t not in KEY:
            continue
        pl = e.get("payload", {}) if isinstance(e.get("payload"), dict) else {}
        ts = (e.get("ts") or e.get("timestamp") or "")[-12:]
        si = pl.get("step_idx")
        extra = ""
        if t == "SET_T":
            extra = f"target={pl.get('target_temperature_C')}"
        elif t in ("COOL_TO_START_DONE", "COOL_TO_START_FAILED"):
            extra = f"actual={pl.get('actual_C')} {pl.get('reason','')}"
        elif t == "CHI_MEASUREMENT_COMPLETED":
            extra = f"file={str(pl.get('output_file'))[-42:]} n={pl.get('n_points')}"
        elif t == "Rb_FIT":
            extra = f"T={pl.get('temperature_C')} Rb={pl.get('rb_ohm')} sigma={pl.get('conductivity_S_cm')} R2={pl.get('r_squared')}"
        elif t == "SHADOW_VERDICT":
            extra = f"agree={pl.get('agree')} rate={pl.get('agreement_rate')} blind={pl.get('blind_retry_count')}"
        elif t == "RBACT_DECISION":
            extra = f"{pl.get('decision')} dlog={pl.get('abs_dlog10_rb')} flip={pl.get('unexplained_flip')}"
        elif t == "TXN_ADMISSION":
            extra = f"bo={pl.get('entered_bo')} adm={pl.get('admissions')}"
        elif t == "MEASUREMENT_SKIPPED":
            extra = f"target={pl.get('target_temperature_C')} actual={pl.get('actual_temperature_C')} {pl.get('reason','')}"
        print(f"  [{ts}] {t:<26} step={si} {extra}")


if __name__ == "__main__":
    main()
