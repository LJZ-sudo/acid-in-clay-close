# -*- coding: utf-8 -*-
"""故障注入仪器模拟器（M5-A,纯软件,零硬件)。

模拟真实湿实验里"软件 success ≠ 物理发生"的几类故障,供 Demo A 验证 Harness 行为。
模拟器持有 ground-truth(文件是否生成/仪器状态/温度日志/校准),reconciler 据此核对,
**不需要真实仪器**。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class Fault:
    NONE = "NONE"
    TIMEOUT_ACK_LOST_FILE_OK = "TIMEOUT_ACK_LOST_FILE_OK"   # 工作完成、文件已生成,但确认消息丢失→超时
    TIMEOUT_NO_EFFECT = "TIMEOUT_NO_EFFECT"                 # 仪器空闲、无文件→真失败
    TEMP_NOT_EQUILIBRATED = "TEMP_NOT_EQUILIBRATED"        # 测了但温度未平衡→计量无效
    CALIBRATION_EXPIRED = "CALIBRATION_EXPIRED"            # 测了但校准过期→计量无效
    KK_FAIL = "KK_FAIL"                                     # 谱质量差→KK 失败→计量无效


@dataclass
class DispatchResult:
    ack_received: bool          # 是否收到仪器确认(False=超时)
    timed_out: bool


class InstrumentSimulator:
    """带可注入故障的仪器。ground-truth 字段供 reconciler 核对。"""

    def __init__(self, fault: str = Fault.NONE, sample_id: str = "S1"):
        self.fault = fault
        self.sample_id = sample_id
        # ground-truth(reconciler 查询)
        self.output_file_exists = True
        self.instrument_state = "DONE"     # IDLE | RUNNING | DONE
        self.temp_equilibrated = True
        self.calibration_valid = True
        self._apply_fault()

    def _apply_fault(self) -> None:
        if self.fault == Fault.TIMEOUT_NO_EFFECT:
            self.output_file_exists = False
            self.instrument_state = "IDLE"
        elif self.fault == Fault.TEMP_NOT_EQUILIBRATED:
            self.temp_equilibrated = False
        elif self.fault == Fault.CALIBRATION_EXPIRED:
            self.calibration_valid = False
        # TIMEOUT_ACK_LOST_FILE_OK / KK_FAIL:物理上已完成,文件在(KK 差在测量层体现)

    def dispatch(self, command_id: str) -> DispatchResult:
        """下发命令。两类故障会导致"超时"(无确认),但物理结果可能已发生。"""
        if self.fault in (Fault.TIMEOUT_ACK_LOST_FILE_OK, Fault.TIMEOUT_NO_EFFECT):
            return DispatchResult(ack_received=False, timed_out=True)
        return DispatchResult(ack_received=True, timed_out=False)

    # ground-truth 查询接口(reconciler 用,不触发重测)
    def query_output_file(self, command_id: str) -> bool:
        return self.output_file_exists

    def query_instrument_state(self) -> str:
        return self.instrument_state

    def query_sample_id(self) -> str:
        return self.sample_id
