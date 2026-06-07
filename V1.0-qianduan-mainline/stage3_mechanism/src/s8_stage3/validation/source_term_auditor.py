from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from s8_stage3.contracts.discovery import (
    ALLOWED_CLAIM_BY_MODE,
    CLAIM_STRENGTH_BY_MODE,
    FORBIDDEN_CLAIM_BY_MODE,
)


@dataclass
class CandidateAuditResult:
    target_candidate_group: str
    discovery_mode: str
    allowed_before_s09: list[str]
    n_hits_total: int
    first_hit: Optional[dict] = None
    hits: list[dict] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)
    allowed_claim_strength: str = "unknown"
    allowed_claim: str = ""
    forbidden_claim: str = ""


_TEXT_EXTENSIONS = {".py", ".md", ".json", ".jsonl", ".yaml", ".yml", ".txt", ".csv"}

_STAGE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"src[\\/]s8_stage3[\\/]prompts"), "prompts"),
    (re.compile(r"src[\\/]s8_stage3[\\/]contracts"), "contracts"),
    (re.compile(r"src[\\/]s8_stage3[\\/]mock"), "mock"),
    (re.compile(r"data[\\/]cache"), "cache"),
    (re.compile(r"literature_workspace"), "literature_workspace"),
    (re.compile(r"06_literature_materials"), "s08_literature_scout_materials"),
    (re.compile(r"07_material_families"), "s09_candidate_family_generator"),
    (re.compile(r"08_material_instances"), "s09_candidate_family_generator"),
    (re.compile(r"09_ranking"), "s10_instance_ranker"),
    (re.compile(r"10_reports"), "s11_report_compiler"),
    (re.compile(r"11_candidate_registry"), "s12_prospective_registry"),
    (re.compile(r"12_validation_binding"), "s13_validation_binding"),
    (re.compile(r"13_claim_audit"), "s14_claim_audit"),
    (re.compile(r"audit[\\/]candidate_terms"), "audit/candidate_terms"),
    (re.compile(r"data[\\/]validation"), "validation_data"),
    (re.compile(r"user_candidates"), "user_candidates"),
]

_ALWAYS_ALLOWED_STAGES = {
    "audit/candidate_terms",
    "validation_data",
    "cache",
    "s09_candidate_family_generator",
    "s10_instance_ranker",
    "s11_report_compiler",
    "s12_prospective_registry",
    "s13_validation_binding",
    "s14_claim_audit",
}

_EXCLUDED_FILENAMES = {
    "source_term_auditor.py",
    "source_term_audit.json",
    "discovery.py",
    "claim_audit.py",
    "prospective.py",
    "validation.py",
    "design_principle.py",
}

_EXCLUDED_DIR_FRAGMENTS = (
    "audit/candidate_terms",
    "audit\\candidate_terms",
    "outputs/archive",
    "outputs\\archive",
    "data/cache/archive",
    "data\\cache\\archive",
)

_GUARDRAIL_LINE_PATTERNS = (
    re.compile(r"\bdo not claim\b", re.IGNORECASE),
    re.compile(r"\bmust not claim\b", re.IGNORECASE),
    re.compile(r"\bforbidden[_ -]?overclaim\b", re.IGNORECASE),
    re.compile(r"\bguardrail\b", re.IGNORECASE),
    re.compile(r"\bcounter[- ]?example\b", re.IGNORECASE),
)


def _stage_label_for_path(path: Path) -> str:
    text = str(path)
    for pattern, label in _STAGE_PATTERNS:
        if pattern.search(text):
            return label
    return "other"


def _is_excluded(path: Path) -> bool:
    text = str(path)
    if path.name in _EXCLUDED_FILENAMES:
        return True
    return any(fragment in text for fragment in _EXCLUDED_DIR_FRAGMENTS)


def _is_guardrail_line(line: str) -> bool:
    return any(pattern.search(line or "") for pattern in _GUARDRAIL_LINE_PATTERNS)


def _iter_text_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in _TEXT_EXTENSIONS:
                files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in _TEXT_EXTENSIONS and not _is_excluded(path):
                files.append(path)
    return files


def _build_term_pattern(terms: list[str]) -> re.Pattern[str]:
    parts = [re.escape(term) for term in sorted(set(terms), key=len, reverse=True) if term]
    return re.compile("|".join(parts), re.IGNORECASE)


def _scan_file(path: Path, pattern: re.Pattern[str]) -> list[dict]:
    hits: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line_number, line in enumerate(handle, start=1):
                match = pattern.search(line)
                if not match:
                    continue
                excerpt = line.strip()[:240]
                if _is_guardrail_line(excerpt):
                    continue
                hits.append(
                    {
                        "term": match.group(0),
                        "stage": _stage_label_for_path(path),
                        "path": str(path),
                        "line_number": line_number,
                        "line_excerpt": excerpt,
                    }
                )
    except OSError:
        pass
    return hits


