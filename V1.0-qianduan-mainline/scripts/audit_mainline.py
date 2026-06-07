#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only mainline audit for the AiCE + S8 reasoning project.

The script inspects current contracts and writes a JSON/Markdown report under
the external `codex` report directory by default. It does not mutate project
state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = PROJECT_ROOT / "codex"
CAMPAIGN = PROJECT_ROOT / "stage1_optimization" / "campaigns" / "attapulgite_aice_campaign.json"
RECIPE = PROJECT_ROOT / "stage1_optimization" / "output" / "attapulgite_aice" / "next_experiment_recipe.json"
STAGE2_SEED = PROJECT_ROOT / "stage2_statistics" / "exports" / "stage3_seed.json"
STAGE3_OUTPUTS = PROJECT_ROOT / "stage3_mechanism" / "outputs"
STAGE1_ENV = PROJECT_ROOT / "stage1_optimization" / ".env"
STAGE3_ENV = PROJECT_ROOT / "stage3_mechanism" / ".env"
STAGE3_SRC = PROJECT_ROOT / "stage3_mechanism" / "src"
STAGE3_FEEDBACK = PROJECT_ROOT / "stage3_mechanism" / "data" / "validation" / "experimental_feedback.json"
LEGACY_ROOT_MARKERS = (
    "D:/acid-in-clay-close",
    "D:\\acid-in-clay-close",
    "C:/Users/JZ/Desktop/acid-in-clay-close",
    "C:\\Users\\JZ\\Desktop\\acid-in-clay-close",
)

EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "archive",
    "backups",
    "codex",
    "data",
    ".venv",
    "venv",
    "output",
    "outputs",
    "runs",
}
TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".csv",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


def _sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _same_path(left: str | None, right: Path) -> bool:
    if not left:
        return False
    try:
        resolved_left = _resolve_project_path(left)
        return resolved_left is not None and resolved_left.resolve() == right.resolve()
    except Exception:  # noqa: BLE001
        return False


def _has_legacy_root(raw: str | None) -> bool:
    if not raw:
        return False
    return any(marker in raw for marker in LEGACY_ROOT_MARKERS)


def _resolved_project_path_summary(raw: str | None) -> dict[str, Any]:
    resolved = _resolve_project_path(raw)
    return {
        "recorded_empty": not bool(raw),
        "recorded_has_legacy_root": _has_legacy_root(raw),
        "resolved_path": _rel(resolved) if resolved is not None else "",
        "resolved_exists": bool(resolved and resolved.exists()),
    }


def _resolve_project_path(raw: str | None) -> Path | None:
    """Resolve paths recorded on another machine back into this project tree."""
    if not raw:
        return None
    path = Path(raw)
    if path.exists():
        return path

    text = str(raw).replace("\\", "/")
    marker = "V1.0-qianduan-mainline/"
    if marker in text:
        suffix = text.split(marker, 1)[1]
        candidate = PROJECT_ROOT / suffix
        if candidate.exists():
            return candidate

    candidate = PROJECT_ROOT / text
    if candidate.exists():
        return candidate
    return path


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _secret_fingerprint(value: str) -> dict[str, Any]:
    if not value:
        return {"present": False, "length": 0, "sha256_prefix": "missing"}
    return {
        "present": True,
        "length": len(value),
        "sha256_prefix": hashlib.sha256(value.encode("utf-8")).hexdigest()[:12],
    }


def audit_stage1_recipe() -> dict[str, Any]:
    campaign = _load_json(CAMPAIGN)
    recipe = _load_json(RECIPE)
    storage = campaign.get("storage") or {}
    expected_history = PROJECT_ROOT / "stage1_optimization" / storage.get(
        "history_db", "campaign_memory/history_db_attapulgite.json"
    )
    required = [
        "schema_version",
        "artifact_type",
        "created_at",
        "campaign_config",
        "source_mode",
        "source_tag",
        "history_db",
        "input_bundle_hash",
        "recipe",
        "optimizer_suggestion",
        "optimizer_vs_llm_delta",
        "safety_box",
    ]
    missing = [k for k in required if k not in recipe]
    warnings: list[str] = []
    if recipe.get("schema_version") != "0.2.0":
        warnings.append("schema_version_not_0.2.0")
    if recipe.get("artifact_type") != "stage1_next_experiment_recipe":
        warnings.append("artifact_type_not_stage1_recipe")
    if missing:
        warnings.append("missing_fields:" + ",".join(missing))
    if not _same_path(str(recipe.get("history_db") or ""), expected_history):
        warnings.append("history_db_path_mismatch")
    params = ((recipe.get("recipe") or {}).get("recommended_parameters") or {})
    if params.get("R") is None or params.get("N") is None:
        warnings.append("recommended_R_or_N_missing")
    return {
        "path": _rel(RECIPE),
        "exists": RECIPE.exists(),
        "schema_version": recipe.get("schema_version"),
        "artifact_type": recipe.get("artifact_type"),
        "history_db": recipe.get("history_db"),
        "expected_history_db": str(expected_history.resolve()),
        "schema_valid": not warnings,
        "warnings": warnings,
    }


