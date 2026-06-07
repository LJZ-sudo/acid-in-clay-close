"""Stage1 closed-loop bookkeeping (P-Stage1-A/B).

提供按"轮"持久化的实验闭环 manifest：每轮三件套
    round_NNN_suggestion.json
    round_NNN_stage0_result.json
    round_NNN_decision_trace.json
以及聚合后的 closed_loop_metrics.json。
"""

from .round_logger import RoundLogger
from .metrics_aggregator import build_closed_loop_metrics
from .termination_evaluator import evaluate_termination

__all__ = ["RoundLogger", "build_closed_loop_metrics", "evaluate_termination"]
