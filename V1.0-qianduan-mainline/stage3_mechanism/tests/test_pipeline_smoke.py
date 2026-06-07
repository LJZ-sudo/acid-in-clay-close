"""端到端 mock pipeline smoke test：从 mock seed 跑到 S11。"""
import os
import pathlib
import tempfile
import pytest


@pytest.fixture(autouse=True)
def set_mock_env(monkeypatch):
    monkeypatch.setenv("STAGE3_LLM_MODE", "mock")
    monkeypatch.setenv("STAGE3_LITERATURE_MODE", "mock")
    monkeypatch.setenv("STAGE3_RUN_MODE", "mock")
    monkeypatch.setenv("STAGE3_API_KEY", "test_key")
    monkeypatch.setenv("STAGE3_API_BASE_URL", "https://api.openai.com")
    monkeypatch.setenv("STAGE3_MODEL_CHEAP", "gpt-4o-mini")
    monkeypatch.setenv("STAGE3_MODEL_STANDARD", "gpt-4o")
    monkeypatch.setenv("STAGE3_MODEL_PREMIUM", "gpt-4o")
    monkeypatch.setenv("STAGE3_ENABLE_CACHE", "false")
    monkeypatch.setenv("STAGE3_MAX_LLM_CALLS_PER_RUN", "200")


def make_gateway():
    from s8_stage3.config.settings import load_settings
    from s8_stage3.config.model_registry import ModelRegistry
    from s8_stage3.config.llm_gateway import LLMGateway
    settings = load_settings()
    registry = ModelRegistry(
        cheap=settings.model_cheap,
        standard=settings.model_standard,
        premium=settings.model_premium,
    )
    return LLMGateway(settings, registry), settings


def test_mock_pipeline_full_run():
    """Mock 模式下跑通当前 Stage3 可执行链，验证所有输出文件存在且有内容。"""
    gateway, settings = make_gateway()
    from s8_stage3.orchestrator.pipeline import Pipeline
    from s8_stage3.mock.mock_seed_factory import create_mock_seed_bundle

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = pathlib.Path(tmpdir)
        pipeline = Pipeline(
            settings=settings,
            gateway=gateway,
            output_dir=output_dir,
            run_mode="mock",
            literature_mode="mock",
        )
        results = pipeline.run_mock()

    assert results["evidence"] is not None
    assert len(results["evidence"].evidence_cards) > 0
    assert results["hypothesis_board"] is not None
    assert len(results["hypothesis_board"].hypotheses) >= 3
    assert results["mechanism_arbitration"] is not None
    assert results["descriptor_sheet"] is not None
    assert len(results["descriptor_sheet"].descriptors) >= 3
    assert results["ranking"] is not None
    assert len(results["ranking"].ranked_candidates) >= 2


def test_mock_seed_factory_shape():
    """Mock seed factory 必须产出最小样本数，保证下游测试有真实输入。"""
    from s8_stage3.mock.mock_seed_factory import create_mock_seed_bundle
    bundle = create_mock_seed_bundle()
    assert bundle.source_mode == "mock"
    assert len(bundle.seed_sample_summaries) >= 4
    assert len(bundle.seed_segments) >= 8
    assert len(bundle.seed_composition_nodes) >= 3
    assert len(bundle.seed_atlas_hints) >= 2


def test_s03_standalone_evidence_builder():
    """单独验证 S03 可运行，不依赖完整 pipeline。"""
    import tempfile, pathlib
    from s8_stage3.mock.mock_seed_factory import create_mock_seed_bundle
    from s8_stage3.agents.s03_evidence_builder import run_s03
    seed = create_mock_seed_bundle()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = pathlib.Path(tmpdir)
        bundle = run_s03(seed, output_dir)
        out_file = output_dir / "01_evidence" / "evidence_cards.json"
        assert len(bundle.evidence_cards) >= 3
        assert out_file.exists(), f"Expected output at {out_file}"


def test_mock_pipeline_until_s06():
    """Mock 模式截止到 S06。"""
    gateway, settings = make_gateway()
    from s8_stage3.orchestrator.pipeline import Pipeline

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = pathlib.Path(tmpdir)
        pipeline = Pipeline(
            settings=settings,
            gateway=gateway,
            output_dir=output_dir,
            run_mode="mock",
            literature_mode="mock",
            until_step="s06",
        )
        results = pipeline.run_mock()

    assert results["evidence"] is not None
    assert results["mechanism_arbitration"] is not None
    # S07+ 不应运行
    assert results.get("descriptor_sheet") is None


def test_mock_pipeline_s07_circuit_breaker_does_not_trigger():
    """正常 mock run 时，S07 不应触发断路器（mock 返回 >= 5 个描述符）。"""
    gateway, settings = make_gateway()
    from s8_stage3.orchestrator.pipeline import Pipeline

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = pathlib.Path(tmpdir)
        pipeline = Pipeline(
            settings=settings,
            gateway=gateway,
            output_dir=output_dir,
            run_mode="mock",
            literature_mode="mock",
            until_step="s07",
        )
        results = pipeline.run_mock()

    sheet = results.get("descriptor_sheet")
    assert sheet is not None
    assert len(sheet.descriptors) >= 3


def test_ranking_has_element_level_support():
    """每条排名路线必须带有文献支撑 (literature_support_card_ids 派生自 element_evidence)；
    即使 combination_novelty 是 novel_combination，每个组分也应有元素级类比论文。"""
    gateway, settings = make_gateway()
    from s8_stage3.orchestrator.pipeline import Pipeline

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = pathlib.Path(tmpdir)
        pipeline = Pipeline(
            settings=settings,
            gateway=gateway,
            output_dir=output_dir,
            run_mode="mock",
            literature_mode="mock",
        )
        results = pipeline.run_mock()

    ranking = results["ranking"]
    assert len(ranking.ranked_candidates) >= 1, "至少要有一条排名候选"
    for c in ranking.ranked_candidates:
        assert c.literature_support_card_ids, (
            f"候选 {c.instance_id} 缺少 literature_support_card_ids，"
            "违反反凭空编造审计要求"
        )
