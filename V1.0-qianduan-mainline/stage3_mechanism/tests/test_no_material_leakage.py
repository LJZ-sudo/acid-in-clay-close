"""测试 no_leakage_checker 的 advisory 行为。

2025 重构后语义变化：
  - no_leakage_checker 不再针对特定候选材料（lotus/PVA/attapulgite/sepiolite）做黑名单，
    因为那会把"答案"写死进流程。
  - 仍保留一个通用的"商业品牌 PEM 名"黑名单（Nafion / SPEEK 等）和具体配方数值检查，
    用来挡 LLM 在机理层凭空脱口而出。
  - assert_no_leakage 被降级为 advisory，不再 raise。
"""


def test_leakage_checker_detects_nafion_brand():
    from s8_stage3.validation.no_leakage_checker import check_leakage
    violations = check_leakage("s04", {"statement": "Nafion-type membrane provides baseline"})
    assert len(violations) > 0, "商业品牌名 Nafion 应被 advisory 标记"


def test_leakage_checker_detects_specific_loading():
    from s8_stage3.validation.no_leakage_checker import check_leakage
    violations = check_leakage("s05", "Mechanism favors 12 wt% doping at low T")
    assert len(violations) > 0, "'12 wt%' 这种配方级数值不应出现在机理层"


def test_leakage_checker_clean():
    from s8_stage3.validation.no_leakage_checker import check_leakage
    violations = check_leakage("s04", {"statement": "OH-rich host with H-bond network"})
    assert len(violations) == 0


def test_leakage_checker_no_longer_blocks_lotus_or_starch():
    """Regression: lotus / PVA / attapulgite / sepiolite / starch 必须不在黑名单里。
    这些是自然涌现的候选材料，不该被上游 advisory 阻断。"""
    from s8_stage3.validation.no_leakage_checker import check_leakage
    for substance in ["lotus", "PVA", "attapulgite", "sepiolite", "starch", "chitosan", "藕粉"]:
        v = check_leakage("s09_families", f"Candidate family mentions {substance}")
        assert v == [], f"{substance!r} 不应再被 advisory 拦截"


def test_mock_s03_output_no_leakage():
    """Mock pipeline S03 输出不应触发 advisory（因为 S03 只产出观测 evidence）。"""
    import os
    os.environ["STAGE3_LLM_MODE"] = "mock"
    os.environ["STAGE3_API_KEY"] = "test"
    os.environ["STAGE3_ENABLE_CACHE"] = "false"

    from s8_stage3.mock.mock_seed_factory import create_mock_seed_bundle
    from s8_stage3.agents.s03_evidence_builder import run_s03
    from s8_stage3.validation.no_leakage_checker import check_leakage
    import tempfile
    import pathlib

    seed = create_mock_seed_bundle()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = pathlib.Path(tmpdir)
        (output_dir / "01_evidence").mkdir()
        bundle = run_s03(seed, output_dir)
        data = bundle.model_dump(mode="json")
        violations = check_leakage("s03", data)
        assert len(violations) == 0, f"S03 输出不应触发 advisory: {violations}"


def test_mock_s07_output_no_leakage():
    """Mock S07 描述符不应触发 advisory。"""
    from s8_stage3.mock.mock_llm import mock_chat_json
    from s8_stage3.validation.no_leakage_checker import check_leakage
    result = mock_chat_json("s07_descriptor_extractor", [])
    violations = check_leakage("s07", result)
    assert len(violations) == 0, f"Mock S07 不应触发 advisory: {violations}"


def test_assert_no_leakage_is_advisory_no_raise():
    """assert_no_leakage 已降级为 advisory：即使命中也不 raise。"""
    from s8_stage3.validation.no_leakage_checker import assert_no_leakage
    # 不抛异常
    assert_no_leakage("s04", {"text": "Nafion + lotus starch mix"})


# --- Tier1 lock-down (2026-06-01): advisory default + opt-in strict mode ---

def test_assert_no_leakage_default_returns_violations_without_raising():
    """默认 strict=False：返回违规列表但绝不 raise（保持冻结行为）。"""
    from s8_stage3.validation.no_leakage_checker import assert_no_leakage
    violations = assert_no_leakage("s04", {"text": "Nafion baseline membrane"})
    assert isinstance(violations, list)
    assert len(violations) > 0


def test_assert_no_leakage_strict_raises_on_violation():
    """strict=True（Tier2 硬强制路径）：命中时抛 LeakageViolationError。"""
    import pytest
    from s8_stage3.validation.no_leakage_checker import (
        assert_no_leakage,
        LeakageViolationError,
    )
    with pytest.raises(LeakageViolationError):
        assert_no_leakage("s04", {"text": "Nafion baseline membrane"}, strict=True)


def test_assert_no_leakage_strict_clean_does_not_raise():
    from s8_stage3.validation.no_leakage_checker import assert_no_leakage
    violations = assert_no_leakage(
        "s04", {"text": "OH-rich host with H-bond network"}, strict=True
    )
    assert violations == []
