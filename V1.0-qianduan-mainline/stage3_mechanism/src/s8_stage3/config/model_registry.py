"""模型注册中心：管理模型别名和 step 级路由。"""

from __future__ import annotations

import os
from enum import Enum
from typing import Optional


class ModelTier(str, Enum):
    CHEAP = "cheap"
    STANDARD = "standard"
    PREMIUM = "premium"


# step -> 默认使用的 tier
#
# 分级原则:
#   PREMIUM  = 主推理链 (假说 / 仲裁 / 候选生成 / 排名 / 报告)
#   STANDARD = 中等推理 (描述符抽取)
#   CHEAP    = 机械性文本抽取 (文献摘要 / paper card 抽取)
#
# 若 .env 里设了 STAGE3_MODEL_TIER (非空/有效值), 会整体覆盖本表; 想用本表请把该 env 留空.
# paper_card_<id> 是动态 step 名, 不在此 map 中; 经 dict.get 回退到 ModelTier.CHEAP.
STEP_TIER_MAP: dict[str, ModelTier] = {
    "s03_evidence_builder": ModelTier.CHEAP,           # S03 实际不调用 LLM, 此项仅为 fallback
    "s04_hypothesis_generator": ModelTier.PREMIUM,     # 主推理: 生成竞争假说
    # NOTE: 代码里 gateway.chat_json(step=...) 实际传入的是 "s05_literature_mechanism"
    # (见 agents/s05_literature_scout_mechanism.py L58, L155). 保留旧 key 作为兼容回退.
    "s05_literature_scout_mechanism": ModelTier.CHEAP, # legacy alias (实际调用见下方)
    "s05_literature_mechanism": ModelTier.CHEAP,       # 实际调用 step 名: 文献摘要(机理)
    "s05_summarize": ModelTier.CHEAP,                  # legacy alias
    "s06_mechanism_arbiter": ModelTier.PREMIUM,        # 主推理: 机理仲裁
    "s06b_design_principle_extractor": ModelTier.PREMIUM, # 主推理: 从仲裁结论抽取可迁移设计原则
    "s07_descriptor_extractor": ModelTier.STANDARD,    # 中等推理: 描述符抽取
    "s08_literature_scout_materials": ModelTier.CHEAP, # legacy alias
    "s08_summarize": ModelTier.CHEAP,                  # legacy alias
    # NOTE: 代码里 gateway.chat_json(step=...) 实际传入的是 "s08_summarize_batch"
    # (见 agents/s08_literature_scout_materials.py L269).
    "s08_summarize_batch": ModelTier.CHEAP,            # 实际调用 step 名: 文献摘要(材料)
    # 下面三个 step 默认走 deterministic 分支 (s09: deterministic_from_d4 命中时直出;
    # s10: settings.deterministic=True 时走 _build_deterministic_ranking;
    # s11: settings.s11_deterministic_report=True 时走 _fallback_report).
    # 仅当 deterministic 路径未命中 / 被显式关闭时, 才会落到 LLM, 此时按 PREMIUM 路由.
    # 当前默认 .env 配置下, 这三个 step 在真跑里**不会**调用 LLM (见近期 llm_cost_summary).
    "s09_candidate_family_generator": ModelTier.PREMIUM, # LLM fallback: 候选家族/实例
    "s10_instance_ranker": ModelTier.PREMIUM,          # LLM fallback: 排名
    "s11_report_compiler": ModelTier.PREMIUM,          # LLM fallback: 报告生成
}


_VALID_TIER_VALUES = {t.value for t in ModelTier}


class ModelRegistry:
    def __init__(self, cheap: str, standard: str, premium: str):
        self._map = {
            ModelTier.CHEAP: cheap,
            ModelTier.STANDARD: standard,
            ModelTier.PREMIUM: premium,
        }

    def resolve_for_step(self, step_name: str, override_tier: Optional[str] = None) -> str:
        # 优先级: 显式 override_tier > STAGE3_MODEL_TIER 全局环境变量 > STEP_TIER_MAP 默认
        if override_tier:
            tier = ModelTier(override_tier)
        else:
            env_tier = os.environ.get("STAGE3_MODEL_TIER", "").strip().lower()
            if env_tier in _VALID_TIER_VALUES:
                tier = ModelTier(env_tier)
            else:
                tier = STEP_TIER_MAP.get(step_name, ModelTier.CHEAP)
        return self.resolve(tier)

    def resolve(self, tier: ModelTier | str) -> str:
        if isinstance(tier, str):
            tier = ModelTier(tier)
        return self._map.get(tier, self._map[ModelTier.CHEAP])

    def list_configured(self) -> dict[str, str]:
        return {t.value: m for t, m in self._map.items()}
