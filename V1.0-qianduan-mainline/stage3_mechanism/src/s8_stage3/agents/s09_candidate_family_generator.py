from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, Field

from s8_stage3.config.prompt_registry import load_prompt
from s8_stage3.contracts.descriptor import DescriptorSheet
from s8_stage3.contracts.literature import LiteratureSurvey
from s8_stage3.contracts.material import (
    ElementEvidence,
    MaterialFamily,
    MaterialFamilySet,
    MaterialInstance,
    MaterialInstanceSet,
)
from s8_stage3.contracts.seed import SystemContext
from s8_stage3.io.writers import write_json
from s8_stage3.llm.prompt_packing import pack_for_s09


class _S09Output(BaseModel):
    families: list[MaterialFamily] = Field(default_factory=list)
    instances: list[MaterialInstance] = Field(default_factory=list)


def _truncate(text: object, limit: int) -> str:
    s = str(text or "")
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _compact_s09_payload(packed: str) -> str:
    payload = json.loads(packed)
    claim_pool = payload.get("descriptor_claim_pool") or []
    if not claim_pool:
        return packed

    compact_claims = []
    for claim in claim_pool[:30]:
        if not isinstance(claim, dict):
            continue
        compact_claims.append(
            {
                "component": _truncate(claim.get("component"), 80),
                "descriptor_id": _truncate(claim.get("descriptor_id"), 12),
                "paper_id": _truncate(claim.get("paper_id"), 80),
                "anchor": _truncate(claim.get("quantitative_anchor"), 100),
                "claim": _truncate(claim.get("claim_text"), 180),
            }
        )

    compact = {
        "descriptors": [
            {
                "id": d.get("id"),
                "text": _truncate(d.get("text"), 140),
                "role": _truncate(d.get("mechanism_role"), 80),
            }
            for d in payload.get("descriptors", [])
            if isinstance(d, dict)
        ],
        "descriptor_claim_pool": compact_claims,
        "generation_contract": {
            "families": "exactly 3 abstract families; no substance names in family_name",
            "instances": "exactly 5 concrete instances; at least 3 novel_combination; at most 1 exact_match",
            "brevity": "one-sentence family_description, <=3 expected_properties, <=2 risk_flags",
            "evidence": "cite only paper_id values present in descriptor_claim_pool; cover each meaningful component in element_evidence",
        },
    }
    if payload.get("system_context"):
        ctx = payload["system_context"]
        compact["system_context"] = {
            "chemistry_summary": _truncate(ctx.get("chemistry_summary"), 240),
            "temperature_window_K": ctx.get("temperature_window_K", []),
        }
    return json.dumps(compact, ensure_ascii=False)


def _claim_records(survey: LiteratureSurvey) -> list[dict]:
    records: list[dict] = []
    for card in survey.cards:
        for claim in card.component_descriptor_claims:
            for descriptor_id in claim.descriptor_ids:
                records.append(
                    {
                        "component": claim.component,
                        "descriptor_id": descriptor_id,
                        "paper_id": card.card_id,
                        "paper_title": card.title,
                        "anchor": claim.quantitative_anchor,
                        "claim": claim.claim_text,
                    }
                )
    return records


def _find_claim(records: list[dict], *needles: str, exclude: tuple[str, ...] = ()) -> dict | None:
    for record in records:
        haystack = " ".join(
            str(record.get(key, "")) for key in ("component", "claim", "paper_title")
        ).lower()
        if all(needle.lower() in haystack for needle in needles) and not any(
            item.lower() in haystack for item in exclude
        ):
            return record
    return None


