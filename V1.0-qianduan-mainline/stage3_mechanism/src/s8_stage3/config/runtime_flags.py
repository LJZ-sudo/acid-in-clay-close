"""运行时开关，从环境变量读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key, "true" if default else "false").lower()
    return v in ("1", "true", "yes", "on")


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class RuntimeFlags:
    skip_web: bool = False
    debug_snapshots: bool = False
    no_cache: bool = False
    until_step: str = ""        # 空字符串=跑到底
    max_samples: int = 0        # 0=不限制
    abort_on_step_failure: bool = True

    @classmethod
    def from_env(cls) -> "RuntimeFlags":
        return cls(
            skip_web=_env_bool("STAGE3_SKIP_WEB", False),
            debug_snapshots=_env_bool("STAGE3_DEBUG_SNAPSHOTS", False),
            no_cache=_env_bool("STAGE3_NO_CACHE", False),
            until_step=os.getenv("STAGE3_UNTIL_STEP", ""),
            max_samples=_env_int("STAGE3_MAX_SAMPLES", 0),
            abort_on_step_failure=_env_bool("STAGE3_ABORT_ON_STEP_FAILURE", True),
        )

    def is_mock(self) -> bool:
        return os.getenv("STAGE3_LLM_MODE", "mock") == "mock"
