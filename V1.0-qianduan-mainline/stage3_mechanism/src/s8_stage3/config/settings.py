"""Stage3 全局配置，从环境变量读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=False)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key, "true" if default else "false").lower()
    return v in ("1", "true", "yes", "on")


@dataclass
class Stage3Settings:
    # LLM endpoint
    api_key: str = field(default_factory=lambda: _env("STAGE3_API_KEY"))
    api_base_url: str = field(default_factory=lambda: _env("STAGE3_API_BASE_URL", "https://api.openai.com"))
    timeout_seconds: int = field(default_factory=lambda: _env_int("STAGE3_TIMEOUT_SECONDS", 180))
    max_retries: int = field(default_factory=lambda: _env_int("STAGE3_MAX_RETRIES", 3))
    verify_ssl: bool = field(default_factory=lambda: _env_bool("STAGE3_VERIFY_SSL", True))

    # Model names (tier)
    model_cheap: str = field(default_factory=lambda: _env("STAGE3_MODEL_CHEAP", "gpt-4o-mini"))
    model_standard: str = field(default_factory=lambda: _env("STAGE3_MODEL_STANDARD", "gpt-4o"))
    model_premium: str = field(default_factory=lambda: _env("STAGE3_MODEL_PREMIUM", "gpt-4o"))

    # Run mode
    run_mode: str = field(default_factory=lambda: _env("STAGE3_RUN_MODE", "mock"))
    llm_mode: str = field(default_factory=lambda: _env("STAGE3_LLM_MODE", "mock"))
    literature_mode: str = field(default_factory=lambda: _env("STAGE3_LITERATURE_MODE", "mock"))
    model_tier: str = field(default_factory=lambda: _env("STAGE3_MODEL_TIER", "cheap"))
    # 是否尝试 Structured Outputs (json_schema+strict)
    # 设为 false 可避免在不支持该功能的代理平台（如 Polo）产生无谓的 400 错误
    use_structured_outputs: bool = field(default_factory=lambda: _env_bool("STAGE3_USE_STRUCTURED_OUTPUTS", True))

    # Literature providers
    openalex_mailto: str = field(default_factory=lambda: _env("STAGE3_OPENALEX_MAILTO", ""))
    semantic_scholar_api_key: str = field(default_factory=lambda: _env("STAGE3_SEMANTIC_SCHOLAR_API_KEY", ""))

    # Budget guardrails
    max_llm_calls_per_run: int = field(default_factory=lambda: _env_int("STAGE3_MAX_LLM_CALLS_PER_RUN", 100))
    max_literature_queries_per_step: int = field(default_factory=lambda: _env_int("STAGE3_MAX_LITERATURE_QUERIES_PER_STEP", 10))
    max_papers_per_query: int = field(default_factory=lambda: _env_int("STAGE3_MAX_PAPERS_PER_QUERY", 20))
    max_total_papers_per_step: int = field(default_factory=lambda: _env_int("STAGE3_MAX_TOTAL_PAPERS_PER_STEP", 50))
    abort_on_budget_exceeded: bool = field(default_factory=lambda: _env_bool("STAGE3_ABORT_ON_BUDGET_EXCEEDED", True))
    s08_claim_batch_size: int = field(default_factory=lambda: _env_int("STAGE3_S08_CLAIM_BATCH_SIZE", 4))
    s08_min_claim_relevance: float = field(default_factory=lambda: _env_float("STAGE3_S08_MIN_CLAIM_RELEVANCE", 0.3))
    s09_deterministic_from_d4: bool = field(default_factory=lambda: _env_bool("STAGE3_S09_DETERMINISTIC_FROM_D4", True))
    # Tier3 (issue 4): opt-in evidence-based S09 candidate generation. Default
    # False keeps the frozen deterministic_from_d4 path. Exposing it as an
    # explicit, auditable switch (env STAGE3_S09_EVIDENCE_BASED_GENERATION) does
    # not change default behaviour; the S09 branch already reads this attribute.
    s09_evidence_based_generation: bool = field(
        default_factory=lambda: _env_bool("STAGE3_S09_EVIDENCE_BASED_GENERATION", False)
    )
    s10_deterministic_from_audit: bool = field(default_factory=lambda: _env_bool("STAGE3_S10_DETERMINISTIC_FROM_AUDIT", True))
    s11_deterministic_report: bool = field(default_factory=lambda: _env_bool("STAGE3_S11_DETERMINISTIC_REPORT", True))

    # LLM reproducibility
    llm_temperature: float = field(default_factory=lambda: _env_float("STAGE3_LLM_TEMPERATURE", 0.0))
    llm_seed: int = field(default_factory=lambda: _env_int("STAGE3_LLM_SEED", 0))
    record_prompt_hashes: bool = field(default_factory=lambda: _env_bool("STAGE3_RECORD_PROMPT_HASHES", True))

    # Sampling (for low-cost smoke runs)
    max_samples: Optional[int] = field(default_factory=lambda: _env_int("STAGE3_MAX_SAMPLES", 0) or None)
    max_composition_nodes: Optional[int] = field(
        default_factory=lambda: _env_int("STAGE3_MAX_COMPOSITION_NODES", 0) or None
    )

    # Cache
    enable_cache: bool = field(default_factory=lambda: _env_bool("STAGE3_ENABLE_CACHE", True))
    llm_enable_smoke: bool = field(default_factory=lambda: _env_bool("STAGE3_LLM_ENABLE_SMOKE", False))

    # P-Stage3-C: discovery / source-term audit / final audit
    discovery_mode: str = field(
        default_factory=lambda: _env("STAGE3_DISCOVERY_MODE", "broad_literature_pool_selection")
    )
    final_audit: bool = field(default_factory=lambda: _env_bool("STAGE3_FINAL_AUDIT", False))
    candidate_term_audit: bool = field(
        default_factory=lambda: _env_bool("STAGE3_CANDIDATE_TERM_AUDIT", True)
    )

    # P-Stage3-H/I: prospective registry top-N 与强制重置
    prospective_top_n: int = field(
        default_factory=lambda: _env_int("STAGE3_PROSPECTIVE_TOP_N", 5)
    )
    prospective_force_reset: bool = field(
        default_factory=lambda: _env_bool("STAGE3_PROSPECTIVE_FORCE_RESET", False)
    )

    def __post_init__(self):
        # final_audit=True 强制关闭 cache，避免复用含目标候选词的旧 LLM 响应。
        if self.final_audit and self.enable_cache:
            self.enable_cache = False

    @property
    def is_mock(self) -> bool:
        return self.llm_mode == "mock"

    @property
    def outputs_dir(self) -> Path:
        override = _env("STAGE3_OUTPUT_DIR", "")
        if override:
            return Path(override)
        return Path(__file__).parent.parent.parent.parent / "outputs" / "stage3"

    @property
    def cache_dir(self) -> Path:
        override = _env("STAGE3_CACHE_DIR", "")
        if override:
            return Path(override)
        return Path(__file__).parent.parent.parent.parent / "data" / "cache" / "current"

    @property
    def logs_dir(self) -> Path:
        return Path(__file__).parent.parent.parent.parent / "logs"

    @property
    def prompts_dir(self) -> Path:
        return Path(__file__).parent.parent / "prompts"

    @property
    def literature_workspace_dir(self) -> Path:
        return Path(__file__).parent.parent.parent.parent / "literature_workspace"

    @property
    def parsed_sample_ids(self) -> list[str]:
        raw = _env("STAGE3_SAMPLE_IDS", "")
        return [s.strip() for s in raw.split(",") if s.strip()] if raw else []


def load_settings() -> Stage3Settings:
    return Stage3Settings()
