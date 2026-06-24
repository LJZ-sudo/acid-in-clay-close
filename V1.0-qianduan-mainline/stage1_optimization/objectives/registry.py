# -*- coding: utf-8 -*-
"""目标函数注册表（M1-6 / G7）。

消除评分口径漂移：把"训练目标"(combined_score) 与"审计/展示目标"(score_v3) 显式隔离、
各带冻结哈希。任何 trial 入库时应盖 objective_definition_id + sha256；查询最优应按
objective_definition_id 而非裸字符串 "combined_score"。

来源唯一真相：configs/objective_registry.yaml。本模块不改写 memory_manager / 冻结闭环，
只提供"按定义查询/盖章/一致性校验"的纯函数,供 v2 与新代码使用(向后兼容)。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_THIS = Path(__file__).resolve()
MAINLINE_ROOT = _THIS.parents[2]                         # V1.0-qianduan-mainline/
REGISTRY_YAML = MAINLINE_ROOT / "configs" / "objective_registry.yaml"


@dataclass(frozen=True)
class ObjectiveDefinition:
    id: str
    role: str
    direction: str                  # maximize | minimize
    trial_objective_key: str        # trial.objectives 里的实际键名
    expression: str
    variables: List[str] = field(default_factory=list)
    units: str = "dimensionless"
    source: str = ""

    @property
    def sha256(self) -> str:
        """对"语义定义"做稳定哈希（id+方向+表达式+变量+键名），表达式改动即变。"""
        payload = json.dumps({
            "id": self.id,
            "direction": self.direction,
            "trial_objective_key": self.trial_objective_key,
            "expression": self.expression,
            "variables": list(self.variables),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_stamp(self) -> Dict[str, str]:
        return {
            "objective_definition_id": self.id,
            "objective_definition_sha256": self.sha256,
            "objective_role": self.role,
        }


def _load_yaml() -> Dict[str, Any]:
    import yaml
    if not REGISTRY_YAML.exists():
        raise FileNotFoundError(f"objective registry not found: {REGISTRY_YAML}")
    return yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8")) or {}


def load_registry() -> Dict[str, ObjectiveDefinition]:
    raw = _load_yaml()
    out: Dict[str, ObjectiveDefinition] = {}
    for o in raw.get("objectives", []) or []:
        defn = ObjectiveDefinition(
            id=o["id"],
            role=o.get("role", ""),
            direction=o.get("direction", "maximize"),
            trial_objective_key=o.get("trial_objective_key", o["id"]),
            expression=o.get("expression", ""),
            variables=list(o.get("variables", []) or []),
            units=o.get("units", "dimensionless"),
            source=o.get("source", ""),
        )
        out[defn.id] = defn
    return out


def get_objective(objective_id: str) -> ObjectiveDefinition:
    reg = load_registry()
    if objective_id not in reg:
        raise KeyError(f"unknown objective id '{objective_id}'; known: {list(reg)}")
    return reg[objective_id]


def objective_for_role(role: str) -> ObjectiveDefinition:
    """按 role_bindings 取目标定义（如 training / best_trial / pareto_annotation）。"""
    raw = _load_yaml()
    bindings = raw.get("role_bindings", {}) or {}
    if role not in bindings:
        raise KeyError(f"unknown role '{role}'; known: {list(bindings)}")
    return get_objective(bindings[role])


def stamp_metadata(objective_id: str) -> Dict[str, str]:
    """返回可塞进 trial.metadata 的目标定义盖章（id + sha256 + role）。"""
    return get_objective(objective_id).to_stamp()


def get_best_trial_by_definition(
    memory_manager,
    objective_id: str,
) -> Optional[Dict[str, Any]]:
    """按 objective_definition_id 查询历史最优（取代裸 get_best_trial("combined_score")）。

    用注册表里的 trial_objective_key + direction 调 memory_manager.get_best_trial,
    禁止调用方再手写键名/方向,从根上杜绝"优化一个目标、用另一个键名宣布成功"。
    """
    defn = get_objective(objective_id)
    goal = "maximize" if defn.direction == "maximize" else "minimize"
    return memory_manager.get_best_trial(defn.trial_objective_key, goal)


def assert_campaign_matches_role(
    objective_name: str,
    goal: str,
    role: str = "training",
) -> Dict[str, Any]:
    """校验 campaign 的目标键/方向与注册表绑定的角色定义一致（G7 口径漂移守卫）。

    用途：在闭环 Step3 取历史最优前调用——若 campaign 的 `objective.target`/`goal`
    与注册表 `role_bindings[role]` 指向的定义(trial_objective_key/direction)不符,
    立即抛 ValueError,从根上杜绝"优化一个目标键、用另一个键名/方向宣布成功"。

    Returns: 成功时返回 {objective_definition_id, objective_definition_sha256,
             objective_role, trial_objective_key, direction}(可写入 run manifest)。
    Raises:  ValueError —— 键名或方向漂移。
    """
    defn = objective_for_role(role)
    goal_norm = (goal or "").strip().lower()
    dir_norm = (defn.direction or "").strip().lower()
    problems: List[str] = []
    if objective_name != defn.trial_objective_key:
        problems.append(
            f"campaign objective.target='{objective_name}' != registry[{role}]"
            f".trial_objective_key='{defn.trial_objective_key}'")
    if goal_norm and goal_norm != dir_norm:
        problems.append(
            f"campaign objective.goal='{goal_norm}' != registry[{role}].direction='{dir_norm}'")
    if problems:
        raise ValueError(
            "目标口径漂移(G7)：campaign 与目标注册表不一致 —— " + "；".join(problems)
            + f"。请对齐 configs/objective_registry.yaml 的 role_bindings.{role}。")
    stamp = defn.to_stamp()
    stamp.update({"trial_objective_key": defn.trial_objective_key, "direction": defn.direction})
    return stamp


def assert_trial_objective_consistency(
    trials: List[Dict[str, Any]],
    expected_objective_id: str,
    require_stamp: bool = False,
) -> Dict[str, Any]:
    """校验历史 trial 的目标定义盖章与期望一致。

    - require_stamp=False（默认，兼容旧库）：旧 trial 无盖章时记 'backfilled',不报错。
    - require_stamp=True：任何缺章/串章直接抛 ValueError（新库严格模式）。

    Returns: {n_trials, n_stamped, n_backfilled, n_mismatch, mismatches}
    """
    defn = get_objective(expected_objective_id)
    expected_sha = defn.sha256
    n_stamped = n_backfilled = n_mismatch = 0
    mismatches: List[Dict[str, Any]] = []
    for t in trials:
        meta = t.get("metadata") or {}
        sha = meta.get("objective_definition_sha256")
        oid = meta.get("objective_definition_id")
        if sha is None and oid is None:
            n_backfilled += 1
            if require_stamp:
                raise ValueError(
                    f"trial {t.get('trial_id')} missing objective_definition stamp "
                    f"(strict mode); expected {expected_objective_id}")
            continue
        n_stamped += 1
        if oid != expected_objective_id or (sha is not None and sha != expected_sha):
            n_mismatch += 1
            mismatches.append({
                "trial_id": t.get("trial_id"),
                "found_id": oid, "found_sha": sha,
                "expected_id": expected_objective_id, "expected_sha": expected_sha,
            })
    if n_mismatch and require_stamp:
        raise ValueError(f"objective definition mismatch on {n_mismatch} trials: {mismatches}")
    return {
        "n_trials": len(trials),
        "n_stamped": n_stamped,
        "n_backfilled": n_backfilled,
        "n_mismatch": n_mismatch,
        "mismatches": mismatches,
        "expected_objective_id": expected_objective_id,
        "expected_sha256": expected_sha,
    }


if __name__ == "__main__":
    reg = load_registry()
    print("Objective registry (configs/objective_registry.yaml):")
    for oid, d in reg.items():
        print(f"  [{d.role:18s}] {oid}")
        print(f"      key={d.trial_objective_key}  dir={d.direction}  sha={d.sha256[:12]}…")
        print(f"      expr= {d.expression}")
    print("\nrole bindings:")
    raw = _load_yaml()
    for role, oid in (raw.get("role_bindings") or {}).items():
        print(f"  {role:22s} -> {oid}")
