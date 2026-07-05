# -*- coding: utf-8 -*-
"""在线仪器见证 + 协议级故障注入（H2 / ESAS-OS 2.0 §10.1 的真机在线半）。

`measurement_txn.ReplayInstrument` 用**已落盘 bundle 的 file_hashes** 作离线见证——它把
`ack/state/file` 恒判成"已完成"(dispatch.ack=True、state=DONE),因此**无法**演示在线仪器层
的失败(ACK 丢失、仪器卡住、文件未写、样品错插、校准过期)。本模块补上真机在线见证:

  * `OnlineInstrumentWitness`:实现 `EvidenceTransaction` 需要的仪器接口
    (dispatch/query_output_file/query_instrument_state/query_sample_id + 新增
    `query_temp_trace`),见证全部来自**一次真实完成的在线测量步**:
      - RAW_FILE  :真实 EIS .txt **落盘文件的 sha256**(独立见证);
      - TEMP_TRACE:温控是否稳定到设定点(独立见证,仅在线可得,离线 replay 没有);
      - INSTRUMENT_STATE / SOFTWARE_ACK:仪器软件态(非独立);
      - SAMPLE_ID :样品身份核对(独立)。
  * **协议级故障注入**(驱动边界软件注入,**绝不触碰样品/温控物理安全**):
      - ACK_LOSS         :ACK 丢失(看似超时)→ 应"先核对见证、禁盲目重试",文件在则仍 confirmed;
      - INSTRUMENT_STUCK :仪器停在 RUNNING → 至多 possible → 不进 BO;
      - FILE_MISSING     :原始文件未写(state IDLE)→ not_occurred → 拒;
      - FILE_DELAY       :文件延迟(state RUNNING、暂查不到)→ unknown → 拒(不盲目当成功);
      - SAMPLE_SWAP      :在线样品条码与预期不符 → unknown → 拒;
      - CALIBRATION_EXPIRED:校准过期 → 计量不确定度判 UNKNOWN → U5 拒(物理发生但不可用于 BO)。

诚实边界:**物理破坏性**故障(电极短接/断路、真样品损伤)仍须 dummy cell/参考电路,不在旧样品上做;
本模块只做**协议/见证级**注入(改的是"仪器上报了什么",不改"物理上做了什么"),旧材料真机安全。
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .transaction import EvidenceTransaction, ClaimRequest, TransactionResult
from .admission import IntendedUse


class ProtocolFault:
    """协议/见证级故障类型(非物理破坏性)。"""
    ACK_LOSS = "ACK_LOSS"
    INSTRUMENT_STUCK = "INSTRUMENT_STUCK"
    FILE_MISSING = "FILE_MISSING"
    FILE_DELAY = "FILE_DELAY"
    SAMPLE_SWAP = "SAMPLE_SWAP"
    CALIBRATION_EXPIRED = "CALIBRATION_EXPIRED"
    ALL = frozenset({ACK_LOSS, INSTRUMENT_STUCK, FILE_MISSING, FILE_DELAY,
                     SAMPLE_SWAP, CALIBRATION_EXPIRED})


class _Dispatch:
    def __init__(self, ack_received: bool, timed_out: bool):
        self.ack_received = ack_received
        self.timed_out = timed_out


def _sha256_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:  # noqa: BLE001
        return None


class OnlineInstrumentWitness:
    """从一次真实完成的在线测量步构造仪器见证(可选协议级故障注入)。

    与 `witness.witnesses_from_instrument` 完全兼容:实现 dispatch / query_output_file /
    query_instrument_state / query_sample_id,并额外提供独立的 `query_temp_trace`。
    """

    def __init__(
        self,
        *,
        sample_id: Optional[str],
        output_file: Optional[str],
        chi_success: bool = True,
        chamber_actual_C: Optional[float] = None,
        setpoint_C: Optional[float] = None,
        settle_tol_C: float = 1.5,
        protocol_fault: Optional[str] = None,
    ):
        self._sample_id = sample_id
        self._chi_success = bool(chi_success)
        self._chamber_actual_C = chamber_actual_C
        self._setpoint_C = setpoint_C
        self._settle_tol_C = float(settle_tol_C)
        self._fault = protocol_fault if protocol_fault in ProtocolFault.ALL else None
        # 真实文件见证:文件存在则算 sha256(独立 RAW_FILE 见证)。
        self._path = Path(output_file) if output_file else None
        self._file_hash = (
            _sha256_file(self._path)
            if (self._path is not None and self._path.exists()) else None)

    # --- EvidenceTransaction 需要的接口 ---
    def dispatch(self, command_id: str):
        ack = self._chi_success and (self._fault != ProtocolFault.ACK_LOSS)
        timed_out = (self._fault == ProtocolFault.ACK_LOSS)  # ACK 丢失 → 走"先核对"语义
        return _Dispatch(ack_received=ack, timed_out=timed_out)

    def query_output_file(self, command_id: str):
        if self._fault in (ProtocolFault.FILE_MISSING, ProtocolFault.FILE_DELAY):
            return None
        if not self._chi_success or self._file_hash is None:
            return None
        return {str(self._path): self._file_hash}

    def query_instrument_state(self):
        if self._fault == ProtocolFault.INSTRUMENT_STUCK:
            return "RUNNING"
        if self._fault == ProtocolFault.FILE_DELAY:
            return "RUNNING"
        if self._fault == ProtocolFault.FILE_MISSING:
            return "IDLE"
        if self._chi_success and self._file_hash is not None:
            return "DONE"
        return "IDLE"

    def query_sample_id(self):
        if self._fault == ProtocolFault.SAMPLE_SWAP and self._sample_id is not None:
            return f"{self._sample_id}__PROTOCOL_SWAP"
        return self._sample_id

    def query_temp_trace(self) -> Optional[Dict[str, Any]]:
        """独立温控见证:温度是否稳定到设定点(仅在线可得)。"""
        if self._setpoint_C is None or self._chamber_actual_C is None:
            return None
        settled = abs(float(self._chamber_actual_C) - float(self._setpoint_C)) <= self._settle_tol_C
        return {
            "settled": bool(settled),
            "setpoint_C": self._setpoint_C,
            "actual_C": self._chamber_actual_C,
            "tol_C": self._settle_tol_C,
        }


def submit_measurement_online(
    *,
    sample_id: Optional[str],
    output_file: Optional[str],
    measurement_signals: Dict[str, Any],
    chi_success: bool = True,
    chamber_actual_C: Optional[float] = None,
    setpoint_C: Optional[float] = None,
    settle_tol_C: float = 1.5,
    protocol_fault: Optional[str] = None,
    expected_sample_id: Optional[str] = None,
    intended_uses: Optional[List[str]] = None,
    target_claims: Optional[List[ClaimRequest]] = None,
    rb_act_signals: Optional[Dict[str, Any]] = None,
    event_store: Optional[Any] = None,
    command_id: Optional[str] = None,
) -> TransactionResult:
    """用**真实在线见证**提交一次测量事务(可选协议级故障注入),返回 TransactionResult。

    与 `submit_measurement_offline` 语义一致,但见证来自 `OnlineInstrumentWitness`
    (真实落盘文件 + 温控稳定 + 仪器态),而非 bundle 的历史 file_hashes。
    `CALIBRATION_EXPIRED` 会把计量不确定度打到 UNKNOWN(物理发生但不可用于 BO)。
    """
    signals = dict(measurement_signals or {})
    if rb_act_signals:
        for k, v in rb_act_signals.items():
            if v is not None:
                signals[k] = v
    if protocol_fault == ProtocolFault.CALIBRATION_EXPIRED:
        signals["uncertainty_status"] = "UNKNOWN"
        signals["calibration_valid"] = False

    inst = OnlineInstrumentWitness(
        sample_id=sample_id, output_file=output_file, chi_success=chi_success,
        chamber_actual_C=chamber_actual_C, setpoint_C=setpoint_C,
        settle_tol_C=settle_tol_C, protocol_fault=protocol_fault)
    txn = EvidenceTransaction(event_store)
    return txn.process(
        command_id=command_id or f"online-{uuid.uuid4().hex[:8]}",
        command="ONLINE_MEASUREMENT",
        instrument=inst,
        measurement_signals=signals,
        intended_uses=intended_uses or list(IntendedUse.ALL),
        target_claims=target_claims or [],
        expected_sample_id=expected_sample_id if expected_sample_id is not None else sample_id,
    )
