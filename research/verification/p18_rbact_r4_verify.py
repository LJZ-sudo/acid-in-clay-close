# -*- coding: utf-8 -*-
"""P18 验证(P13-E):Rb-ACT R4 预注册 —— 真谱双跑 + 契约 + 审计接入,legacy 永不覆盖。

R4 的**正式生产替换 legacy** 须真机多批灰度(G-5)。本步只做 R4 **预注册契约 + 审计接入**,
用真实 genuine-live run 的 EIS 谱做 legacy↔Rb-ACT 双跑,断言:
  1. 预注册契约产物:方法指纹(决策代码 sha256 + 阈值 sha256)+ 验收门 + UTC 时间戳 + contract_hash;
  2. 契约不可变性:重算哈希一致;篡改任一字段 → 哈希改变(封印有效);
  3. 审计接入 measurement_txn:R4 审计-only 信号随事务留痕,但 **entered_bo 与不带 R4 时完全一致**
     (证明"接审计但不改数值链 / 不替换 legacy");
  4. legacy 永不覆盖:审计 `legacy_overwritten=0`,且每点 legacy_rb 与 rb_act 后验是独立字段;
  5. 真谱 **0 未解释翻转**(非弃权点 |Δlog10 Rb| 不超阈值);
  6. rb_r4_active 恒 False(软件半绝不激活替换)。
无谱数据则 SKIP,不谎报。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

HERE = Path(__file__).resolve()
NDA = next(_p for _p in HERE.parents if _p.name == "research")
MAIN = NDA.parent / "V1.0-qianduan-mainline"
# G-5:多批 live 合并审计 —— fe2 + fe3 + fe4b 三次真机 run 的谱合并配对,
# 凑满预注册验收门的 paired_points≥30(单 run 也够,合并=跨 run 稳健性更强)。
EVID_RUNS = [
    MAIN / "runs" / "run_20260629_112156_9db536" / "evidence",   # fe2
    MAIN / "runs" / "run_20260630_135646_f33d5e" / "evidence",   # fe3
    MAIN / "runs" / "run_20260702_144507_52a878" / "evidence",   # fe4b(G-4 enforce 长跑)
]
for p in (str(MAIN / "stage0_measurement"), str(MAIN / "stage1_optimization"), str(NDA)):
    if p not in sys.path:
        sys.path.insert(0, p)

import rb_act as RB  # noqa: E402
from scientific_harness.measurement_txn import (  # noqa: E402
    submit_measurement_offline, build_measurement_signals_from_bundle)

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, PASS if cond else FAIL, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def load_spectra():
    out = []
    for evid in EVID_RUNS:
        if not evid.exists():
            continue
        run_id = evid.parent.name
        for fp in sorted(evid.glob("EP-*.json")):
            d = json.loads(fp.read_text(encoding="utf-8")).get("payload", {})
            f = d.get("frequencies"); zr = d.get("z_real"); zi = d.get("z_imag")
            if not (f and zr and zi) or len(f) < 10:
                continue
            out.append({
                "T_C": d.get("temperature_C"), "rb_ohm": d.get("rb_ohm"), "run_id": run_id,
                "f": np.array(f, float), "zr": np.array(zr, float), "zi": np.array(zi, float),
            })
    out.sort(key=lambda s: (s["T_C"] if s["T_C"] is not None else 0), reverse=True)
    return out


def main():
    print("=" * 74)
    print("P18:Rb-ACT R4 预注册 —— 真谱双跑 + 契约 + 审计接入(legacy 永不覆盖)")
    print("=" * 74)
    spectra = load_spectra()
    if len(spectra) < 5:
        print(f"[SKIP] 真实谱不足({len(spectra)}),跳过(不谎报)")
        return 0
    from collections import Counter
    by_run = Counter(s["run_id"] for s in spectra)
    print(f"真实谱 n={len(spectra)}  T∈[{spectra[-1]['T_C']:.1f},{spectra[0]['T_C']:.1f}]°C  "
          f"按 run:{dict(by_run)}")

    # --- 真谱 legacy↔Rb-ACT 双跑 ---
    rb_results = []
    for s in spectra:
        r = RB.analyze_spectrum(s["f"], s["zr"], s["zi"],
                                thickness_cm=0.1, area_cm2=1.96,
                                temperature_K=(s["T_C"] + 273.15) if s["T_C"] is not None else 298.15)
        rb_results.append(r)
    n_report = sum(1 for r in rb_results if r.reported())
    print(f"双跑完成:report={n_report} abstain={len(rb_results)-n_report}")

    # ---- 1. 预注册契约产物 ----
    contract = RB.build_r4_prereg_contract(sample_id="p18-fe3", note="P18 真谱预注册审计")
    fp = contract.get("method_fingerprint", {})
    check("契约含方法指纹(skill 源 sha256 + 阈值 sha256)",
          bool(fp.get("skill_source_sha256")) and bool(fp.get("thresholds_sha256")),
          f"skill_sha={str(fp.get('skill_source_sha256'))[:12]}… thr_sha={str(fp.get('thresholds_sha256'))[:12]}…")
    check("契约含验收门 + UTC 时间戳 + contract_hash",
          bool(contract.get("acceptance_gates")) and bool(contract.get("created_utc"))
          and bool(contract.get("contract_hash")),
          f"hash={contract['contract_hash'][:16]}…")
    check("契约声明 legacy_override=False（永不覆盖）", contract.get("legacy_override") is False)

    # ---- 2. 契约不可变性(封印) ----
    import hashlib as _h
    body = {k: v for k, v in contract.items() if k != "contract_hash"}
    recomputed = _h.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    check("契约哈希可复算一致(封印有效)", recomputed == contract["contract_hash"])
    tampered = dict(body); tampered["acceptance_gates"] = dict(tampered["acceptance_gates"])
    tampered["acceptance_gates"]["max_unexplained_flips"] = 999
    tampered_hash = _h.sha256(json.dumps(tampered, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    check("篡改验收门 → 哈希改变(防事后偷改阈值)", tampered_hash != contract["contract_hash"])

    # ---- 3. 真谱审计 ----
    audit = RB.audit_series(rb_results, contract=contract)
    print(f"审计:n_paired={audit['n_paired']} 未解释翻转={audit['n_unexplained_flips']} "
          f"median|Δ|={audit['median_abs_delta_log10']} report_rate={audit['report_rate']}")
    check("真谱 0 未解释翻转(非弃权点 |Δlog10 Rb| 不超阈值)",
          audit["n_unexplained_flips"] == 0,
          f"flips={audit['n_unexplained_flips']}")
    check("legacy 永不覆盖(legacy_overwritten=0)", audit["legacy_overwritten"] == 0)
    check("审计含各验收门 pass/threshold(可判定)",
          set(audit["gate_checks"]) >= {"paired_points", "unexplained_flips",
                                        "report_rate", "median_abs_delta_dex"})
    check("rb_r4_active 恒 False(软件半绝不激活替换)", audit["rb_r4_active"] is False)

    # ---- 4. 审计接入 measurement_txn:entered_bo 与不带 R4 时完全一致 ----
    r0 = rb_results[0]
    T_K = (spectra[0]["T_C"] + 273.15) if spectra[0]["T_C"] is not None else 298.15
    bundle = {
        "sample_id": "p18-fe3",
        "geometry": {"thickness_cm": 0.1, "area_cm2": 1.96},
        "file_hashes": {"p18_step_0": "live"},
        "eis_points": [{"T_K": T_K, "status": "OK",
                        "kk_residual": 0.02, "rb_ohm": r0.legacy_rb_ohm,
                        "rb_method": r0.legacy_method}],
        "arrhenius": {},
    }
    base_sig = dict(r0.admission_signals or {})
    r4_sig = RB.prereg_admission_signals(contract, audit)
    with_r4 = dict(base_sig); with_r4.update(r4_sig)

    txn_base = submit_measurement_offline(bundle, rb_act_signals=base_sig)
    txn_r4 = submit_measurement_offline(bundle, rb_act_signals=with_r4)
    adm_base = {str(getattr(k, "name", k)): v["status"] for k, v in txn_base.use_admissions.items()}
    adm_r4 = {str(getattr(k, "name", k)): v["status"] for k, v in txn_r4.use_admissions.items()}
    check("接 R4 审计信号后 entered_bo 完全不变(不改数值链)",
          txn_base.entered_bo == txn_r4.entered_bo and adm_base == adm_r4,
          f"entered_bo base={txn_base.entered_bo} r4={txn_r4.entered_bo}")

    sig_r4 = build_measurement_signals_from_bundle(bundle, rb_act_signals=with_r4)
    check("R4 审计-only 信号确随事务留痕(rb_r4_preregistered=True / rb_r4_active=False)",
          sig_r4.get("rb_r4_preregistered") is True and sig_r4.get("rb_r4_active") is False
          and sig_r4.get("rb_r4_prereg_id") == contract["contract_hash"][:12],
          f"prereg_id={sig_r4.get('rb_r4_prereg_id')}")

    # ---- 5. 落盘产物 ----
    out = NDA / "epistemic_out" / "rb_act_r4_prereg.json"
    RB.write_r4_prereg(out, contract, audit)
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    check("rb_act_r4_prereg.json 落盘且可复载(含 contract+audit+admission_signals)",
          out.exists() and reloaded.get("contract", {}).get("contract_hash") == contract["contract_hash"]
          and reloaded.get("admission_signals", {}).get("rb_r4_active") is False,
          str(out))

    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print("\n" + "=" * 74)
    print(f"汇总:{n_pass} PASS / {n_fail} FAIL   "
          f"(真谱 n={len(spectra)};契约 hash={contract['contract_hash'][:12]}…;"
          f"未解释翻转={audit['n_unexplained_flips']})")
    print("=" * 74)
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
