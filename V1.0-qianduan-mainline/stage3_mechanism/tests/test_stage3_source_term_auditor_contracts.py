# -*- coding: utf-8 -*-
from __future__ import annotations

from s8_stage3.validation.source_term_auditor import audit_candidate_terms


def test_source_term_auditor_scans_current_output_dir_not_all_outputs(tmp_path):
    stage3_root = tmp_path / "stage3_mechanism"
    term_dir = stage3_root / "audit" / "candidate_terms"
    term_dir.mkdir(parents=True)
    term_file = term_dir / "lotus.yaml"
    term_file.write_text(
        "\n".join(
            [
                "target_candidate_group: lotus",
                "terms:",
                "  - lotus",
                "allowed_sources_by_mode:",
                "  blind_transfer:",
                "    allowed_before_s09: []",
            ]
        ),
        encoding="utf-8",
    )

    old_output = stage3_root / "outputs" / "old_run"
    old_output.mkdir(parents=True)
    (old_output / "stale.md").write_text("lotus should not be scanned here", encoding="utf-8")

    current_output = stage3_root / "outputs" / "current_run"
    current_output.mkdir(parents=True)
    result = audit_candidate_terms(
        stage3_root=stage3_root,
        output_dir=current_output,
        discovery_mode="blind_transfer",
        final_audit=False,
        candidate_term_files=[term_file],
    )

    assert result["lotus"].n_hits_total == 0

    (current_output / "pre_s09.md").write_text("lotus is a current-run hit", encoding="utf-8")
    result = audit_candidate_terms(
        stage3_root=stage3_root,
        output_dir=current_output,
        discovery_mode="blind_transfer",
        final_audit=False,
        candidate_term_files=[term_file],
    )

    assert result["lotus"].n_hits_total == 1
    assert result["lotus"].violations[0]["path"].endswith("pre_s09.md")


def test_source_term_auditor_ignores_archived_cache(tmp_path):
    stage3_root = tmp_path / "stage3_mechanism"
    term_dir = stage3_root / "audit" / "candidate_terms"
    term_dir.mkdir(parents=True)
    term_file = term_dir / "lotus.yaml"
    term_file.write_text(
        "\n".join(
            [
                "target_candidate_group: lotus",
                "terms:",
                "  - lotus",
                "allowed_sources_by_mode:",
                "  blind_transfer:",
                "    allowed_before_s09: []",
            ]
        ),
        encoding="utf-8",
    )

    archived_cache = stage3_root / "data" / "cache" / "archive" / "old" / "llm_cache"
    archived_cache.mkdir(parents=True)
    (archived_cache / "old.json").write_text('{"content":"lotus from old cache"}', encoding="utf-8")

    current_cache = stage3_root / "data" / "cache" / "current" / "llm_cache"
    current_cache.mkdir(parents=True)
    (current_cache / "current.json").write_text('{"content":"lotus from current cache"}', encoding="utf-8")

    result = audit_candidate_terms(
        stage3_root=stage3_root,
        output_dir=stage3_root / "outputs" / "current_run",
        discovery_mode="blind_transfer",
        final_audit=False,
        candidate_term_files=[term_file],
    )

    assert result["lotus"].n_hits_total == 1
    assert result["lotus"].hits[0]["path"].endswith("current.json")
