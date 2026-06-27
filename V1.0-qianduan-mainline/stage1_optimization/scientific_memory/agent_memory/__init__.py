# -*- coding: utf-8 -*-
"""R²-Memory — Role-isolated & Retractable scientific memory（ESAS-OS 2.0 / §10.2）。

与 SQLite 证据图(`claim_graph`)/`history_bridge` **互补、不替换**:证据图管"主张四值 + 失效传播",
本层管"角色隔离投影 / 用途守卫(来源域)/ 多轮 RoundState / 决策保持性压缩"。
默认旁挂只读,不夺权(对齐 §10.7:不改 trial DB/σ)。
"""
from .models import (  # noqa: F401
    MemoryItem, RoundState, WriteDecision, Role, Use,
    PROPOSED, ACTIVE, CONTESTED, REJECTED, INVALID,
    ACCEPT, REBASE_REQUIRED, DENY,
)
from .store import AgentMemory, UsageViolation  # noqa: F401
from . import bench  # noqa: F401