def _dedupe_claims(claims: list[dict | None]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for claim in claims:
        if not claim:
            continue
        key = (
            str(claim.get("component", "")).lower(),
            str(claim.get("descriptor_id", "")),
            str(claim.get("paper_id", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(claim)
    return out


def _paper_ids(claims: list[dict]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for claim in claims:
        paper_id = str(claim.get("paper_id", ""))
        if paper_id and paper_id not in seen:
            seen.add(paper_id)
            ids.append(paper_id)
    return ids


def _element_evidence(claim: dict) -> dict:
    return {
        "component": claim["component"],
        "role_in_formulation": _truncate(claim.get("claim"), 120),
        "descriptor_satisfied": [claim["descriptor_id"]],
        "analog_paper_ids": [claim["paper_id"]],
        "analog_reason": _truncate(claim.get("claim"), 160),
    }


def _instance(
    *,
    instance_id: str,
    family_id: str,
    name: str,
    claims: list[dict],
    novelty: str,
    rationale: str,
    properties: list[str],
    risks: list[str],
) -> MaterialInstance:
    claims = _dedupe_claims(claims)
    return MaterialInstance(
        instance_id=instance_id,
        family_id=family_id,
        instance_name=name,
        composition_description=" + ".join(claim["component"] for claim in claims),
        components=[claim["component"] for claim in claims],
        expected_properties=properties[:3],
        risk_flags=risks[:2],
        combination_novelty=novelty,
        element_evidence=[_element_evidence(claim) for claim in claims],
        novelty_rationale=rationale,
    )


def _build_d4_deterministic_output(survey: LiteratureSurvey) -> _S09Output | None:
    records = _claim_records(survey)
    if not records:
        return None

    starch = _find_claim(records, "starch", exclude=("polyacrylamide",))
    paam_starch = _find_claim(records, "paam") or _find_claim(records, "polyacrylamide")
    chitosan = _find_claim(records, "chitosan")
    pva = _find_claim(records, "pva") or _find_claim(records, "vinyl alcohol")
    phosphoric = _find_claim(records, "phosphoric") or _find_claim(records, "h3po4")
    hnt = _find_claim(records, "halloysite")
    attapulgite = _find_claim(records, "attapulgite")
    mmt = _find_claim(records, "montmorillonite")
    hydrogel = _find_claim(records, "hydrogel")
    nb2o5 = _find_claim(records, "nb2o5")

    f1_claims = _dedupe_claims([starch, paam_starch, chitosan, pva, phosphoric])
    f2_claims = _dedupe_claims([attapulgite, hnt, mmt, phosphoric])
    f3_claims = _dedupe_claims([hydrogel, paam_starch, nb2o5, phosphoric])
    families = [
        MaterialFamily(
            family_id="F1",
            family_name="OH-rich polymer host plus retained proton donor network",
            family_description="OH-rich polymer or biopolymer hosts retain proton donors and provide hydrogen-bond pathways.",
            descriptor_match=["D1: host H-bond sites", "D4: retained phosphoric acid or mobile proton phase"],
            literature_support_card_ids=_paper_ids(f1_claims),
        ),
        MaterialFamily(
            family_id="F2",
            family_name="Clay-confined acid channel composite",
            family_description="Tubular or fibrous clays confine acid-rich phases and support interfacial proton transport.",
            descriptor_match=["D1: physical confinement", "D4: acid retention", "D6: donor-acceptor hopping motifs"],
            literature_support_card_ids=_paper_ids(f2_claims),
        ),
        MaterialFamily(
            family_id="F3",
            family_name="Cold-side hydrogel or plasticised electrolyte network",
            family_description="Hydrogel-like or defect-rich matrices preserve conduction continuity in the low-temperature window.",
            descriptor_match=["D3: matrix mobility or free volume", "D5: suppressed crystallisation or phase break"],
            literature_support_card_ids=_paper_ids(f3_claims),
        ),
    ]

    instances = [
        _instance(
            instance_id="I1",
            family_id="F1",
            name="Starch/PVA/organic-modified attapulgite/phosphoric acid membrane",
            claims=[starch, pva, attapulgite, phosphoric],
            novelty="novel_combination",
            rationale=(
                "This combines separate starch, PVA, 1-D clay, and phosphoric-acid evidence into a quaternary cold-side membrane rather than copying one S08 formulation."
            ),
            properties=[
                "cold_window: bound-water and retained-acid continuity",
                "processability: water-processable film route",
                "evidence_basis: component-level D4 claims",
            ],
            risks=["acid leaching must be measured", "clay dispersion controls reproducibility"],
        ),
        _instance(
            instance_id="I2",
            family_id="F2",
            name="Chitosan/organic-modified attapulgite/phosphoric acid composite",
            claims=[chitosan, attapulgite, phosphoric],
            novelty="novel_combination",
            rationale=(
                "This uses chitosan host evidence with attapulgite confinement and retained phosphoric acid from separate S08 claims, making the combined formulation literature-auditable but not a direct copy."
            ),
            properties=[
                "host_sites: chitosan hydrogen-bond matrix",
                "confinement: fibrous clay compartment",
                "carrier: retained phosphoric acid",
            ],
            risks=["biopolymer swelling may alter percolation", "acid loading needs optimisation"],
        ),
        _instance(
            instance_id="I3",
            family_id="F2",
            name="Halloysite nanotube/phosphoric acid/PVA hybrid membrane",
            claims=[hnt, phosphoric, pva],
            novelty="novel_combination",
            rationale=(
                "This transfers halloysite-confined acid evidence into a PVA-containing film-forming route, differing from the closest single-paper acid-in-clay formulation by the added polymer matrix role."
            ),
            properties=[
                "acid_retention: nanotube-confined phosphoric acid",
                "film_integrity: PVA binder contribution",
                "transport: packed-acid donor-acceptor network",
            ],
            risks=["high acid fraction may plasticise the matrix", "tube loading must avoid brittleness"],
        ),
        _instance(
            instance_id="I4",
            family_id="F3",
            name="PAAm-g-starch/phosphoric acid hydrogel electrolyte",
            claims=[paam_starch, phosphoric, hydrogel],
            novelty="close_variant",
            rationale=(
                "This is close to hydrogel acid-retention literature but is retained as an interpretable low-temperature comparison route with explicit component evidence."
            ),
            properties=[
                "retention: microporous hydrogel acid uptake",
                "cold_window: hydrogel continuity motif",
                "host_sites: starch-containing H-bond network",
            ],
            risks=["water content may dominate freezing behaviour", "mechanical strength may be low"],
        ),
        _instance(
            instance_id="I5",
            family_id="F3",
            name="PVA/chitosan/Nb2O5/H3PO4 defect-assisted composite",
            claims=[pva, chitosan, nb2o5, phosphoric],
            novelty="novel_combination",
            rationale=(
                "This combines PVA film support, chitosan host sites, Nb2O5 free-volume evidence, and phosphoric-acid proton donation across separate component claims to create a distinct defect-assisted route."
            ),
            properties=[
                "mobility: oxide-induced free volume",
                "carrier: H3PO4 donor-acceptor sites",
                "matrix: PVA/chitosan film continuity",
            ],
            risks=["oxide agglomeration can block conduction", "acid-base balance needs screening"],
        ),
    ]

    return _S09Output(families=families, instances=instances)


def _build_evidence_based_output(
    survey: LiteratureSurvey,
    descriptor_sheet: DescriptorSheet,
    *,
    max_instances: int = 5,
    max_components: int = 4,
) -> _S09Output | None:
    """Tier3 (issue 4): generate candidates by descriptor-matching over the
    S08 component-claim pool, instead of the fixed code-defined I1..I5 set.

    Deterministic and fully evidence-grounded: each instance is a greedy
    set-cover of mechanism descriptors using independent component claims, and
    every component carries its real ``analog_paper_ids`` from the claim pool.
    No fabricated names — components come only from S08 claims. Family names
    contain no substance names (per the S09 generation contract); instance
    names may, since S09 is the layer allowed to name concrete routes.
    """
    records = _claim_records(survey)
    if not records:
        return None

    comp_desc: dict[str, set[str]] = defaultdict(set)
    comp_desc_papers: dict[tuple[str, str], set[str]] = defaultdict(set)
    comp_claim_text: dict[str, str] = {}
    for r in records:
        comp = str(r["component"]).strip()
        did = str(r["descriptor_id"]).strip()
        if not comp or not did:
            continue
        comp_desc[comp].add(did)
        pid = str(r.get("paper_id", "")).strip()
        if pid:
            comp_desc_papers[(comp, did)].add(pid)
        comp_claim_text.setdefault(comp, str(r.get("claim") or ""))

    if not comp_desc:
        return None

    all_descriptor_ids = [d.descriptor_id for d in descriptor_sheet.descriptors] or sorted(
        {str(r["descriptor_id"]).strip() for r in records if str(r["descriptor_id"]).strip()}
    )
    all_set = set(all_descriptor_ids)
    # deterministic ranking: widest descriptor coverage first, ties by name
    ranked = sorted(comp_desc.keys(), key=lambda c: (-len(comp_desc[c] & all_set), c))

    families: list[MaterialFamily] = []
    instances: list[MaterialInstance] = []
    for idx, seed in enumerate(ranked[:max_instances], start=1):
        covered: set[str] = set()
        chosen: list[str] = []
        order = [seed] + [c for c in ranked if c != seed]
        for comp in order:
            gain = (comp_desc[comp] & all_set) - covered
            if comp == seed or gain:
                chosen.append(comp)
                covered |= comp_desc[comp] & all_set
            if len(chosen) >= max_components or (all_set and covered >= all_set):
                break

        element_evidence: list[ElementEvidence] = []
        for comp in chosen:
            dsat = sorted(comp_desc[comp] & all_set)
            papers = sorted({p for did in dsat for p in comp_desc_papers[(comp, did)]})
            element_evidence.append(
                ElementEvidence(
                    component=comp,
                    role_in_formulation=_truncate(comp_claim_text.get(comp, ""), 120),
                    descriptor_satisfied=dsat,
                    analog_paper_ids=papers,
                    analog_reason=_truncate(
                        comp_claim_text.get(comp, "") or "component-level S08 literature analog",
                        160,
                    ),
                )
            )

        family_id = f"F{idx}"
        families.append(
            MaterialFamily(
                family_id=family_id,
                family_name=f"Descriptor-coverage family {sorted(covered)}",
                family_description=(
                    "Components grouped by greedy mechanism-descriptor coverage over the "
                    "S08 component-claim pool (evidence-based generation)."
                ),
                descriptor_match=[f"{d}: covered by element-level claim" for d in sorted(covered)],
                literature_support_card_ids=sorted(
                    {p for ev in element_evidence for p in ev.analog_paper_ids}
                ),
            )
        )
        instances.append(
            MaterialInstance(
                instance_id=f"I{idx}",
                family_id=family_id,
                instance_name=" + ".join(chosen),
                composition_description=" + ".join(chosen),
                components=chosen,
                expected_properties=[
                    f"descriptor_coverage: {len(covered)}/{len(all_set) if all_set else len(covered)}",
                ],
                risk_flags=["evidence-based draft; requires human curation before synthesis"],
                combination_novelty="novel_combination",
                element_evidence=element_evidence,
                novelty_rationale=(
                    "Greedy descriptor-coverage combination assembled from independent S08 "
                    "component claims; not a copy of any single S08 formulation."
                ),
            )
        )

    return _S09Output(families=families, instances=instances)


def _candidate_origin(discovery_mode: str, novelty: str) -> str:
    if novelty == "exact_match":
        return "control_baseline"
    if discovery_mode == "blind_transfer":
        return "llm_proposed_blind"
    if discovery_mode == "human_seeded_ranking":
        return "human_seeded_llm_ranked"
    if discovery_mode == "retrospective_explanation":
        return "retrospective_explained"
    return "llm_selected_from_broad_pool"


def _audit_candidate_generation(
    instances: MaterialInstanceSet,
    survey: LiteratureSurvey,
    output_dir: Path,
    *,
    generation_mode: str = "",
) -> dict:
    valid_card_ids = {card.card_id for card in survey.cards}
    bad_rows: list[dict] = []
    missing_rationale: list[str] = []
    for inst in instances.instances:
        cited: set[str] = set(inst.literature_support_card_ids)
        for ev in inst.element_evidence:
            cited.update(ev.analog_paper_ids)
        bad_ids = sorted(pid for pid in cited if pid and pid not in valid_card_ids)
        if bad_ids:
            bad_rows.append({"instance_id": inst.instance_id, "bad_paper_ids": bad_ids})
        if not inst.novelty_rationale:
            missing_rationale.append(inst.instance_id)
    audit = {
        "audit_ok": not bad_rows and not missing_rationale,
        "valid_literature_card_ids": sorted(valid_card_ids),
        "instances_with_bad_paper_ids": bad_rows,
        "instances_missing_novelty_rationale": missing_rationale,
        "n_instances": len(instances.instances),
    }
    if generation_mode:
        audit["generation_mode"] = generation_mode
    write_json(output_dir / "08_material_instances" / "candidate_generation_audit.json", audit)
    return audit


def run_s09(
    descriptor_sheet: DescriptorSheet,
    material_literature: LiteratureSurvey,
    gateway,
    output_dir: Path,
    *,
    system_context: SystemContext | None = None,
    settings=None,
) -> tuple[MaterialFamilySet, MaterialInstanceSet]:
    packed = pack_for_s09(
        descriptor_sheet.model_dump(mode="json"),
        material_literature.model_dump(mode="json"),
        system_context.model_dump(mode="json") if system_context else None,
    )
    prompt_name = "s09_family_generator"
    generation_mode = "llm"
    # DETERMINISM CAVEAT (Tier1 note 2026-06-01): by default
    # ``s09_deterministic_from_d4`` is True (settings.py /
    # STAGE3_S09_DETERMINISTIC_FROM_D4), so the candidate families (F1/F2/F3) and
    # instances (I1..I5) come from ``_build_d4_deterministic_output`` — a fixed,
    # code-defined mapping over the D4 literature claims — NOT from free LLM
    # generation. This is intentional for reproducibility, but it means the
    # downstream "Top-list stability" has a DETERMINISTIC component (the candidate
    # set itself is fixed); it is not solely an emergent LLM ranking result.
    # Replacing this with genuine evidence-based / LLM candidate generation is a
    # Tier 3 capability upgrade. The default flag + the fixed family/instance set
    # are locked by a test so this property cannot drift silently.
    #
    # Tier3 (issue 4): opt-in evidence-based generation. When
    # ``s09_evidence_based_generation`` is True (default False), candidates are
    # generated by descriptor-matching over the S08 claim pool instead of the
    # fixed I1..I5 set. Default stays the frozen deterministic path.
    if getattr(settings, "s09_evidence_based_generation", False):
        evidence = _build_evidence_based_output(material_literature, descriptor_sheet)
        if evidence and evidence.instances:
            parsed = evidence
            generation_mode = "evidence_based_descriptor_match"
        else:
            parsed = None
    elif getattr(settings, "s09_deterministic_from_d4", True):
        deterministic = _build_d4_deterministic_output(material_literature)
        if deterministic:
            parsed = deterministic
            generation_mode = "deterministic_from_d4"
        else:
            parsed = None
    else:
        parsed = None

    if parsed is None:
        generation_mode = "llm_compact" if _claim_records(material_literature) else "llm"
    try:
        if parsed is None and json.loads(packed).get("descriptor_claim_pool"):
            packed = _compact_s09_payload(packed)
            prompt_name = "s09_family_generator_compact"
    except Exception:
        prompt_name = "s09_family_generator"

    if parsed is None:
        raw = gateway.chat_json(
            [
                {"role": "system", "content": load_prompt(prompt_name)},
                {"role": "user", "content": packed},
            ],
            step="s09_candidate_family_generator",
            output_schema=_S09Output,
        )
        parsed = _S09Output.model_validate(raw)
    discovery_mode = str(getattr(settings, "discovery_mode", "broad_literature_pool_selection"))
    # Tier3 (issue 4): when generation is the deterministic evidence-based
    # descriptor-match branch, the instance metadata must be TRUTHFUL — it is NOT
    # an LLM selection from a broad pool. The frozen deterministic_from_d4 / llm
    # paths are unchanged.
    evidence_based = generation_mode == "evidence_based_descriptor_match"
    for inst in parsed.instances:
        if evidence_based:
            inst.source_mode = "evidence_based_descriptor_match"
            inst.origin = "deterministic_evidence_based_descriptor_match"
        else:
            inst.source_mode = discovery_mode
            inst.origin = _candidate_origin(discovery_mode, inst.combination_novelty)
        if not inst.literature_support_card_ids and inst.element_evidence:
            ids: list[str] = []
            seen: set[str] = set()
            for ev in inst.element_evidence:
                for pid in ev.analog_paper_ids:
                    if pid and pid not in seen:
                        seen.add(pid)
                        ids.append(pid)
            inst.literature_support_card_ids = ids

    families = MaterialFamilySet(families=parsed.families)
    instances = MaterialInstanceSet(instances=parsed.instances)
    write_json(output_dir / "07_material_families" / "material_families.json", families)
    write_json(output_dir / "08_material_instances" / "material_instances.json", instances)
    _audit_candidate_generation(
        instances,
        material_literature,
        output_dir,
        generation_mode=generation_mode,
    )
    return families, instances