def _parse_simple_yaml(text: str) -> dict:
    result: dict = {"terms": [], "allowed_sources_by_mode": {}}
    current_list: list[str] | None = None
    current_mode: str | None = None
    in_allowed_before = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("target_candidate_group:"):
            result["target_candidate_group"] = stripped.split(":", 1)[1].strip().strip('"')
            continue
        if stripped == "terms:":
            current_list = result["terms"]
            current_mode = None
            in_allowed_before = False
            continue
        if stripped == "allowed_sources_by_mode:":
            current_list = None
            current_mode = None
            in_allowed_before = False
            continue
        if raw.startswith("  ") and not raw.startswith("    ") and stripped.endswith(":"):
            current_mode = stripped[:-1]
            result["allowed_sources_by_mode"].setdefault(current_mode, {})
            in_allowed_before = False
            current_list = None
            continue
        if stripped.startswith("allowed_before_s09:") and current_mode:
            result["allowed_sources_by_mode"][current_mode]["allowed_before_s09"] = []
            current_list = result["allowed_sources_by_mode"][current_mode]["allowed_before_s09"]
            in_allowed_before = True
            if "[]" in stripped:
                current_list = None
                in_allowed_before = False
            continue
        if stripped.startswith("- "):
            value = stripped[2:].strip().strip('"').strip("'")
            if current_list is not None:
                current_list.append(value)
    return result


def load_term_definition(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    return _parse_simple_yaml(text)


def audit_candidate_terms(
    *,
    stage3_root: Path,
    output_dir: Path,
    discovery_mode: str = "broad_literature_pool_selection",
    final_audit: bool = False,
    candidate_term_files: Optional[list[Path]] = None,
) -> dict[str, CandidateAuditResult]:
    stage3_root = Path(stage3_root)
    output_dir = Path(output_dir)
    if candidate_term_files is None:
        term_dir = stage3_root / "audit" / "candidate_terms"
        candidate_term_files = sorted(term_dir.glob("*.yaml")) if term_dir.exists() else []
    if not candidate_term_files:
        return {}

    scan_roots = [
        stage3_root / "src" / "s8_stage3" / "prompts",
        stage3_root / "src" / "s8_stage3" / "contracts",
        stage3_root / "src" / "s8_stage3" / "mock",
        stage3_root / "data" / "cache" / "current",
        stage3_root / "data" / "validation",
        stage3_root / "literature_workspace",
        output_dir,
    ]
    files = _iter_text_files(scan_roots)

    results: dict[str, CandidateAuditResult] = {}
    for term_file in candidate_term_files:
        spec = load_term_definition(term_file)
        group = str(spec.get("target_candidate_group") or term_file.stem)
        terms = [str(term) for term in (spec.get("terms") or []) if str(term).strip()]
        if not terms:
            continue
        mode_cfg = (spec.get("allowed_sources_by_mode") or {}).get(discovery_mode, {})
        allowed_before = list(mode_cfg.get("allowed_before_s09") or [])
        pattern = _build_term_pattern(terms)
        hits: list[dict] = []
        for file_path in files:
            hits.extend(_scan_file(file_path, pattern))
        allowed = set(allowed_before) | _ALWAYS_ALLOWED_STAGES
        violations = [hit for hit in hits if hit["stage"] not in allowed]
        results[group] = CandidateAuditResult(
            target_candidate_group=group,
            discovery_mode=discovery_mode,
            allowed_before_s09=allowed_before,
            n_hits_total=len(hits),
            first_hit=hits[0] if hits else None,
            hits=hits,
            violations=violations,
            allowed_claim_strength=CLAIM_STRENGTH_BY_MODE.get(discovery_mode, "unknown"),
            allowed_claim=ALLOWED_CLAIM_BY_MODE.get(discovery_mode, ""),
            forbidden_claim=FORBIDDEN_CLAIM_BY_MODE.get(discovery_mode, ""),
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "discovery_mode": discovery_mode,
        "final_audit": final_audit,
        "stage3_root": str(stage3_root),
        "output_dir": str(output_dir),
        "scan_roots": [str(path) for path in scan_roots],
        "groups": {name: asdict(result) for name, result in results.items()},
    }
    (output_dir / "source_term_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if final_audit:
        offenders = {name: result for name, result in results.items() if result.violations}
        if offenders:
            detail = "; ".join(
                f"{name}: {len(result.violations)} violation(s)"
                for name, result in offenders.items()
            )
            raise RuntimeError(f"[source_term_auditor] final_audit=True and violations found: {detail}")
    return results
