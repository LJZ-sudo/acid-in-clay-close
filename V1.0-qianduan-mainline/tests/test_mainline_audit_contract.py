import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_audit_module():
    path = ROOT / "scripts" / "audit_mainline.py"
    spec = importlib.util.spec_from_file_location("audit_mainline", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_audit_report_contains_provenance_fields_without_plaintext_keys():
    audit = _load_audit_module()
    report = audit.build_report()

    assert "llm_config" in report
    assert "experimental_feedback" in report
    assert "stage3_current_artifacts" in report
    for key in [
        "llm_keys_present",
        "stage3_model_aligned",
        "feedback_schema_valid_or_absent",
        "latest_robustness_present",
        "claim_audit_paths_relative",
    ]:
        assert key in report["summary"]

    stage1_key = audit._read_env(audit.STAGE1_ENV).get("LLM_API_KEY", "")
    stage3_key = audit._read_env(audit.STAGE3_ENV).get("STAGE3_API_KEY", "")
    rendered = json.dumps(report, ensure_ascii=False)

    if stage1_key:
        assert stage1_key not in rendered
    if stage3_key:
        assert stage3_key not in rendered
    for marker in audit.LEGACY_ROOT_MARKERS:
        assert marker not in rendered
    assert "sha256_prefix" in rendered
    for row in report["stage3_manifests"]["latest_manifests"]:
        assert "stage2_seed_path" not in row
        assert "output_dir" not in row
        assert "stage2_seed_path_resolved" in row
        assert "output_dir_resolved" in row
    binding = report["stage3_current_artifacts"]["validation_binding"]
    assert "source_feedback_path" not in binding
    assert binding["source_feedback_path_resolved"] == "stage3_mechanism/data/validation/experimental_feedback.json"
