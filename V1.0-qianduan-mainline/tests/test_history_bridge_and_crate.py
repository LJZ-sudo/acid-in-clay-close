# -*- coding: utf-8 -*-
"""WP5 剩余:history_db 物化为 CommittedObservationView(只有 committed 进 BO)+ RO-Crate。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from scientific_memory.history_bridge import (  # noqa: E402
    materialize_committed_view, view_to_training_arrays, load_trials,
)
from scientific_memory.invalidation_engine import InvalidationEngine  # noqa: E402
from scientific_memory.bo_rebuilder import rebuild_after_invalidation  # noqa: E402
from scientific_e2e.ro_crate import build_ro_crate, build_default_crate  # noqa: E402

HISTORY_DB = MAINLINE / "stage1_optimization" / "campaign_memory" / "history_db_attapulgite.json"


# ---- history_db → CommittedObservationView(真实数据) ----

def test_materialize_real_history_db():
    graph, view, id2trial = materialize_committed_view(HISTORY_DB, objective_key="combined_score")
    trials = load_trials(HISTORY_DB)
    n_with_obj = sum(1 for t in trials if "combined_score" in (t.get("objectives") or {}))
    assert len(view.observations) == n_with_obj > 0
    # 真实数据里 trial 1(R0.186)combined_score=-1.94 是最优
    best = view.best()
    assert best is not None
    assert id2trial[best.evidence_id] == 1
    graph.close()


def test_only_committed_evidence_feeds_bo_and_invalidation_changes_training_set():
    graph, view, id2trial = materialize_committed_view(HISTORY_DB, objective_key="combined_score")
    X0, y0 = view_to_training_arrays(view, ["R", "N"])
    n0 = len(X0)
    best0 = view.best().evidence_id

    # 失效"当前最优"那条证据(模拟其 Skill/校准事后失效)→ 重建训练集
    InvalidationEngine(graph).mark_invalid([best0], reason="post_hoc_calibration_bug")
    all_obs = view.observations
    new_view, report = rebuild_after_invalidation(graph, all_obs, "combined_score", view)
    X1, y1 = view_to_training_arrays(new_view, ["R", "N"])

    assert best0 in report.removed_evidence_ids       # 失效证据被剔除
    assert len(X1) == n0 - 1                           # 训练集少一条(只有 committed 进 BO)
    assert report.best_changed is True                 # 最优改变
    graph.close()


# ---- RO-Crate 复现包 ----

def test_ro_crate_records_real_artifacts(tmp_path):
    md = build_default_crate(MAINLINE)
    files = [e for e in md["@graph"] if e.get("@type") in ("File", "Dataset") and "@id" in e
             and e["@id"] not in ("./",)]
    # 至少 objective/dataset registry 这些真实文件应 present + 带 sha256
    present = [e for e in files if e.get("present")]
    assert md["_summary"]["n_present"] >= 4
    for e in present:
        assert e["sha256"] and len(e["sha256"]) == 64


def test_ro_crate_flags_missing_not_fabricated(tmp_path):
    out = tmp_path / "ro-crate-metadata.json"
    md = build_ro_crate(tmp_path, [{"path": "does_not_exist.json", "type": "File", "desc": "x"}], out)
    ent = [e for e in md["@graph"] if e.get("@id") == "does_not_exist.json"][0]
    assert ent["present"] is False and ent["sha256"] is None    # 缺失如实标记,不伪造
    assert out.is_file()
