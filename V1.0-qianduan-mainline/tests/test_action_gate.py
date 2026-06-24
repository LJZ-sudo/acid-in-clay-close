# -*- coding: utf-8 -*-
"""WP4 Cutover:ActionGate 单一受控入口 + shadow/canary/enforce + override + 旁路清零。"""
from __future__ import annotations

import sys
from pathlib import Path

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_harness.action_gate import (  # noqa: E402
    ActionGate, ActionProposal, resolve_mode,
    SHADOW, CANARY, ENFORCE, DISPATCHED, SHADOW_DISPATCHED, BLOCKED, OVERRIDE_DISPATCHED,
)


def _gate(mode):
    calls = []
    g = ActionGate(enqueue_fn=lambda *a: calls.append(a), mode=mode)
    return g, calls


def test_shadow_always_dispatches_behavior_preserved():
    g, calls = _gate(SHADOW)
    d = g.submit(ActionProposal(command="TRIGGER_FINE_SCAN"))
    assert d.decision == SHADOW_DISPATCHED and d.dispatched is True
    assert calls == [("TRIGGER_FINE_SCAN",)]


def test_shadow_records_would_block_for_disallowed():
    g, calls = _gate(SHADOW)
    d = g.submit(ActionProposal(command="DROP_SAMPLE_IN_ACID"))  # 不在 allowlist
    assert d.decision == SHADOW_DISPATCHED      # shadow 仍照常下发(只观察)
    assert any("would_block_in_enforce=True" in r for r in d.reasons)


def test_enforce_blocks_disallowed():
    g, calls = _gate(ENFORCE)
    d = g.submit(ActionProposal(command="DROP_SAMPLE_IN_ACID"))
    assert d.decision == BLOCKED and d.dispatched is False
    assert calls == []                          # 未下发


def test_enforce_allows_allowlisted():
    g, calls = _gate(ENFORCE)
    d = g.submit(ActionProposal(command="BACKTRACK", params={"backtrack_delta": 10.0}))
    assert d.decision == DISPATCHED and d.dispatched is True
    assert calls == [("BACKTRACK", {"backtrack_delta": 10.0})]


def test_operator_override_dispatches_and_records():
    g, calls = _gate(ENFORCE)
    # 人工 override 即使命令不在 allowlist 也放行,但留痕、不计入自主
    d = g.submit(ActionProposal(command="MANUAL_STOP", source="operator", operator="JZ"))
    assert d.decision == OVERRIDE_DISPATCHED and d.dispatched is True


def test_mode_resolution_env(monkeypatch):
    monkeypatch.setenv("SCITX_HARNESS_MODE", "enforce")
    assert resolve_mode() == ENFORCE
    assert resolve_mode("shadow") == SHADOW          # 显式参数优先
    monkeypatch.delenv("SCITX_HARNESS_MODE", raising=False)
    assert resolve_mode() == SHADOW                  # 默认 shadow


def test_no_autonomous_bypass_after_cutover():
    """审计:agent.py 不再直连 enqueue_command(自主旁路=0)。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "audit_hw", str(MAINLINE / "scripts" / "audit_hardware_write_paths.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    hits = mod.scan(mod.PROJECT_ROOT)
    rep = mod.build_report(hits, mod.DEFAULT_ALLOWLIST)
    assert rep["autonomous_bypass_count"] == 0, rep["autonomous_bypass_sites"]
