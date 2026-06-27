"""反事实证明携带科学记忆(M5-B / B2)。

SQLite 证据超图 + 四值逻辑(UNKNOWN/SUPPORTED/REFUTED/CONTESTED)+ 最小支持集 +
失效传播引擎。与 memory_manager(trial DB/去重/SHA 链)互补 —— 这是**权威主张图谱层**,
不替换 trial DB。

核心不变量:
  - 证据失效 → 删依赖该证据的支持/反驳路径 → 下游主张按四值逻辑自动重算 → 旧决策标 AFFECTED;
  - 独立支持链存活:仍有全有效支持集的主张保持 SUPPORTED;
  - 失效证据绝不再被"有效证据检索"返回(无泄漏)。
"""
from .claim_graph import ClaimGraph, ClaimStatus, NodeType, EdgeType  # noqa: F401
from .invalidation_engine import InvalidationEngine, InvalidationReport  # noqa: F401
# WP3:版本快照/写门、独立根去重、失效→BO 重建、压缩证书
from .snapshots import (  # noqa: F401
    GraphSnapshot, WriteGateResult, take_snapshot, validate_write,
    ACCEPT, REBASE_REQUIRED, REJECTED,
)
from .root_dedup import (  # noqa: F401
    EvidenceSource, RootKind, normalize_root, count_independent_roots, dedup_sources,
)
from .bo_rebuilder import (  # noqa: F401
    Observation, CommittedObservationView, DecisionImpactReport,
    build_committed_view, rebuild_after_invalidation, apply_revocation_impact,
)
from .compression import (  # noqa: F401
    MemoryState, CompressionCertificate, compress_and_verify,
)
from .history_bridge import (  # noqa: F401
    materialize_committed_view, view_to_training_arrays, load_trials, evidence_id_for_trial,
)
from .bo_retrain_bridge import CommittedMemoryView, rebuild_and_resuggest  # noqa: F401
# ESAS-OS 2.0（§10.2）：R²-Memory 角色隔离/可撤销/多轮记忆（旁挂，不替换证据图）
from .agent_memory import (  # noqa: F401
    AgentMemory, MemoryItem, RoundState, Role, Use, UsageViolation,
)
from .agent_memory import bench as agent_memory_bench  # noqa: F401
