# -*- coding: utf-8 -*-
"""WP1-c：三类 ID + PhysicalEffect 多见证推断契约测试。

核心诚实约束:仅软件见证 ⇒ 至多 possible;ACK 丢失但有独立文件+DONE ⇒ confirmed(重建);
样品错配 ⇒ unknown;空闲无文件 ⇒ not_occurred。
"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_harness.witness import (  # noqa: E402
    Witness, WitnessKind, ExecutionAttempt, PhysicalEffect,
    infer_physical_effect, witnesses_from_instrument,
)
from scientific_harness.commits import PhysicalCommit  # noqa: E402
from scientific_harness.fault_injection import InstrumentSimulator, Fault  # noqa: E402


def test_software_only_witness_is_at_most_possible():
    """仅软件 ACK + 状态查询(无独立见证)→ 不得 confirmed,最多 possible。"""
    ws = [Witness(WitnessKind.SOFTWARE_ACK, True),
          Witness(WitnessKind.INSTRUMENT_STATE, True, detail="DONE")]
    eff = infer_physical_effect("cmd1", ws)
    assert eff.occurred == "possible"
    assert eff.independent_witness_count == 0


def test_ack_lost_but_independent_file_done_is_confirmed():
    """ACK 丢失,但有独立原始文件 + 状态 DONE → confirmed(= 重建)。"""
    ws = [Witness(WitnessKind.SOFTWARE_ACK, False),
          Witness(WitnessKind.RAW_FILE, True, detail="sha=abc"),
          Witness(WitnessKind.INSTRUMENT_STATE, True, detail="DONE")]
    eff = infer_physical_effect("cmd1", ws)
    assert eff.occurred == "confirmed"
    assert eff.independent_witness_count >= 1
    assert eff.to_commit_status() == PhysicalCommit.EFFECT_OBSERVED


def test_sample_mismatch_is_unknown():
    ws = [Witness(WitnessKind.RAW_FILE, True),
          Witness(WitnessKind.INSTRUMENT_STATE, True, detail="DONE"),
          Witness(WitnessKind.SAMPLE_ID, True, detail="WRONG")]
    eff = infer_physical_effect("cmd1", ws, expected_sample_id="S1")
    assert eff.occurred == "unknown"


def test_idle_no_file_is_not_occurred():
    ws = [Witness(WitnessKind.SOFTWARE_ACK, False),
          Witness(WitnessKind.RAW_FILE, False),
          Witness(WitnessKind.INSTRUMENT_STATE, True, detail="IDLE"),
          Witness(WitnessKind.TEMP_TRACE, True)]
    eff = infer_physical_effect("cmd1", ws)
    assert eff.occurred == "not_occurred"
    assert eff.to_commit_status() == PhysicalCommit.FAILED


def test_three_ids_are_distinct():
    a = ExecutionAttempt.make("cmd1", command="EIS", ack_received=True)
    eff = infer_physical_effect("cmd1", [Witness(WitnessKind.RAW_FILE, True),
                                         Witness(WitnessKind.INSTRUMENT_STATE, True, detail="DONE")])
    # attempt_id 与 physical_effect_id 是不同的标识(GPT-3:三类 ID 必须分离)
    assert a.attempt_id != eff.physical_effect_id
    assert a.command_hash is not None


def test_from_instrument_ack_lost_file_ok_simulator():
    """与既有 fault_injection 模拟器联动:TIMEOUT_ACK_LOST_FILE_OK → confirmed。"""
    inst = InstrumentSimulator(fault=Fault.TIMEOUT_ACK_LOST_FILE_OK, sample_id="S1")
    ws = witnesses_from_instrument(inst, "cmd1", ack_received=False)
    eff = infer_physical_effect("cmd1", ws, expected_sample_id="S1")
    assert eff.occurred == "confirmed"  # 文件在(独立)+ 状态 DONE


def test_from_instrument_no_effect_simulator():
    inst = InstrumentSimulator(fault=Fault.TIMEOUT_NO_EFFECT, sample_id="S1")
    ws = witnesses_from_instrument(inst, "cmd1", ack_received=False)
    eff = infer_physical_effect("cmd1", ws, expected_sample_id="S1")
    assert eff.occurred == "not_occurred"
