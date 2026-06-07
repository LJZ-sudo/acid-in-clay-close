"""测试 prompt 注册表能正确加载所有 prompt 文件。"""
import pytest


def test_list_prompts():
    from s8_stage3.config.prompt_registry import list_prompts
    prompts = list_prompts()
    assert len(prompts) >= 5, f"Expected at least 5 prompts, got {prompts}"


def test_load_s04_prompt():
    from s8_stage3.config.prompt_registry import load_prompt
    text = load_prompt("s04_hypothesis_generator")
    assert "OUTPUT FORMAT" in text
    assert "hypotheses" in text


def test_load_s06_prompt():
    from s8_stage3.config.prompt_registry import load_prompt
    text = load_prompt("s06_mechanism_arbiter")
    assert "mechanism_card" in text
    assert "justification" in text


def test_load_s07_prompt():
    from s8_stage3.config.prompt_registry import load_prompt
    text = load_prompt("s07_descriptor_extractor")
    assert "descriptors" in text
    assert "priority" in text


def test_load_s09_prompt():
    from s8_stage3.config.prompt_registry import load_prompt
    text = load_prompt("s09_family_generator")
    assert "families" in text
    assert "instances" in text


def test_load_s09_compact_prompt():
    from s8_stage3.config.prompt_registry import load_prompt
    text = load_prompt("s09_family_generator_compact")
    assert "exactly 5 instances" in text
    assert "descriptor_claim_pool" in text


def test_missing_prompt_raises():
    from s8_stage3.config.prompt_registry import load_prompt, PromptNotFoundError
    with pytest.raises(PromptNotFoundError):
        load_prompt("nonexistent_prompt_xyz")
