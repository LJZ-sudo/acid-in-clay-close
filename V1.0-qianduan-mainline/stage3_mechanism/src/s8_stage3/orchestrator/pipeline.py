from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepResult:
    step_id: str
    status: StepStatus
    error: Optional[str] = None


@dataclass
class Pipeline:
    settings: object
    gateway: object
    output_dir: Path
    run_mode: str = "mock"
    literature_mode: str = "mock"
    until_step: str = ""
    max_samples: Optional[int] = None
    sample_ids: Optional[list[str]] = None
    manual_strict: bool = False
    stage2_output_dir: Optional[Path] = None
    allow_legacy_atlas: bool = False
    strict_real_input: bool = False
    stage2_input_metadata: dict = field(default_factory=dict)
    step_results: list[StepResult] = field(default_factory=list)
    agent_trace: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_mock(self):
        from s8_stage3.mock.mock_seed_factory import create_mock_seed_bundle

        self.run_mode = "mock"
        seed = create_mock_seed_bundle()
        return self.run_from_seed(seed)

    def run_real(self):
        from s8_stage3.adapters.input_resolver import resolve_inputs
        from s8_stage3.adapters.stage2_seed_adapter import build_seed_bundle_from_stage2
        from s8_stage3.io.writers import write_json

        self.run_mode = "real"
        inputs = resolve_inputs(
            stage2_output_dir=self.stage2_output_dir,
            allow_legacy_atlas=self.allow_legacy_atlas,
        )
        self.strict_real_input = inputs.strict_real_input
        self.stage2_input_metadata = {
            "stage2_input_dir": str(inputs.input_dir),
            "stage2_seed_path": str(inputs.stage2_seed_v2_path) if inputs.stage2_seed_v2_path else None,
            "strict_real_input": inputs.strict_real_input,
            "allow_legacy_atlas": inputs.allow_legacy_atlas,
            "input_source": inputs.input_source,
        }
        bundle, diagnostics = build_seed_bundle_from_stage2(
            csv_path=inputs.csv_path,
            data_profile_path=inputs.data_profile_path,
            execution_plan_path=inputs.execution_plan_path,
            atlas_path=inputs.atlas_path,
            visualization_manifest_path=inputs.visualization_manifest_path,
            max_samples=self.max_samples,
            sample_ids=self.sample_ids,
            stage1_campaign_path=inputs.stage1_campaign_path,
            stage2_seed_v2_path=inputs.stage2_seed_v2_path,
            strict_real_input=inputs.strict_real_input,
            allow_legacy_atlas=inputs.allow_legacy_atlas,
        )
        self.stage2_input_metadata["adapter_warning_count"] = len(bundle.adapter_warnings)
        self.stage2_input_metadata["stage2_seed_sha256"] = (
            diagnostics.get("stage2_seed_v2_sha256")
            or (diagnostics.get("input_hashes") or {}).get("stage2_seed_v2")
        )

        seed_dir = self.output_dir / "00_seed_real"
        write_json(seed_dir / "seed_bundle_real.json", bundle)
        write_json(seed_dir / "real_seed_diagnostics.json", diagnostics)
        write_json(seed_dir / "adapter_warnings.json", {"warnings": bundle.adapter_warnings})
        return self.run_from_seed(bundle)

    def run_from_seed(self, seed):
        seed = self._apply_sampling(seed)
        self._prepare_seed_digest(seed)
        self._run_source_term_audit()

        steps = self._resolve_steps()
        lit_cache = self._build_literature_cache()

        from s8_stage3.agents.s03_evidence_builder import run_s03
        from s8_stage3.agents.s04_hypothesis_generator import run_s04
        from s8_stage3.agents.s05_literature_scout_mechanism import run_s05
        from s8_stage3.agents.s06_mechanism_arbiter import run_s06
        from s8_stage3.agents.s06b_design_principle_extractor import run_s06b
        from s8_stage3.agents.s07_descriptor_extractor import run_s07
        from s8_stage3.agents.s08_literature_scout_materials import run_s08
        from s8_stage3.agents.s09_candidate_family_generator import run_s09
        from s8_stage3.agents.s10_instance_ranker import run_s10
        from s8_stage3.agents.s11_report_compiler import run_s11
        from s8_stage3.agents.s12_prospective_registry import run_s12
        from s8_stage3.agents.s13_validation_binder import run_s13
        from s8_stage3.agents.s14_claim_auditor import run_s14

        evidence = None
        hypothesis_board = None
        mechanism_lit = None
        arbitration = None
        descriptor_sheet = None
        material_lit = None
        family_set = None
        instance_set = None
        ranking = None

        for step_id in steps:
            trace_entry = {
                "step": step_id,
                "status": StepStatus.RUNNING.value,
                "output_hashes": {},
                "guardrail_warnings": [],
            }
            self.step_results.append(StepResult(step_id, StepStatus.RUNNING))
            try:
                if step_id == "s03_evidence_builder":
                    evidence = run_s03(seed, self.output_dir, strict_real_input=self.strict_real_input)
                    trace_entry["guardrail_warnings"].extend(
                        self._run_guardrails("s03", evidence.model_dump(mode="json"))
                    )
                elif step_id == "s04_hypothesis_generator":
                    hypothesis_board = run_s04(
                        evidence,
                        self.gateway,
                        self.output_dir,
                        system_context=seed.system_context,
                    )
                    trace_entry["guardrail_warnings"].extend(
                        self._run_guardrails("s04", hypothesis_board.model_dump(mode="json"))
                    )
                elif step_id == "s05_literature_scout_mechanism":
                    mechanism_lit = run_s05(
                        hypothesis_board,
                        self.gateway,
                        self.output_dir,
                        literature_mode=self.literature_mode,
                        lit_cache=lit_cache,
                        settings=self.settings,
                        manual_strict=self.manual_strict,
                    )
                elif step_id == "s06_mechanism_arbiter":
                    arbitration = run_s06(
                        evidence,
                        mechanism_lit,
                        self.gateway,
                        self.output_dir,
                        hypothesis_board=hypothesis_board,
                        system_context=seed.system_context,
                    )
                elif step_id == "s06b_design_principle_extractor":
                    self._design_principles = run_s06b(
                        arbitration,
                        evidence,
                        self.gateway,
                        self.output_dir,
                        system_context=seed.system_context,
                    )
                elif step_id == "s07_descriptor_extractor":
                    descriptor_sheet = run_s07(arbitration, self.gateway, self.output_dir)
                    trace_entry["guardrail_warnings"].extend(
                        self._run_guardrails("s07", descriptor_sheet.model_dump(mode="json"))
                    )
                elif step_id == "s08_literature_scout_materials":
                    material_lit = run_s08(
                        descriptor_sheet,
                        self.gateway,
                        self.output_dir,
                        literature_mode=self.literature_mode,
                        lit_cache=lit_cache,
                        settings=self.settings,
                        manual_strict=self.manual_strict,
                    )
                elif step_id == "s09_candidate_family_generator":
                    material_lit = self._inject_design_principles(material_lit)
                    family_set, instance_set = run_s09(
                        descriptor_sheet,
                        material_lit,
                        self.gateway,
                        self.output_dir,
                        system_context=seed.system_context,
                        settings=self.settings,
                    )
                elif step_id == "s10_instance_ranker":
                    ranking = run_s10(
                        instance_set,
                        arbitration,
                        material_lit,
                        self.gateway,
                        self.output_dir,
                        system_context=seed.system_context,
                        settings=self.settings,
                    )
                elif step_id == "s12_prospective_registry":
                    self._prospective_registry = run_s12(
                        ranking,
                        instance_set,
                        self.output_dir,
                        self.settings,
                        top_n=int(getattr(self.settings, "prospective_top_n", 5) or 5),
                        force_reset=bool(getattr(self.settings, "prospective_force_reset", False)),
                    )
                elif step_id == "s13_validation_binder":
                    registry = getattr(self, "_prospective_registry", None)
                    if registry is not None:
                        self._validation_report = run_s13(registry, self.output_dir, self.settings)
                elif step_id == "s14_claim_auditor":
                    run_s14(self.output_dir, self.settings)
                elif step_id == "s11_report_compiler":
                    run_s11(
                        evidence,
                        arbitration,
                        family_set,
                        instance_set,
                        ranking,
                        self.gateway,
                        self.output_dir,
                        settings=self.settings,
                    )

                self.step_results[-1].status = StepStatus.COMPLETED
                trace_entry["status"] = StepStatus.COMPLETED.value
                trace_entry["output_hashes"] = self._collect_output_hashes()
                self.agent_trace.append(trace_entry)
            except Exception as exc:
                self.step_results[-1].status = StepStatus.FAILED
                self.step_results[-1].error = str(exc)
                trace_entry["status"] = StepStatus.FAILED.value
                trace_entry["error"] = str(exc)
                self.agent_trace.append(trace_entry)
                self._write_cost_summary()
                self._write_run_manifest()
                raise

        self._write_cost_summary()
        self._write_run_manifest()
        return {
            "evidence": evidence,
            "hypothesis_board": hypothesis_board,
            "mechanism_arbitration": arbitration,
            "descriptor_sheet": descriptor_sheet,
            "ranking": ranking,
        }

    def _apply_sampling(self, seed):
        if self.sample_ids:
            wanted = set(self.sample_ids)
            seed.seed_sample_summaries = [s for s in seed.seed_sample_summaries if s.sample_id in wanted]
            seed.seed_segments = [s for s in seed.seed_segments if s.sample_id in wanted]
            seed.seed_composition_nodes = [
                node for node in seed.seed_composition_nodes if any(sid in wanted for sid in node.sample_ids)
            ]
        elif self.max_samples:
            keep = {s.sample_id for s in seed.seed_sample_summaries[: self.max_samples]}
            seed.seed_sample_summaries = seed.seed_sample_summaries[: self.max_samples]
            seed.seed_segments = [s for s in seed.seed_segments if s.sample_id in keep]
            seed.seed_composition_nodes = [
                node for node in seed.seed_composition_nodes if any(sid in keep for sid in node.sample_ids)
            ]
        return seed

    def _prepare_seed_digest(self, seed) -> None:
        from s8_stage3.io.writers import write_json
        from s8_stage3.pre_llm.seed_sanitizer import (
            format_sanitizer_warnings_for_prompt,
            sanitize_seed,
        )

        digest = sanitize_seed(seed)
        self._sanitizer_warnings = format_sanitizer_warnings_for_prompt(digest)
        write_json(self.output_dir / "00_sanitizer_digest.json", digest)

    def _run_source_term_audit(self) -> None:
        if not bool(getattr(self.settings, "candidate_term_audit", True)):
            return
        from s8_stage3.validation.source_term_auditor import audit_candidate_terms

        stage3_root = Path(__file__).resolve().parents[3]
        audit_candidate_terms(
            stage3_root=stage3_root,
            output_dir=self.output_dir,
            discovery_mode=str(getattr(self.settings, "discovery_mode", "broad_literature_pool_selection")),
            final_audit=bool(getattr(self.settings, "final_audit", False)),
        )

    def _build_literature_cache(self):
        if not bool(getattr(self.settings, "enable_cache", False)):
            return None
        from s8_stage3.literature.cache import LiteratureCache

        return LiteratureCache(self.settings.cache_dir)

    def _inject_design_principles(self, material_lit):
        dp = getattr(self, "_design_principles", None)
        if material_lit is None or dp is None or not getattr(dp, "principles", None):
            return material_lit
        lines = ["\n\nTransferable Design Principles (S06b):"]
        for principle in dp.principles:
            lines.append(
                f"- [{principle.principle_id}] {principle.principle_type}: "
                f"{principle.transferable_rule[:200]}"
            )
        material_lit.synthesis_notes = (material_lit.synthesis_notes or "") + "\n".join(lines)
        return material_lit

    def _run_guardrails(self, step_id: str, data: dict) -> list[dict]:
        try:
            from s8_stage3.validation.no_leakage_checker import check_leakage

            return check_leakage(step_id, data)
        except Exception:
            return []

    def _resolve_steps(self) -> list[str]:
        from s8_stage3.orchestrator.state_machine import steps_until, validate_step_order

        steps = steps_until(self.until_step)
        violations = validate_step_order(steps)
        if violations:
            raise RuntimeError("Invalid Stage3 step order: " + "; ".join(violations))
        return steps

    def _collect_output_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        if not self.output_dir.exists():
            return hashes
        for path in sorted(self.output_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md"}:
                continue
            try:
                rel = str(path.relative_to(self.output_dir)).replace("\\", "/")
                hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
            except Exception:
                continue
        return hashes

    def _ranking_robustness_manifest(self) -> dict:
        path = self.output_dir / "09_ranking" / "ranking_robustness_v2.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "status": data.get("status") or "ok",
                "stability_class": data.get("stability_class"),
                "top1_stability_rate": data.get("top1_stability_rate"),
                "top3_jaccard_mean": data.get("top3_jaccard_mean"),
                "recommended_wording_hint": data.get("recommended_wording_hint"),
            }
        except Exception as exc:
            return {"path": str(path), "error": str(exc)}

    def _write_run_manifest(self) -> None:
        try:
            from s8_stage3.config.prompt_registry import prompt_manifest
        except Exception:
            prompt_manifest = lambda: []

        manifest = {
            "run_mode": self.run_mode,
            "literature_mode": self.literature_mode,
            "output_dir": str(self.output_dir),
            "selected_steps": [row.step_id for row in self.step_results],
            "until_step": self.until_step,
            "max_samples": self.max_samples,
            "sample_ids": self.sample_ids,
            "manual_strict": self.manual_strict,
            "stage2_input": self.stage2_input_metadata,
            "stage2_input_dir": self.stage2_input_metadata.get("stage2_input_dir"),
            "stage2_seed_path": self.stage2_input_metadata.get("stage2_seed_path"),
            "stage2_seed_sha256": self.stage2_input_metadata.get("stage2_seed_sha256"),
            "strict_real_input": self.stage2_input_metadata.get("strict_real_input"),
            "adapter_warning_count": self.stage2_input_metadata.get("adapter_warning_count"),
            "settings": {
                "llm_mode": getattr(self.settings, "llm_mode", None),
                "model_tier": getattr(self.settings, "model_tier", None),
                "enable_cache": getattr(self.settings, "enable_cache", None),
                "llm_temperature": getattr(self.settings, "llm_temperature", None),
                "llm_seed": getattr(self.settings, "llm_seed", 0) or None,
                "use_structured_outputs": getattr(self.settings, "use_structured_outputs", None),
            },
            "prompt_manifest": prompt_manifest(),
            "step_results": [
                {"step": row.step_id, "status": row.status.value, "error": row.error}
                for row in self.step_results
            ],
            "ranking_robustness": self._ranking_robustness_manifest(),
            "agent_trace": self.agent_trace,
            "output_hashes": self._collect_output_hashes(),
        }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.output_dir / "agent_trace.json").write_text(
            json.dumps(self.agent_trace, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_cost_summary(self) -> None:
        if not hasattr(self.gateway, "get_cost_summary"):
            return
        try:
            summary = self.gateway.get_cost_summary()
            (self.output_dir / "llm_cost_summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("Failed to write cost summary", exc_info=True)
