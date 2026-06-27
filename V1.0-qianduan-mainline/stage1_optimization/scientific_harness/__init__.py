"""三重提交物理信念态 Harness(M5-A / B1)。

把"测量完成→写库"升级为**物理提交 C_P → 计量提交 C_M → 认知提交 C_E**三道不可跳过的闸:
  - C_P:动作究竟是否发生(已发生/未发生/部分/未知/重建);超时先核对、**禁盲目重试**;
  - C_M:测量是否满足计量资格(复用 M1-4 evidence_admission 的 QA/KK/Rb);
  - C_E:仅当 C_P∧C_M∧scope 明确才允许进入 BO/主张/长期记忆。
核心不变量:`¬C_E ⇒ 不入 {BO, 主张, 长期记忆}`;`timeout(a) ⇒ ¬retry(a) U reconciled(a)`。
与冻结闭环互补:shadow 旁路记录,不夺仪器控制权(见 demo_a)。
"""
from .commits import (  # noqa: F401
    PhysicalCommit, MetrologicalCommit, EpistemicCommit,
)
from .event_store import EventStore  # noqa: F401
from .commit_controller import CommitController, CommitResult  # noqa: F401
# SciTX 2.0（WP1）：按用途/主张分级准入、多见证物理作用、证据事务编排
from .admission import (  # noqa: F401
    IntendedUse, UseAdmission, ClaimAdmission,
    assess_use, assess_all_uses, assess_claim_admission, USE_MAX_CLAIM_LEVEL,
)
from .witness import (  # noqa: F401
    Witness, WitnessKind, ExecutionAttempt, PhysicalEffect,
    infer_physical_effect, witnesses_from_instrument,
)
from .transaction import EvidenceTransaction, ClaimRequest, TransactionResult  # noqa: F401
# ESAS-OS 2.0（§10.1）：测量提交路径事务化（离线可测 helper）
from .measurement_txn import (  # noqa: F401
    ReplayInstrument, build_measurement_signals_from_bundle, submit_measurement_offline,
)
# WP4 Cutover：自主硬件命令的唯一受控入口
from .action_gate import (  # noqa: F401
    ActionGate, ActionProposal, GateDecision, resolve_mode,
    SHADOW, CANARY, ENFORCE,
)
