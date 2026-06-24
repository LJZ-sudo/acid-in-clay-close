# -*- coding: utf-8 -*-
"""状态核对器（M5-A）。

超时后**先核对、不盲目重试**:查询仪器状态/输出文件/样品 ID → 判定物理提交状态。
不变量:`timeout(a) ⇒ ¬retry(a) U reconciled(a)`(本模块只核对、绝不发起重测)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .commits import PhysicalCommit


@dataclass
class ReconcileResult:
    physical_status: str
    reasons: list
    did_retry: bool = False     # 核对阶段绝不重试 → 恒 False


def reconcile(command_id: str, instrument: Any, expected_sample_id: str) -> ReconcileResult:
    """超时后核对物理是否发生(纯查询,无重试)。"""
    reasons = []
    file_ok = bool(instrument.query_output_file(command_id))
    state = instrument.query_instrument_state()
    sample_ok = (instrument.query_sample_id() == expected_sample_id)
    reasons.append(f"output_file_exists={file_ok}")
    reasons.append(f"instrument_state={state}")
    reasons.append(f"sample_id_match={sample_ok}")

    if file_ok and state == "DONE" and sample_ok:
        status = PhysicalCommit.RECONSTRUCTED      # 确认已发生(确认消息丢失而已)
    elif file_ok and not sample_ok:
        status = PhysicalCommit.UNKNOWN            # 文件在但样品对不上→不确定
    elif (not file_ok) and state == "IDLE":
        status = PhysicalCommit.FAILED             # 仪器空闲且无文件→未发生
    elif file_ok and state == "RUNNING":
        status = PhysicalCommit.PARTIAL
    else:
        status = PhysicalCommit.UNKNOWN
    return ReconcileResult(physical_status=status, reasons=reasons, did_retry=False)
