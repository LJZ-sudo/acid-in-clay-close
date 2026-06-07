"""测试排名约束：combination_novelty / 分数一致性 / scoring 模块。"""
import pytest


def test_mock_ranking_combination_novelty():
    """方案 B: 每条候选都必须声明 combination_novelty;
    所有候选 (包括 exact_match / close_variant) 都必须有实质性 novelty_rationale。"""
    from s8_stage3.mock.mock_llm import mock_chat_json
    result = mock_chat_json("s10", [])
    candidates = result.get("ranked_candidates", [])
    assert len(candidates) >= 1
    novelty_seen = set()
    for c in candidates:
        assert "lotus_related" not in c, "lotus_related 字段不应再出现在 mock 输出"
        assert "evidence_tier" not in c, "evidence_tier 字段已被 combination_novelty 替代"
        nov = c.get("combination_novelty")
        assert nov in {"novel_combination", "close_variant", "exact_match"}, (
            f"候选 {c.get('instance_id')} combination_novelty 非法: {nov}"
        )
        novelty_seen.add(nov)
        # novelty_rationale 对所有 instance 都必填
        assert len((c.get("novelty_rationale") or "").strip()) >= 120, (
            f"候选 {c.get('instance_id')} novelty_rationale "
            f"需 >= 120 chars (对所有 combination_novelty 值都强制)"
        )
        # element 级文献引用: literature_support_card_ids 应非空
        assert c.get("literature_support_card_ids"), (
            f"候选 {c.get('instance_id')} literature_support_card_ids 为空, "
            "每个候选至少应有一个 element-level 类比"
        )
    # mock 应包含 novel_combination 作为主体
    assert "novel_combination" in novelty_seen, (
        f"Mock S10 输出必须示范 novel_combination, 实际: {novelty_seen}"
    )


def test_ranking_contract_validates_mock():
    """Mock S10 输出可以被 RankingResult contract 接受。"""
    from s8_stage3.mock.mock_llm import mock_chat_json
    from s8_stage3.contracts.ranking import RankingResult
    result = mock_chat_json("s10", [])
    ranking = RankingResult.model_validate(result)
    assert len(ranking.ranked_candidates) >= 2
    assert ranking.ranked_candidates[0].rank == 1


def test_scoring_consistency():
    """compute_weighted_score 结果与 total_score 相差不应超过 0.15。"""
    from s8_stage3.mock.mock_llm import mock_chat_json
    from s8_stage3.contracts.ranking import RankingResult
    from s8_stage3.scoring.material_score import compute_weighted_score

    result = mock_chat_json("s10", [])
    ranking = RankingResult.model_validate(result)
    for cand in ranking.ranked_candidates:
        if cand.criteria_scores:
            computed = compute_weighted_score(cand)
            assert abs(computed - cand.total_score) < 0.15, (
                f"Score mismatch for {cand.instance_name}: "
                f"computed={computed}, stated={cand.total_score}"
            )


def test_ranking_order_descending():
    """排名候选的得分应按降序排列（允许小误差）。"""
    from s8_stage3.mock.mock_llm import mock_chat_json
    from s8_stage3.contracts.ranking import RankingResult
    result = mock_chat_json("s10", [])
    ranking = RankingResult.model_validate(result)
    scores = [c.total_score for c in ranking.ranked_candidates]
    for i in range(1, len(scores)):
        assert scores[i] <= scores[i - 1] + 0.02, (
            f"Ranking order violation: score[{i}]={scores[i]} > score[{i-1}]={scores[i-1]}"
        )


def test_sensitivity_analysis():
    from s8_stage3.mock.mock_llm import mock_chat_json
    from s8_stage3.contracts.ranking import RankingResult
    from s8_stage3.scoring.sensitivity import rank_sensitivity_summary
    result = mock_chat_json("s10", [])
    ranking = RankingResult.model_validate(result)
    summary = rank_sensitivity_summary(ranking.ranked_candidates)
    assert "top1" in summary
    assert "score_gap" in summary
