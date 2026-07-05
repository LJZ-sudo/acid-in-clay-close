# -*- coding: utf-8 -*-
"""M2-4 / G4 — LLM 安全修正 vs 确定性基线。

回答 GPT/GPT-2 的问题:LLM 把 raw MOBO R=0.0285 修正到 R=0.28,这个"安全价值"
能否被确定性规则替代?用 **真实** SafetyValidator + 真实历史 R 范围 + 真实冻结 recipe,
对同一个 raw 建议跑 5 个基线,客观对照。

基线:
  RAW_MOBO              原始建议(R=0.0285)
  HARD_CONSTRAINED_MOBO 裁剪到硬边界 [low,high]
  DETERMINISTIC_PROJECTION 投影到"观测可行 R 域"[R_obs_min,R_obs_max]
  RULE_BASED_RISK_REPAIR  显式规则:R < R_obs_min → 上调到 R_obs_min
  LLM_TOPK_SELECTION    真实 LLM 修正(R=0.28,来自冻结 official_recipe.json)

关键事实(代码实证):SafetyValidator 硬边界是 R∈[0,1.04],**R=0.0285 在界内 → 安全箱
通过**;低 R 无 warning(只有 R>0.9 警告)。故硬约束抓不到"超低酸外推";确定性投影/规则
能抓到。结论据此客观给出,不预判、不为 LLM 护短。
绝不改 legacy;输出 *_v2。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

THIS = Path(__file__).resolve()
REPO_ROOT = THIS.parents[3]
MAINLINE = REPO_ROOT / "V1.0-qianduan-mainline"
STAGE1 = MAINLINE / "stage1_optimization"
sys.path.insert(0, str(STAGE1))

from canonical_input.campaign_parser import CampaignConfig  # noqa: E402
from safety.safety_validator import SafetyValidator  # noqa: E402

CAMPAIGN = STAGE1 / "campaigns" / "attapulgite_aice_campaign.json"
HISTORY_DB = STAGE1 / "campaign_memory" / "history_db_attapulgite.json"
OFFICIAL_RECIPE = REPO_ROOT / "research" / "prospective" / "line_B_mobo_closed_loop" / "official_recipe.json"


def _observed_r_range() -> Tuple[float, float]:
    db = json.loads(HISTORY_DB.read_text(encoding="utf-8-sig"))
    rs = [t["parameters"]["R"] for t in db["trials"]]
    return float(min(rs)), float(max(rs))


def _hard_bounds(cfg: CampaignConfig) -> Dict[str, Tuple[float, float]]:
    out = {}
    for name, c in (cfg.parameters or {}).items():
        out[name] = (float(c["low"]), float(c["high"]))
    return out


# --- 5 个基线(纯函数,作用于 raw 建议) --- #
def baseline_raw(raw, bounds, r_obs):
    return dict(raw), {}


def baseline_hard_constrained(raw, bounds, r_obs):
    out = {}
    changed = {}
    for k, v in raw.items():
        lo, hi = bounds[k]
        nv = min(max(v, lo), hi)
        out[k] = nv
        if abs(nv - v) > 1e-12:
            changed[k] = {"from": v, "to": nv}
    return out, changed


def baseline_deterministic_projection(raw, bounds, r_obs):
    """投影到观测可行 R 域 [r_obs_min, r_obs_max](N 仍受硬边界)。"""
    r_lo, r_hi = r_obs
    out, changed = baseline_hard_constrained(raw, bounds, r_obs)
    r = out.get("R")
    if r is not None:
        nr = min(max(r, r_lo), r_hi)
        if abs(nr - r) > 1e-12:
            changed["R"] = {"from": raw["R"], "to": nr, "reason": "project_to_observed_R_range"}
        out["R"] = nr
    return out, changed


def baseline_rule_risk_repair(raw, bounds, r_obs):
    """显式规则:R < 观测下限 → 上调到下限(编码"低 R 外推风险")。"""
    r_lo, _ = r_obs
    out, changed = baseline_hard_constrained(raw, bounds, r_obs)
    r = out.get("R")
    if r is not None and r < r_lo:
        changed["R"] = {"from": raw["R"], "to": r_lo, "reason": "R_below_observed_floor_rule"}
        out["R"] = r_lo
    return out, changed


def baseline_llm(raw, bounds, r_obs, llm_final=None):
    return dict(llm_final), {"R": {"from": raw["R"], "to": llm_final["R"], "reason": "llm_physical_correction"},
                             "N": {"from": raw["N"], "to": llm_final["N"]}}


def _evaluate(name: str, recipe: Dict[str, float], changed: Dict[str, Any],
              validator: SafetyValidator, r_obs: Tuple[float, float]) -> Dict[str, Any]:
    res = validator.validate(recipe)
    r_lo, r_hi = r_obs
    r = recipe.get("R")
    below = bool(r is not None and r < r_lo)
    return {
        "policy": name,
        "recipe": recipe,
        "changed": changed,
        "safety_passed": res.passed,
        "n_violations": len(res.violations),
        "n_warnings": len(res.warnings),
        "R_below_observed_floor": below,
        "R_extrapolation_distance": float(max(0.0, r_lo - r)) if r is not None else None,
        "in_observed_R_region": bool(r is not None and r_lo <= r <= r_hi),
    }


def run(out_subdir: str = "policy_ablation") -> Dict[str, Any]:
    cfg = CampaignConfig(str(CAMPAIGN))
    validator = SafetyValidator(cfg)
    bounds = _hard_bounds(cfg)
    r_obs = _observed_r_range()
    recipe = json.loads(OFFICIAL_RECIPE.read_text(encoding="utf-8"))
    raw = {"R": recipe["raw_mobo"]["R"], "N": recipe["raw_mobo"]["N"]}
    llm_final = {"R": recipe["llm_final"]["R"], "N": recipe["llm_final"]["N"]}

    rows: List[Dict[str, Any]] = []
    for name, fn in [
        ("RAW_MOBO", baseline_raw),
        ("HARD_CONSTRAINED_MOBO", baseline_hard_constrained),
        ("DETERMINISTIC_PROJECTION", baseline_deterministic_projection),
        ("RULE_BASED_RISK_REPAIR", baseline_rule_risk_repair),
    ]:
        rec, changed = fn(raw, bounds, r_obs)
        rows.append(_evaluate(name, rec, changed, validator, r_obs))
    rec, changed = baseline_llm(raw, bounds, r_obs, llm_final=llm_final)
    rows.append(_evaluate("LLM_TOPK_SELECTION", rec, changed, validator, r_obs))

    # 客观判定:硬约束是否抓到低 R?确定性规则是否能复制 LLM 方向?
    hard = next(r for r in rows if r["policy"] == "HARD_CONSTRAINED_MOBO")
    proj = next(r for r in rows if r["policy"] == "DETERMINISTIC_PROJECTION")
    rule = next(r for r in rows if r["policy"] == "RULE_BASED_RISK_REPAIR")
    llm = next(r for r in rows if r["policy"] == "LLM_TOPK_SELECTION")

    hard_misses_low_r = bool(hard["R_below_observed_floor"])  # 硬约束后仍在观测下限以下
    deterministic_repairs = bool(proj["in_observed_R_region"] and rule["in_observed_R_region"])
    llm_in_region = bool(llm["in_observed_R_region"])

    if hard_misses_low_r and deterministic_repairs:
        verdict = ("硬安全箱/硬约束抓不到 raw 的超低酸外推(R=0.0285 仍判通过);"
                   "确定性投影/规则可把 R 拉回观测可行域,方向与 LLM 一致 → "
                   "LLM 的安全修正**可被确定性规则替代**(但该规则当前不在安全箱中)。"
                   "应表述为'LLM 完成了一次合理的领域修正',不写'LLM 提供了独特安全能力'。")
    elif not deterministic_repairs and llm_in_region:
        verdict = "确定性基线未能修复而 LLM 修复 → LLM 在此案例提供了额外价值(需更多案例确认)。"
    else:
        verdict = "各策略表现相近;无法据此单点声称 LLM 安全价值不可替代。"

    summary = {
        "provenance": {
            "campaign": str(CAMPAIGN.relative_to(REPO_ROOT)),
            "official_recipe": str(OFFICIAL_RECIPE.relative_to(REPO_ROOT)),
            "freeze_commit": recipe.get("freeze_commit"),
            "observed_R_range": list(r_obs),
            "raw_mobo": raw, "llm_final": llm_final,
        },
        "results": rows,
        "key_findings": {
            "hard_box_passes_raw_low_R": next(r for r in rows if r["policy"] == "RAW_MOBO")["safety_passed"],
            "hard_constraint_misses_low_R": hard_misses_low_r,
            "deterministic_rule_repairs_direction": deterministic_repairs,
            "llm_in_observed_region": llm_in_region,
        },
        "verdict": verdict,
    }
    out_dir = REPO_ROOT / "research" / "results" / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "policy_ablation_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    s = run()
    print("Observed R range:", s["provenance"]["observed_R_range"])
    print(f"raw={s['provenance']['raw_mobo']}  llm={s['provenance']['llm_final']}\n")
    for r in s["results"]:
        print(f"  {r['policy']:24s} R={r['recipe']['R']:.4f} safe={r['safety_passed']} "
              f"warn={r['n_warnings']} below_floor={r['R_below_observed_floor']} "
              f"in_region={r['in_observed_R_region']}")
    print("\nVERDICT:", s["verdict"])
