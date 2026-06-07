"""测试 LLM Gateway 的 mock 模式。"""
import os
import pytest


@pytest.fixture
def mock_gateway():
    os.environ["STAGE3_LLM_MODE"] = "mock"
    os.environ["STAGE3_API_KEY"] = "test_key"
    os.environ["STAGE3_API_BASE_URL"] = "https://api.openai.com"
    os.environ["STAGE3_MODEL_CHEAP"] = "gpt-4o-mini"
    os.environ["STAGE3_MODEL_STANDARD"] = "gpt-4o"
    os.environ["STAGE3_MODEL_PREMIUM"] = "gpt-4o"
    os.environ["STAGE3_ENABLE_CACHE"] = "false"

    from s8_stage3.config.settings import load_settings
    from s8_stage3.config.model_registry import ModelRegistry
    from s8_stage3.config.llm_gateway import LLMGateway
    settings = load_settings()
    registry = ModelRegistry(
        cheap=settings.model_cheap,
        standard=settings.model_standard,
        premium=settings.model_premium,
    )
    return LLMGateway(settings, registry)


def test_gateway_is_mock(mock_gateway):
    assert mock_gateway.is_mock is True


def test_gateway_resolves_model(mock_gateway):
    model = mock_gateway.resolve_model_for_step("s04_hypothesis_generator")
    assert isinstance(model, str)
    assert len(model) > 0


def test_gateway_mock_chat_json_s04(mock_gateway):
    messages = [{"role": "user", "content": "test"}]
    result = mock_gateway.chat_json(messages, step="s04_hypothesis_generator")
    assert isinstance(result, dict)
    assert "hypotheses" in result
    assert len(result["hypotheses"]) >= 4


def test_gateway_mock_chat_json_s07(mock_gateway):
    messages = [{"role": "user", "content": "test"}]
    result = mock_gateway.chat_json(messages, step="s07_descriptor_extractor")
    assert isinstance(result, dict)
    assert "descriptors" in result
    assert len(result["descriptors"]) >= 3


def test_gateway_call_count(mock_gateway):
    messages = [{"role": "user", "content": "test"}]
    mock_gateway.chat_json(messages, step="s04_hypothesis_generator")
    mock_gateway.chat_json(messages, step="s07_descriptor_extractor")
    assert mock_gateway.call_count == 2


def test_gateway_cost_summary(mock_gateway):
    messages = [{"role": "user", "content": "test"}]
    mock_gateway.chat_json(messages, step="s04")
    summary = mock_gateway.get_cost_summary()
    assert "total_calls" in summary
    assert summary["total_calls"] >= 1