def audit_llm_config() -> dict[str, Any]:
    stage1_env = _read_env(STAGE1_ENV)
    stage3_env = _read_env(STAGE3_ENV)
    stage1_model = stage1_env.get("LLM_MODEL") or stage1_env.get("MODEL") or ""
    stage3_models = {
        "cheap": stage3_env.get("STAGE3_MODEL_CHEAP") or "",
        "standard": stage3_env.get("STAGE3_MODEL_STANDARD") or "",
        "premium": stage3_env.get("STAGE3_MODEL_PREMIUM") or "",
    }
    non_empty_stage3_models = [m for m in stage3_models.values() if m]
    model_aligned = bool(stage1_model) and all(
        m == stage1_model for m in non_empty_stage3_models
    )
    return {
        "stage1_env_exists": STAGE1_ENV.exists(),
        "stage3_env_exists": STAGE3_ENV.exists(),
        "stage1_key": _secret_fingerprint(stage1_env.get("LLM_API_KEY", "")),
        "stage3_key": _secret_fingerprint(stage3_env.get("STAGE3_API_KEY", "")),
        "stage1_model": stage1_model,
        "stage3_models": stage3_models,
        "models_aligned": model_aligned,
    }


def audit_stage2_seed() -> dict[str, Any]:
    seed = _load_json(STAGE2_SEED)
    warnings: list[str] = []
    if seed.get("schema_version") != "0.2.0":
        warnings.append("schema_version_not_0.2.0")
    if seed.get("source_system") != "s8_reference":
        warnings.append("source_system_not_s8_reference")
    if seed.get("stage3_ready") is not True:
        warnings.append("stage3_not_ready")
    if not seed.get("input_hashes"):
        warnings.append("missing_input_hashes")
    return {
        "path": _rel(STAGE2_SEED),
        "exists": STAGE2_SEED.exists(),
        "sha256": _sha256(STAGE2_SEED),
        "schema_version": seed.get("schema_version"),
        "stage3_ready": seed.get("stage3_ready"),
        "blocking_reasons": seed.get("stage3_blocking_reasons"),
        "sample_count": len(seed.get("sample_summary") or []),
        "segment_count": len(seed.get("segment_fits") or []),
        "evidence_unit_count": len(seed.get("evidence_units") or []),
        "warnings": warnings,
    }


