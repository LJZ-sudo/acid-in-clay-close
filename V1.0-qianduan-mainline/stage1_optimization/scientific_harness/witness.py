# -*- coding: utf-8 -*-
"""物理见证与三类 ID（WP1-c / SciTX 2.0）。

GPT-3 指出:当前 C_P 主要来自软件 success/OK,那只是 `command_status`,不是 `physical_effect`。
本模块把"动作是否发生"升级为**由多个见证综合推断的物理信念态**,并严格区分三类 ID:
  - ExecutionAttempt：一次软件尝试(命令下发);可有多次(超时后是**新尝试**,不是幂等重放)。
  - PhysicalEffect ：被推断/确认的真实物理作用(confirmed/not_occurred/possible/unknown)。
  - evidence_id    ：最终提交的证据(在 admission/transaction 层产生)。

**核心诚实约束**:`confirmed` 必须至少有一个**独立于仪器软件**的见证(原始文件哈希/温控轨迹/
人工确认/第二传感器);仅凭软件 ACK 最多只能 `possible`。这正是 GPT-3 要求的"独立物理见证"。
纯软件、零硬件依赖;见证既可来自真机适配层,也可来自 fault_injection 模拟器。
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .commits import PhysicalCommit


class WitnessKind:
    SOFTWARE_ACK = "SOFTWARE_ACK"        # 仪器软件确认(非独立)
    INSTRUMENT_STATE = "INSTRUMENT_STATE"  # 仪器状态查询(非独立,来自同一软件)
    RAW_FILE = "RAW_FILE"                # 原始数据文件存在 + 哈希(独立)
    TEMP_TRACE = "TEMP_TRACE"            # 温控轨迹(独立:独立温控通道)
    SAMPLE_ID = "SAMPLE_ID"              # 样品身份核对(独立:条码/制备记录)
    HUMAN_CONFIRM = "HUMAN_CONFIRM"      # 人工确认(独立)
    SECOND_SENSOR = "SECOND_SENSOR"      # 第二传感器(独立)

    # 哪些见证算"独立于仪器控制软件"
    INDEPENDENT = frozenset({RAW_FILE, TEMP_TRACE, SAMPLE_ID, HUMAN_CONFIRM, SECOND_SENSOR})


@dataclass
class Witness:
    kind: str
    present: bool
    detail: Optional[str] = None

    @property
    def independent(self) -> bool:
        return self.kind in WitnessKind.INDEPENDENT


@dataclass
class ExecutionAttempt:
    command_id: str
    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_hash: Optional[str] = None
    sent_at: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat())
    ack_received: bool = False
    timed_out: bool = False

    @staticmethod
    def make(command_id: str, command: str = "", ack_received: bool = False,
             timed_out: bool = False) -> "ExecutionAttempt":
        return ExecutionAttempt(
            command_id=command_id,
            command_hash=hashlib.sha256(command.encode("utf-8")).hexdigest() if command else None,
            ack_received=ack_received, timed_out=timed_out)


@dataclass
class PhysicalEffect:
    command_id: str
    occurred: str                 # confirmed | not_occurred | possible | unknown
    probability: float
    physical_effect_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    witness_kinds: List[str] = field(default_factory=list)
    independent_witness_count: int = 0
    reasons: List[str] = field(default_factory=list)

    def to_commit_status(self) -> str:
        """映射到既有 PhysicalCommit 状态(供 commit_controller/记录复用)。"""
        return {
            "confirmed": PhysicalCommit.EFFECT_OBSERVED,
            "not_occurred": PhysicalCommit.FAILED,
            "possible": PhysicalCommit.PARTIAL,
            "unknown": PhysicalCommit.UNKNOWN,
        }[self.occurred]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "physical_effect_id": self.physical_effect_id,
            "occurred": self.occurred,
            "probability": self.probability,
            "witness_kinds": list(self.witness_kinds),
            "independent_witness_count": self.independent_witness_count,
            "reasons": list(self.reasons),
        }


def infer_physical_effect(
    command_id: str,
    witnesses: List[Witness],
    expected_sample_id: Optional[str] = None,
    instrument_state: Optional[str] = None,
) -> PhysicalEffect:
    """由多见证综合推断物理作用是否发生。

    判定(诚实优先,宁可 unknown 不可假阳):
      - 样品身份见证存在且不匹配 → unknown(决不当作发生)。
      - 原始文件存在(独立见证)+ 仪器状态 DONE → confirmed(即使 ACK 丢失,= 重建)。
      - 仪器 IDLE 且无原始文件 → not_occurred。
      - 有独立见证但状态 RUNNING/不全 → possible。
      - 仅软件 ACK / 仅状态查询(无任何独立见证)→ 最多 possible(软件成功≠物理发生)。
      - 其余 → unknown。
    """
    present = {w.kind for w in witnesses if w.present}
    indep = [w for w in witnesses if w.present and w.independent]
    n_indep = len(indep)
    reasons: List[str] = [f"witnesses={sorted(present)}", f"independent={n_indep}"]

    # 样品错配 → 不确定(最高优先,安全)
    sample_w = next((w for w in witnesses if w.kind == WitnessKind.SAMPLE_ID), None)
    if sample_w is not None and expected_sample_id is not None:
        if sample_w.detail is not None and sample_w.detail != expected_sample_id:
            reasons.append("SAMPLE_ID_MISMATCH")
            return PhysicalEffect(command_id, "unknown", 0.3, witness_kinds=sorted(present),
                                  independent_witness_count=n_indep, reasons=reasons)

    file_ok = WitnessKind.RAW_FILE in present
    state = instrument_state
    state_w = next((w for w in witnesses if w.kind == WitnessKind.INSTRUMENT_STATE and w.present), None)
    if state is None and state_w is not None:
        state = state_w.detail

    # 无任何独立见证:软件成功不足以判"发生"
    if n_indep == 0:
        if WitnessKind.SOFTWARE_ACK in present or WitnessKind.INSTRUMENT_STATE in present:
            reasons.append("ONLY_SOFTWARE_WITNESS_AT_MOST_POSSIBLE")
            return PhysicalEffect(command_id, "possible", 0.5, witness_kinds=sorted(present),
                                  independent_witness_count=0, reasons=reasons)
        reasons.append("NO_WITNESS")
        return PhysicalEffect(command_id, "unknown", 0.1, witness_kinds=sorted(present),
                              independent_witness_count=0, reasons=reasons)

    # 有独立见证
    if file_ok and state == "DONE":
        reasons.append("INDEPENDENT_FILE_AND_STATE_DONE")
        return PhysicalEffect(command_id, "confirmed", 0.97, witness_kinds=sorted(present),
                              independent_witness_count=n_indep, reasons=reasons)
    if (not file_ok) and state == "IDLE":
        reasons.append("IDLE_NO_FILE")
        return PhysicalEffect(command_id, "not_occurred", 0.95, witness_kinds=sorted(present),
                              independent_witness_count=n_indep, reasons=reasons)
    if file_ok and state == "RUNNING":
        reasons.append("FILE_BUT_RUNNING_PARTIAL")
        return PhysicalEffect(command_id, "possible", 0.6, witness_kinds=sorted(present),
                              independent_witness_count=n_indep, reasons=reasons)
    if file_ok:
        # 文件在但状态不明 → 多个独立见证可升 confirmed,否则 possible
        if n_indep >= 2:
            reasons.append("MULTI_INDEPENDENT_FILE")
            return PhysicalEffect(command_id, "confirmed", 0.9, witness_kinds=sorted(present),
                                  independent_witness_count=n_indep, reasons=reasons)
        reasons.append("SINGLE_INDEPENDENT_FILE_ONLY")
        return PhysicalEffect(command_id, "possible", 0.7, witness_kinds=sorted(present),
                              independent_witness_count=n_indep, reasons=reasons)
    reasons.append("INDETERMINATE")
    return PhysicalEffect(command_id, "unknown", 0.3, witness_kinds=sorted(present),
                          independent_witness_count=n_indep, reasons=reasons)


def witnesses_from_instrument(instrument: Any, command_id: str, ack_received: bool) -> List[Witness]:
    """从既有仪器接口(query_output_file/query_instrument_state/query_sample_id)构造见证列表。

    与 fault_injection.InstrumentSimulator / 真机适配层兼容;原始文件视为独立见证。
    """
    ws: List[Witness] = [Witness(WitnessKind.SOFTWARE_ACK, present=bool(ack_received))]
    try:
        ws.append(Witness(WitnessKind.RAW_FILE, present=bool(instrument.query_output_file(command_id))))
    except Exception:
        ws.append(Witness(WitnessKind.RAW_FILE, present=False))
    try:
        ws.append(Witness(WitnessKind.INSTRUMENT_STATE, present=True,
                          detail=str(instrument.query_instrument_state())))
    except Exception:
        pass
    try:
        ws.append(Witness(WitnessKind.SAMPLE_ID, present=True, detail=str(instrument.query_sample_id())))
    except Exception:
        pass
    # 独立温控见证(TEMP_TRACE):仅当仪器提供 query_temp_trace 时加入(在线适配层有,
    # 离线 ReplayInstrument 没有 → 向后兼容跳过)。稳定到设定点=独立于仪器软件的物理见证。
    query_tt = getattr(instrument, "query_temp_trace", None)
    if callable(query_tt):
        try:
            tt = query_tt()
            if tt is not None:
                ws.append(Witness(WitnessKind.TEMP_TRACE, present=bool(tt.get("settled")),
                                  detail=f"setpoint={tt.get('setpoint_C')},actual={tt.get('actual_C')}"))
        except Exception:
            pass
    return ws
