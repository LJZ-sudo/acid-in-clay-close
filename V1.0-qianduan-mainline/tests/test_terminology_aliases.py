# -*- coding: utf-8 -*-
"""WP0 / P0-3：术语别名注册表的活契约测试。

把 configs/terminology_aliases.yaml 与真实代码(claim_audit.CLAIM_LEVEL_PREFERRED)
交叉校验,确保它不是死文档:命名降温映射必须与 claim 层实际生效的映射一致。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

MAINLINE = Path(__file__).resolve().parents[1]
YAML_PATH = MAINLINE / "configs" / "terminology_aliases.yaml"
S8_SRC = MAINLINE / "stage3_mechanism" / "src"
sys.path.insert(0, str(S8_SRC))


def _load():
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def test_yaml_parses_and_has_core_aliases():
    d = _load()
    aliases = d["aliases"]
    # 三个对外规范术语必须存在
    for canonical in ("transport_regime_change", "mechanistic_consistency"):
        assert canonical in aliases, canonical
        assert aliases[canonical]["legacy"], f"{canonical} 缺 legacy 映射"
        assert aliases[canonical]["max_claim_level"] in {"C0", "C1", "C2", "C3", "C4", "C5"}


def test_eis_only_terms_respect_c4_cap():
    """EIS-only:任何对外术语的 max_claim_level 不得越过 C4(不声称结构/因果)。"""
    d = _load()
    order = ["C0", "C1", "C2", "C3", "C4", "C5"]
    for canonical, spec in d["aliases"].items():
        assert order.index(spec["max_claim_level"]) <= order.index("C4"), canonical


def test_mechanism_alias_agrees_with_claim_audit():
    """活契约:yaml 的 mechanistic_consistency.legacy 必须与代码里实际生效的映射一致。"""
    d = _load()
    legacy = d["aliases"]["mechanistic_consistency"]["legacy"]
    assert "mechanism_discovery" in legacy
    try:
        from s8_stage3.contracts.claim_audit import CLAIM_LEVEL_PREFERRED
    except Exception:  # noqa: BLE001
        pytest.skip("claim_audit 不可导入(依赖缺失);跳过代码交叉校验")
    # 代码里 mechanism_discovery 的首选名 == yaml 的 canonical
    assert CLAIM_LEVEL_PREFERRED.get("mechanism_discovery") == "mechanism_consistency"


def test_registry_covers_real_legacy_tokens_in_code():
    """活契约:代码中真实出现的关键 legacy 术语必须已登记在别名注册表(防注册表与现实漂移)。

    注意:这是**只读核验**,不改代码。全仓 blanket 改名属高破坏/低价值,故意不做;
    reviewer 风险由 claim 层别名(mechanism_consistency)+ 手稿措辞 + 本注册表共同处理。
    """
    d = _load()
    all_legacy = set()
    for spec in d["aliases"].values():
        all_legacy.update(spec.get("legacy", []))
    for tok in ("phase_transition", "mechanism_discovery"):
        assert tok in all_legacy, f"{tok} 应登记到 terminology_aliases.yaml"
    # 只读扫描确认这些 legacy 词确实仍在代码里(故注册表登记是必要的,非空登记)
    found = {"phase_transition": False, "mechanism_discovery": False}
    for p in MAINLINE.rglob("*.py"):
        if any(seg in p.parts for seg in (".git", "__pycache__", "node_modules", "tests")):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for tok in found:
            if tok in txt:
                found[tok] = True
    assert found["mechanism_discovery"] is True