def audit_stage3_manifests(seed_hash: str) -> dict[str, Any]:
    manifests = sorted(
        STAGE3_OUTPUTS.rglob("run_manifest.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    rows = []
    matching = []
    for path in manifests[:25]:
        data = _load_json(path)
        seed_path = _resolved_project_path_summary(data.get("stage2_seed_path"))
        output_dir = _resolved_project_path_summary(data.get("output_dir"))
        row = {
            "path": _rel(path),
            "stage2_seed_path_resolved": seed_path["resolved_path"],
            "stage2_seed_path_exists": seed_path["resolved_exists"],
            "stage2_seed_path_legacy_root": seed_path["recorded_has_legacy_root"],
            "stage2_seed_sha256": data.get("stage2_seed_sha256"),
            "output_dir_resolved": output_dir["resolved_path"] if not output_dir["recorded_empty"] else _rel(path.parent),
            "output_dir_exists": output_dir["resolved_exists"] if not output_dir["recorded_empty"] else path.parent.exists(),
            "output_dir_legacy_root": output_dir["recorded_has_legacy_root"],
            "strict_real_input": data.get("strict_real_input"),
        }
        rows.append(row)
        if seed_hash != "missing" and data.get("stage2_seed_sha256") == seed_hash:
            matching.append(row)
    return {
        "manifest_count_seen": len(manifests),
        "latest_manifests": rows,
        "matching_current_stage2_seed": matching,
        "warnings": [] if matching else ["no_recent_manifest_matches_current_stage2_seed"],
    }


def _stage3_output_dir_from_manifest(stage3: dict[str, Any]) -> Path | None:
    rows = stage3.get("matching_current_stage2_seed") or stage3.get("latest_manifests") or []
    if not rows:
        return None
    row = rows[0]
    output_dir = row.get("output_dir_resolved")
    if output_dir:
        try:
            resolved = PROJECT_ROOT / str(output_dir).replace("\\", "/")
            if resolved and resolved.exists():
                return resolved
        except TypeError:
            pass

    manifest_path = row.get("path")
    if manifest_path:
        candidate = PROJECT_ROOT / str(manifest_path).replace("\\", "/")
        if candidate.exists():
            return candidate.parent
    return None


def audit_experimental_feedback() -> dict[str, Any]:
    if not STAGE3_FEEDBACK.exists():
        return {
            "path": _rel(STAGE3_FEEDBACK),
            "exists": False,
            "schema_valid": None,
            "warnings": ["experimental_feedback_json_absent_csv_fallback_expected"],
        }
    data = _load_json(STAGE3_FEEDBACK)
    warnings: list[str] = []
    schema_valid = True
    try:
        if str(STAGE3_SRC) not in sys.path:
            sys.path.insert(0, str(STAGE3_SRC))
        from s8_stage3.contracts.experimental_feedback import ExperimentalFeedback

        ExperimentalFeedback.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        schema_valid = False
        warnings.append(f"schema_invalid:{exc}")
    return {
        "path": _rel(STAGE3_FEEDBACK),
        "exists": True,
        "sha256": _sha256(STAGE3_FEEDBACK),
        "schema_version": data.get("schema_version"),
        "artifact_type": data.get("artifact_type"),
        "n_validation_records": len(data.get("validation_records") or []),
        "schema_valid": schema_valid,
        "warnings": warnings,
    }


def audit_stage3_current_artifacts(stage3: dict[str, Any]) -> dict[str, Any]:
    output_dir = _stage3_output_dir_from_manifest(stage3)
    if output_dir is None:
        return {
            "output_dir": "",
            "warnings": ["no_stage3_output_dir_from_manifest"],
        }

    robustness_path = output_dir / "09_ranking" / "ranking_robustness_v2.json"
    binding_path = output_dir / "12_validation_binding" / "validation_binding_report.json"
    claim_path = output_dir / "13_claim_audit" / "claim_audit_report.json"
    robustness = _load_json(robustness_path) if robustness_path.exists() else {}
    binding = _load_json(binding_path) if binding_path.exists() else {}
    claim = _load_json(claim_path) if claim_path.exists() else {}

    claim_text = json.dumps(claim, ensure_ascii=False)
    claim_paths_relative = "outputs/stage3/" not in claim_text.replace("\\", "/")

    warnings: list[str] = []
    if not robustness_path.exists():
        warnings.append("ranking_robustness_v2_missing")
    if not binding_path.exists():
        warnings.append("validation_binding_report_missing")
    if not claim_path.exists():
        warnings.append("claim_audit_report_missing")
    if claim_path.exists() and not claim_paths_relative:
        warnings.append("claim_audit_contains_fixed_outputs_stage3_path")

    return {
        "output_dir": _rel(output_dir),
        "ranking_robustness": {
            "path": _rel(robustness_path),
            "exists": robustness_path.exists(),
            "sha256": _sha256(robustness_path),
            "status": robustness.get("status"),
            "stability_class": robustness.get("stability_class"),
            "top1_stability_rate": robustness.get("top1_stability_rate"),
            "top3_jaccard_mean": robustness.get("top3_jaccard_mean"),
        },
        "validation_binding": {
            "path": _rel(binding_path),
            "exists": binding_path.exists(),
            "sha256": _sha256(binding_path),
            "n_records": binding.get("n_records"),
            "n_bound": binding.get("n_bound"),
            "feedback_schema_valid": binding.get("feedback_schema_valid"),
            "source_feedback_path_resolved": _resolved_project_path_summary(
                binding.get("source_feedback_path")
            )["resolved_path"],
            "source_feedback_path_exists": _resolved_project_path_summary(
                binding.get("source_feedback_path")
            )["resolved_exists"],
            "source_feedback_path_legacy_root": _resolved_project_path_summary(
                binding.get("source_feedback_path")
            )["recorded_has_legacy_root"],
        },
        "claim_audit": {
            "path": _rel(claim_path),
            "exists": claim_path.exists(),
            "sha256": _sha256(claim_path),
            "claim_paths_relative": claim_paths_relative,
            "publication_blocker_count": len(claim.get("publication_blockers") or []),
        },
        "warnings": warnings,
    }


def _iter_text_files():
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if EXCLUDED_DIRS & parts:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def scan_mainline_text() -> dict[str, list[dict[str, Any]]]:
    patterns = {
        "possible_api_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        "run_pipeline_reference": re.compile(r"run_pipeline\.py"),
        "root_next_recipe_reference": re.compile(
            r"stage1_optimization[\\/]+output[\\/]+next_experiment_recipe\.json"
        ),
        "legacy_history_db_reference": re.compile(r"campaign_memory[\\/]+history_db\.json"),
        "fixed_stage3_output_reference": re.compile(r"outputs[\\/]+stage3[\\/]"),
    }
    hits: dict[str, list[dict[str, Any]]] = {key: [] for key in patterns}
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for key, pattern in patterns.items():
                if pattern.search(line):
                    hits[key].append(
                        {
                            "path": _rel(path),
                            "line": lineno,
                            "text": line.strip()[:240],
                        }
                    )
    return hits


def build_report() -> dict[str, Any]:
    stage1 = audit_stage1_recipe()
    llm = audit_llm_config()
    stage2 = audit_stage2_seed()
    stage3 = audit_stage3_manifests(stage2["sha256"])
    feedback = audit_experimental_feedback()
    stage3_artifacts = audit_stage3_current_artifacts(stage3)
    scans = scan_mainline_text()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(PROJECT_ROOT),
        "stage1_recipe": stage1,
        "llm_config": llm,
        "stage2_seed": stage2,
        "stage3_manifests": stage3,
        "experimental_feedback": feedback,
        "stage3_current_artifacts": stage3_artifacts,
        "scans": scans,
        "summary": {
            "stage1_recipe_valid": stage1["schema_valid"],
            "llm_keys_present": (
                llm["stage1_key"]["present"] and llm["stage3_key"]["present"]
            ),
            "stage3_model_aligned": llm["models_aligned"],
            "stage2_ready": stage2["stage3_ready"] is True and not stage2["warnings"],
            "stage3_manifest_matches_current_seed": bool(stage3["matching_current_stage2_seed"]),
            "feedback_schema_valid_or_absent": feedback["schema_valid"] in {True, None},
            "latest_robustness_present": stage3_artifacts.get("ranking_robustness", {}).get("exists") is True,
            "claim_audit_paths_relative": stage3_artifacts.get("claim_audit", {}).get("claim_paths_relative") is True,
            "possible_api_key_hits": len(scans["possible_api_key"]),
            "run_pipeline_reference_hits": len(scans["run_pipeline_reference"]),
            "root_next_recipe_reference_hits": len(scans["root_next_recipe_reference"]),
            "legacy_history_db_reference_hits": len(scans["legacy_history_db_reference"]),
            "fixed_stage3_output_reference_hits": len(scans["fixed_stage3_output_reference"]),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Mainline Audit Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- project_root: `{report['project_root']}`",
        "",
        "## Summary",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Stage1 Recipe"])
    for key, value in report["stage1_recipe"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## LLM Config"])
    lines.append(
        "- `stage1_key`: "
        f"present=`{report['llm_config']['stage1_key']['present']}`, "
        f"length=`{report['llm_config']['stage1_key']['length']}`, "
        f"sha12=`{report['llm_config']['stage1_key']['sha256_prefix']}`"
    )
    lines.append(
        "- `stage3_key`: "
        f"present=`{report['llm_config']['stage3_key']['present']}`, "
        f"length=`{report['llm_config']['stage3_key']['length']}`, "
        f"sha12=`{report['llm_config']['stage3_key']['sha256_prefix']}`"
    )
    lines.append(f"- `stage1_model`: `{report['llm_config']['stage1_model']}`")
    lines.append(f"- `stage3_models`: `{report['llm_config']['stage3_models']}`")
    lines.append(f"- `models_aligned`: `{report['llm_config']['models_aligned']}`")
    lines.extend(["", "## Stage2 Seed"])
    for key, value in report["stage2_seed"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Stage3 Manifests"])
    lines.append(
        f"- matching_current_stage2_seed: `{len(report['stage3_manifests']['matching_current_stage2_seed'])}`"
    )
    for row in report["stage3_manifests"]["latest_manifests"][:5]:
        lines.append(f"- `{row['path']}` seed=`{row.get('stage2_seed_sha256')}`")
    lines.extend(["", "## Experimental Feedback"])
    for key, value in report["experimental_feedback"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Stage3 Current Artifacts"])
    artifacts = report["stage3_current_artifacts"]
    lines.append(f"- `output_dir`: `{artifacts.get('output_dir')}`")
    lines.append(f"- `robustness`: `{artifacts.get('ranking_robustness')}`")
    lines.append(f"- `validation_binding`: `{artifacts.get('validation_binding')}`")
    lines.append(f"- `claim_audit`: `{artifacts.get('claim_audit')}`")
    lines.extend(["", "## Scan Counts"])
    for key, rows in report["scans"].items():
        lines.append(f"- `{key}`: `{len(rows)}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only project mainline audit")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if not args.no_write:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        stem = datetime.now().strftime("%Y%m%d_%H%M%S_mainline_audit")
        (args.report_dir / f"{stem}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (args.report_dir / f"{stem}.md").write_text(
            render_markdown(report),
            encoding="utf-8",
        )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
