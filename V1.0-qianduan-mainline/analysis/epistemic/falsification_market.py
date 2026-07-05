# -*- coding: utf-8 -*-
"""Gap3 —— 多角色 LLM 证伪市场(押注预测合同)。

把 GPT「证伪市场」从"只有评分/信誉数学+选择器"补成**多角色 LLM 押注合同**:
  - Proposer(LLM)   : 对真实 σ(T) 提出机制假设 H,给出可证伪的押注合同
                       C_H={claim_model, 预测分布 p(Y|H,a), 适用域, 证伪条件, 押注置信度 s_H}。
  - Falsifier(LLM)  : 提出"最便宜的致命实验"(下一个测温点),意图证伪 Proposer。
  - Auditor(LLM)    : 审核该实验是否 admissible(在域内、物理合理、非同义反复)。
  - Referee(确定性) : 在**真实数据**上"执行"实验(揭示该温度真实 σ),按严格适当评分
                       (EpistemicAccount,Brier/log-loss)结算押注 → 更新资本/信誉。
                       过度自信且被证伪者 → 资本下跌(机制设计核心)。

LLM 角色是**真实 OpenRouter 调用**;结算用确定性真实数据 replay + 适当评分(不造数据)。
无 key/断网 → 上层脚本 SKIP,不谎报。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from . import models as M
from . import active_design as AD


# --------------------------------------------------------------------------- #
# 轻量 OpenRouter 客户端(与项目 stage1/.env 同源 key)
# --------------------------------------------------------------------------- #
def load_env(key: str, default: Optional[str] = None) -> Optional[str]:
    if os.environ.get(key):
        return os.environ[key]
    # 顺着常见 .env 找
    here = Path(__file__).resolve()
    for env in (here.parents[2] / "stage1_optimization" / ".env",
                here.parents[2] / "stage3_mechanism" / ".env"):
        if env.exists():
            for raw in env.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")
    return default


class LLMClient:
    """最小 chat-json 客户端(OpenRouter / OpenAI 兼容)。"""

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key or load_env("LLM_API_KEY")
        self.base_url = base_url or load_env("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = model or load_env("LLM_MODEL", "openai/gpt-5.4")
        self._client = None
        self.calls: List[Dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=90)
        return self._client

    def chat_json(self, system: str, user: str, role: str) -> Dict[str, Any]:
        client = self._get()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        self.calls.append({
            "role": role, "model": self.model,
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        })
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]+\}", raw)
            return json.loads(m.group()) if m else {"_raw": raw}


# --------------------------------------------------------------------------- #
# 押注预测合同
# --------------------------------------------------------------------------- #
MODEL_FAMILIES = ["arrhenius", "mott", "vtf", "segmented"]


@dataclass
class Contract:
    agent: str
    claim_model: str                 # 主张的机制族
    staked_confidence: float         # s_H ∈ (0,1):押在"我的预测会通过证伪检验"
    domain: Dict[str, Any]           # 适用域(温区等)
    falsification_conditions: str    # 证伪条件(自然语言)
    rationale: str = ""
    source: str = "llm"              # llm / strawman


@dataclass
class Settlement:
    round_idx: int
    test_T_K: float
    predicted_y: float
    predicted_sigma: float
    observed_y: float
    z_score: float
    survived: bool                   # 预测是否通过(|z|<=k)
    outcome: int                     # 1=预测正确,0=被证伪
    auditor_admissible: bool
    falsifier_T_K: float
    fvpc_best_T_K: float             # active_design 选择器的最优点(交叉核对)


# --------------------------------------------------------------------------- #
# LLM 角色
# --------------------------------------------------------------------------- #
def _data_summary(T, y) -> str:
    rows = "\n".join(f"  T={tk:.1f}K ({tk-273.15:.1f}C)  lnσ={yy:.3f}" for tk, yy in zip(T, y))
    return (f"质子导体黏土(attapulgite/ATP)变温电导真实数据(n={len(T)},lnσ=ln(S/cm)):\n{rows}\n"
            f"候选机制族:{MODEL_FAMILIES}(arrhenius=单活化能直线;mott=变程跳跃 T^-1/4;"
            f"vtf=玻璃态;segmented=分段/相变折线)。")


def proposer_propose(client: LLMClient, T_seed, y_seed) -> Contract:
    sysmsg = ("你是机制提案者(Proposer)。基于给定真实变温电导数据,提出**最可能**的传导机制族,"
              "并给出一份可证伪的押注合同。必须输出 JSON,字段:claim_model(从候选族选一),"
              "staked_confidence(0~1,你押注'后续致命实验不会证伪你'的置信度,过度自信会在结算中受罚),"
              "domain(适用温区{T_min_K,T_max_K}),falsification_conditions(什么观测会证伪你),rationale。")
    user = _data_summary(T_seed, y_seed) + "\n只看以上(暖端)数据提出假设。输出 JSON。"
    j = client.chat_json(sysmsg, user, role="proposer")
    cm = str(j.get("claim_model", "arrhenius")).lower().strip()
    if cm not in MODEL_FAMILIES:
        cm = next((f for f in MODEL_FAMILIES if f in cm), "arrhenius")
    sc = j.get("staked_confidence", 0.7)
    try:
        sc = float(sc)
    except (TypeError, ValueError):
        sc = 0.7
    sc = min(max(sc, 0.01), 0.99)
    return Contract(agent="LLM_Proposer", claim_model=cm, staked_confidence=sc,
                    domain=j.get("domain") or {}, rationale=str(j.get("rationale", ""))[:500],
                    falsification_conditions=str(j.get("falsification_conditions", ""))[:300],
                    source="llm")


def falsifier_choose(client: LLMClient, contract: Contract, candidate_T_K: List[float]) -> float:
    sysmsg = ("你是证伪者(Falsifier)。对手押注某机制族。请从候选温度里挑出**最可能证伪对手**的"
              "下一个测温点(不同机制族在该温度预测分歧最大处)。输出 JSON:{test_temp_K, why}。")
    user = (f"对手押注:claim_model={contract.claim_model},confidence={contract.staked_confidence}。\n"
            f"候选温度(K):{[round(t,1) for t in candidate_T_K]}\n"
            f"选一个最致命的 test_temp_K。输出 JSON。")
    j = client.chat_json(sysmsg, user, role="falsifier")
    try:
        t = float(j.get("test_temp_K"))
    except (TypeError, ValueError):
        t = candidate_T_K[len(candidate_T_K) // 2]
    return min(candidate_T_K, key=lambda c: abs(c - t))


def auditor_validate(client: LLMClient, contract: Contract, test_T_K: float,
                     domain_T_range) -> bool:
    sysmsg = ("你是实验审核员(Auditor)。判断该证伪实验是否 admissible:在合理温区、物理可行、"
              "且非同义反复(不是直接抄对手结论)。输出 JSON:{admissible: true/false, reason}。")
    user = (f"对手 claim={contract.claim_model};拟测温度={test_T_K:.1f}K;"
            f"数据温区≈{domain_T_range}。该实验是否 admissible?输出 JSON。")
    j = client.chat_json(sysmsg, user, role="auditor")
    return bool(j.get("admissible", True))


# --------------------------------------------------------------------------- #
# Referee(确定性):真实数据结算 + 适当评分
# --------------------------------------------------------------------------- #
def referee_settle(contract: Contract, T_seed, y_seed, test_T_K, observed_y,
                   *, k_sigma: float = 2.0) -> Dict[str, Any]:
    """用 seed(暖端)拟合 Proposer 主张的模型,外推到 test_T,与真实观测比。
    |z|<=k_sigma → 预测通过(outcome=1);否则被证伪(outcome=0)。"""
    specs = M.fit_all(np.asarray(T_seed, float), np.asarray(y_seed, float))
    spec = specs.get(contract.claim_model)
    sigma = M.measurement_noise_sd(specs)
    if spec is None or not spec.ok:
        return {"ok": False}
    pred = float(spec.predict(np.array([float(test_T_K)]))[0])
    z = (observed_y - pred) / sigma if sigma > 0 else float("inf")
    survived = abs(z) <= k_sigma
    return {"ok": True, "predicted_y": pred, "predicted_sigma": sigma,
            "z_score": float(z), "survived": bool(survived),
            "outcome": int(survived)}


# --------------------------------------------------------------------------- #
# 市场编排
# --------------------------------------------------------------------------- #
def run_market(T, y, *, client: Optional[LLMClient] = None,
               n_seed: int = 6, n_rounds: int = 4,
               include_strawman: bool = True) -> Dict[str, Any]:
    """跑多角色证伪市场。返回合同、逐轮结算、信誉/资本。

    - LLM_Proposer:真实 LLM 提案(若 client 可用)。
    - Strawman_Overconfident:确定性稻草人,押 arrhenius@0.97(真数据含相变→应被证伪、丢资本),
      用于对照演示"过度自信且错→资本下跌"。
    """
    from scientific_skills.dual_account import EpistemicAccount

    T = np.asarray(T, float); y = np.asarray(y, float)
    order = np.argsort(-T)  # 暖→冷
    T = T[order]; y = y[order]
    T_seed, y_seed = T[:n_seed], y[:n_seed]
    rest_idx = list(range(n_seed, len(T)))

    contracts: List[Contract] = []
    llm_used = False
    if client is not None and client.available:
        try:
            contracts.append(proposer_propose(client, T_seed, y_seed))
            llm_used = True
        except Exception as exc:
            contracts.append(Contract("LLM_Proposer_FAILED", "arrhenius", 0.7, {},
                                      f"llm_error:{exc}", source="llm_error"))
    if include_strawman:
        contracts.append(Contract("Strawman_Overconfident", "arrhenius", 0.97,
                                   {"T_min_K": float(T.min()), "T_max_K": float(T.max())},
                                   "总是押单一活化能直线且过度自信", source="strawman"))

    acct = EpistemicAccount(eta=0.6)
    settlements: Dict[str, List[Settlement]] = {c.agent: [] for c in contracts}
    domain_T_range = (round(float(T.min()), 1), round(float(T.max()), 1))

    for r in range(min(n_rounds, len(rest_idx))):
        if not rest_idx:
            break
        cand_T = [float(T[i]) for i in rest_idx]
        # 选择器(确定性 FVPC)给最优判别点,作交叉核对基线
        ch = AD.select_next_temperature(list(T_seed), list(y_seed), cand_T)
        fvpc_T = ch.next_T_K if ch else cand_T[0]
        tested_this_round = set()

        for c in contracts:
            # Falsifier + Auditor:仅对 LLM 合同发起真实 LLM 调用(稻草人用 FVPC 基线)
            if c.source == "llm" and client is not None and client.available:
                try:
                    f_T = falsifier_choose(client, c, cand_T)
                    admissible = auditor_validate(client, c, f_T, domain_T_range)
                except Exception:
                    f_T, admissible = fvpc_T, True
            else:
                f_T, admissible = fvpc_T, True

            # Referee 在真实数据上结算(揭示 f_T 最近的真实点)
            j = min(rest_idx, key=lambda i: abs(T[i] - f_T))
            tested_this_round.add(j)
            res = referee_settle(c, T_seed, y_seed, T[j], y[j])
            if not res.get("ok"):
                continue
            acct.record(c.agent, predicted_prob=c.staked_confidence, outcome=res["outcome"])
            settlements[c.agent].append(Settlement(
                round_idx=r, test_T_K=float(T[j]), predicted_y=res["predicted_y"],
                predicted_sigma=res["predicted_sigma"], observed_y=float(y[j]),
                z_score=res["z_score"],                 survived=res["survived"], outcome=res["outcome"],
                auditor_admissible=admissible, falsifier_T_K=float(f_T), fvpc_best_T_K=float(fvpc_T),
            ))
        # 已测点移出候选池 → 下一轮探索新温度(真正的序贯市场)
        for j in tested_this_round:
            if j in rest_idx:
                rest_idx.remove(j)

    summary = {
        "llm_used": llm_used,
        "llm_calls": (client.calls if client else []),
        "contracts": [c.__dict__ for c in contracts],
        "reputation": {c.agent: acct.reputation(c.agent) for c in contracts},
        "brier": {c.agent: acct.brier(c.agent) for c in contracts},
        "logloss": {c.agent: acct.logloss(c.agent) for c in contracts},
        "settlements": {a: [s.__dict__ for s in ss] for a, ss in settlements.items()},
        "seed_T_K": [float(t) for t in T_seed],
        "domain_T_range": domain_T_range,
    }
    return summary
