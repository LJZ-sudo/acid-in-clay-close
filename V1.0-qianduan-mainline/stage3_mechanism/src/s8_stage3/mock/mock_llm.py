"""Mock LLM — 提供与真实 gateway 格式一致的 mock 响应，用于 mock 模式下测试。

响应按 step 名称分发。输出格式必须与对应 contract 一致。
"""

from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, Callable] = {}


def register_mock(step_name: str):
    def decorator(fn: Callable) -> Callable:
        _REGISTRY[step_name] = fn
        return fn
    return decorator


def mock_chat_json(step: str, messages: list[dict]) -> dict:
    """根据 step 名称分发 mock 响应。"""
    # 精确匹配
    if step in _REGISTRY:
        return _REGISTRY[step](messages)
    # Longer keys first so s06b does not get swallowed by the shorter s06 mock.
    for key, fn in sorted(_REGISTRY.items(), key=lambda item: len(item[0]), reverse=True):
        if key in step:
            return fn(messages)
    # fallback
    return {"mock": True, "step": step, "note": "no mock registered for this step"}


# ---------------------------------------------------------------------------
# S04 Hypothesis Generator
# ---------------------------------------------------------------------------

@register_mock("s04")
def _mock_s04(messages: list[dict]) -> dict:
    return {
        "step_id": "s04_hypotheses",
        "hypotheses": [
            {
                "hypothesis_id": "H1",
                "mechanism_label": "Piecewise-Arrhenius Grotthuss with single H-bond threshold",
                "description": "Proton transport via H-bond network restructuring with a single threshold near T_break.",
                "key_prediction": "Two Arrhenius regimes separated at T_break; EIS arc persists only below T_arc.",
                "mechanism_axes": {
                    "transport": "Grotthuss_hopping",
                    "phase_structure": "single_continuous_phase",
                    "temperature_dependence": "piecewise_Arrhenius",
                    "transition_topology": "single_transition",
                },
                "supporting_evidence_ids": ["E1", "E2"],
                "conflicting_evidence_ids": [],
                "prior_plausibility": 0.55,
            },
            {
                "hypothesis_id": "H2",
                "mechanism_label": "Single percolation threshold with vehicular step-up",
                "description": "Conductive phase percolates at a single temperature, producing a step-change in vehicular transport.",
                "key_prediction": "Step-change in conductivity near T_break; weak T_arc/T_break coupling.",
                "mechanism_axes": {
                    "transport": "vehicular_diffusion",
                    "phase_structure": "single_percolation_threshold",
                    "temperature_dependence": "piecewise_Arrhenius",
                    "transition_topology": "single_transition",
                },
                "supporting_evidence_ids": ["E3"],
                "conflicting_evidence_ids": ["E2"],
                "prior_plausibility": 0.35,
            },
            {
                "hypothesis_id": "H3",
                "mechanism_label": "Cooperative VTF above Tg, no sharp transition",
                "description": "Cooperative segmental motion governs proton mobility; σ(T) is smooth with no distinct transition.",
                "key_prediction": "VTF fit dominates throughout the range; T_break is a fit artifact.",
                "mechanism_axes": {
                    "transport": "vehicular_diffusion",
                    "phase_structure": "single_continuous_phase",
                    "temperature_dependence": "VTF",
                    "transition_topology": "no_transition",
                },
                "supporting_evidence_ids": ["E4"],
                "conflicting_evidence_ids": ["E1"],
                "prior_plausibility": 0.30,
            },
            {
                "hypothesis_id": "H4",
                "mechanism_label": "Multi-threshold confined acid-water reconnection",
                "description": "Multiple connectivity transitions of confined acid-water domains produce several Ea regimes.",
                "key_prediction": "More than one Ea break; EIS arc and conductivity transitions decouple in temperature.",
                "mechanism_axes": {
                    "transport": "hybrid_grotthuss_vehicular",
                    "phase_structure": "multi_threshold_confined_domains",
                    "temperature_dependence": "Arrhenius_with_MeyerNeldel_coupling",
                    "transition_topology": "multi_transition",
                },
                "supporting_evidence_ids": ["E1", "E3", "E4"],
                "conflicting_evidence_ids": [],
                "prior_plausibility": 0.65,
            },
        ],
        "reasoning_notes": (
            "Four competing hypotheses differing on transport (Grotthuss vs vehicular vs hybrid), "
            "phase_structure (continuous vs percolation vs multi-threshold confined), and transition_topology "
            "(no/single/multi)."
        ),
    }


# ---------------------------------------------------------------------------
# S05 Literature Scout (Mechanism)
# ---------------------------------------------------------------------------

@register_mock("s05")
def _mock_s05(messages: list[dict]) -> dict:
    return {
        "step_id": "s05",
        "survey_scope": "mechanism_constraint",
        "cards": [
            {
                "card_id": "ML1",
                "title": "Grotthuss proton hopping in acid hydrogels",
                "authors": "Mock A, Test B",
                "year": 2021,
                "doi": "10.0000/mock-ml1",
                "summary": "Grotthuss mechanism dominant below 270K in PA-polymer systems.",
                "relevance_to_mechanism": "Supports H1 and H4",
                "supports_hypothesis_ids": ["H1", "H4"],
                "weakens_hypothesis_ids": [],
            },
            {
                "card_id": "ML2",
                "title": "EIS arc temperature dependence",
                "authors": "Mock C",
                "year": 2020,
                "doi": "10.0000/mock-ml2",
                "summary": "EIS arc disappearance near T_arc is heuristic.",
                "relevance_to_mechanism": "Context only for T_arc interpretation",
                "supports_hypothesis_ids": ["H2"],
                "weakens_hypothesis_ids": [],
            },
        ],
        "synthesis_notes": "H1 and H4 have strongest literature support; EIS evidence is heuristic only.",
    }


# ---------------------------------------------------------------------------
# S06 Mechanism Arbiter
# ---------------------------------------------------------------------------

@register_mock("s06")
def _mock_s06(messages: list[dict]) -> dict:
    return {
        "step_id": "s06_mechanism",
        "mechanism_card": {
            "selected_hypothesis_id": "H4",
            "mechanism_label": "Multi-threshold confined acid-water H-bond reconnection",
            "justification": (
                "H4 best accounts for the multiple Ea regimes, T_arc < T_break offset, "
                "and wide-temperature behavior observed across samples."
            ),
            "confidence": 0.72,
            "evidence_alignment": [
                "E1: wide T range with two distinct Ea regimes",
                "E3: T_arc consistently below T_break",
                "E4: Arrhenius better than VTF in low-T regime",
            ],
            "literature_support": [
                "ML1: Grotthuss hopping supports low-T Arrhenius regime",
                "ML2: EIS arc disappearance contextually consistent (heuristic)",
            ],
            "t_arc_t_break_explanation": (
                "T_arc reflects the disappearance of grain-boundary impedance arc (interface effect), "
                "while T_break marks restructuring of bulk H-bond network. "
                "These probe different physical processes and can differ by 5-15K."
            ),
            "eis_evolution_explanation": (
                "On cooling, the dominant relaxation time of the bulk H-bond network enters the "
                "measurement frequency window (mechanism (a)), while a slower interfacial / bound-water "
                "process that was dynamically averaged out at room T becomes resolved as a distinct "
                "semicircle (mechanism (b)). At room T only the low-frequency linear tail is visible."
            ),
            "caveats": [
                "EIS interpretation is heuristic and non-unique",
                "VTF vs Arrhenius discrimination requires broader T range",
            ],
            "rejected_hypotheses": [
                "H2 rejected: insufficient evidence for single sharp percolation threshold",
                "H3 partially rejected: VTF not dominant in low-T regime",
            ],
            "why_not": [
                "H2: would have explained composition-driven jumps better only if a single dominant threshold existed; observed multi-jump pattern argues against it",
                "H3: would have explained a continuous VTF trend better than the observed piecewise Arrhenius — none identified for the low-T regime",
            ],
        },
        "arbitration_method": "evidence_consistency + literature_weight + eis_evolution_check",
    }


# ---------------------------------------------------------------------------
# S06b Design Principle Extractor
# ---------------------------------------------------------------------------

@register_mock("s06b")
def _mock_s06b(messages: list[dict]) -> dict:
    return {
        "step_id": "s06b_transfer_principles",
        "principles": [
            {
                "principle_id": "P1",
                "principle_type": "proton_source",
                "acid_in_clay_origin": "E1/E3 indicate conductivity is sustained when the confined acid-water network remains connected.",
                "transferable_rule": "Use a hydrated acid phase that supplies mobile protons while remaining coupled to a hydrogen-bond-rich host.",
                "target_material_descriptor": "phosphoric-acid-containing proton donor embedded in an OH-rich host matrix",
                "required_validation": ["wide-temperature EIS", "acid loading reproducibility"],
                "failure_modes": ["acid dilution causing low carrier density", "excess acid leakage"],
                "evidence_ids": ["E1", "E3"],
                "mechanism_links": ["H4_acid_water_reconnection"],
            },
            {
                "principle_id": "P2",
                "principle_type": "confinement_geometry",
                "acid_in_clay_origin": "E3/E4 support a confined-domain mechanism rather than unrestricted bulk acid behavior.",
                "transferable_rule": "Introduce a nanoscale or fibrous confinement element that limits bulk acid crystallisation and preserves interfacial proton pathways.",
                "target_material_descriptor": "1D or high-aspect-ratio inorganic scaffold with hydrated interfacial sites",
                "required_validation": ["filler dispersion imaging", "thickness-normalised conductivity"],
                "failure_modes": ["filler aggregation", "loss of continuous conduction pathway"],
                "evidence_ids": ["E3", "E4"],
                "mechanism_links": ["H4_confined_network"],
            },
            {
                "principle_id": "P3",
                "principle_type": "bound_water_network",
                "acid_in_clay_origin": "The selected mechanism separates confined mobile populations from bulk-like frozen populations.",
                "transferable_rule": "Retain bound water and hydrogen-bond donor/acceptor density so the proton network does not collapse in the cold window.",
                "target_material_descriptor": "OH-rich polymer or biopolymer matrix with retained bound water below 273 K",
                "required_validation": ["low-temperature EIS", "DSC or mass-retention check"],
                "failure_modes": ["bulk water freezing", "dry brittle matrix"],
                "evidence_ids": ["E1", "E4"],
                "mechanism_links": ["H4_low_T_Grotthuss"],
            },
            {
                "principle_id": "P4",
                "principle_type": "failure_mode_control",
                "acid_in_clay_origin": "Multi-segment Arrhenius behavior marks overfilling and low-temperature degradation risk.",
                "transferable_rule": "Treat low-temperature Ea excess and new Arrhenius breakpoints as hard warning signals for overfilling, freezing, or disconnected acid domains.",
                "target_material_descriptor": "composition window that minimizes Ea_low excess while maintaining room-temperature conductivity",
                "required_validation": ["segmented Arrhenius analysis", "repeat sample at the same composition"],
                "failure_modes": ["overfilled bulk acid phase", "composition-sensitive brittleness"],
                "evidence_ids": ["E1", "E3", "E4"],
                "mechanism_links": ["H4_multi_threshold"],
            },
        ],
        "migration_summary": (
            "The acid-in-clay mechanism transfers as a set of design rules: keep a connected "
            "hydrated proton source, add nanoscale confinement, retain bound water, and use "
            "low-temperature Ea excess as a failure-mode guardrail."
        ),
    }


# ---------------------------------------------------------------------------
# S07 Descriptor Extractor
# ---------------------------------------------------------------------------

@register_mock("s07")
def _mock_s07(messages: list[dict]) -> dict:
    return {
        "step_id": "s07_descriptors",
        "descriptors": [
            {
                "descriptor_id": "D1",
                "descriptor_text": "OH-rich host matrix with dense H-bond donor/acceptor sites operable from 182 K to 299 K",
                "mechanism_role": "Provides cold-side proton hopping backbone",
                "required_material_features": ["high OH density", "hydrophilic", "sub-zero bound water"],
                "priority": "critical",
                "derived_from_mechanism": "H4_low_T_Grotthuss",
            },
            {
                "descriptor_id": "D2",
                "descriptor_text": "Acid anchor sites with moderate retention capacity, resistant to sub-273 K crystallisation",
                "mechanism_role": "Maintains mobile proton source across the cold-to-room-T window",
                "required_material_features": ["acid affinity", "low leakage", "no sub-zero crystallisation"],
                "priority": "critical",
                "derived_from_mechanism": "H4_acid_water_reconnection",
            },
            {
                "descriptor_id": "D3",
                "descriptor_text": "Hydrated 1D scaffold or fibrous filler providing nanometric channel confinement",
                "mechanism_role": "Confines cold-side proton conduction pathway",
                "required_material_features": ["1D morphology", "water retention"],
                "priority": "important",
                "derived_from_mechanism": "H4_confined_network",
            },
            {
                "descriptor_id": "D4",
                "descriptor_text": "Cold-to-room-T matrix continuity: no sharp freezing/crystallisation phase transition inside 182–299 K",
                "mechanism_role": "Preserves conduction pathway down to ~182 K; anti-freeze co-solvent or low-Tg matrix",
                "required_material_features": ["no phase transition 182–299 K", "low-Tg or plasticised matrix"],
                "priority": "critical",
                "derived_from_mechanism": "H4_cold_side_requirement",
            },
            {
                "descriptor_id": "D5",
                "descriptor_text": "Low ionic leakage risk under operational humidification across cold-to-room T",
                "mechanism_role": "Prevents acid loss degrading long-term cold-side conductivity",
                "required_material_features": ["low acid vapor pressure", "crosslinking capability"],
                "priority": "important",
                "derived_from_mechanism": "H4_stability",
            },
        ],
        "extraction_notes": "Five descriptors derived from H4 mechanism; explicitly cold-side-oriented (window 182–299 K).",
    }


# ---------------------------------------------------------------------------
# S08 Literature Scout (Materials)
# ---------------------------------------------------------------------------

@register_mock("s08")
def _mock_s08(messages: list[dict]) -> dict:
    return {
        "step_id": "s08",
        "survey_scope": "material_search",
        "cards": [
            {
                "card_id": "MAT1",
                "title": "Polysaccharide-based proton exchange membranes",
                "authors": "Mock F",
                "year": 2021,
                "doi": "10.0000/mock-mat1",
                "summary": "OH-rich polysaccharides enable Grotthuss transport.",
                "relevance_to_descriptors": "D1, D2",
                "component_descriptor_claims": [
                    {
                        "component": "starch",
                        "descriptor_ids": ["D1"],
                        "quantitative_anchor": "OH density ~11 mmol/g",
                        "claim_text": "starch provides dense OH H-bond donor sites (MAT1).",
                        "confidence": "supported",
                    },
                    {
                        "component": "phosphoric acid (H3PO4)",
                        "descriptor_ids": ["D2"],
                        "quantitative_anchor": "σ ~ 10 mS/cm at 298 K",
                        "claim_text": "H3PO4 supplies mobile protons retained by the matrix (MAT1).",
                        "confidence": "supported",
                    },
                ],
                "supports_hypothesis_ids": [],
                "weakens_hypothesis_ids": [],
            },
            {
                "card_id": "MAT2",
                "title": "Clay-polymer composite membranes",
                "authors": "Mock G, Test H",
                "year": 2020,
                "doi": "10.0000/mock-mat2",
                "summary": "1D clay scaffolds reduce leakage risk.",
                "relevance_to_descriptors": "D3, D4, D5",
                "component_descriptor_claims": [
                    {
                        "component": "attapulgite",
                        "descriptor_ids": ["D3", "D5"],
                        "quantitative_anchor": "1-D tubular channel width ~3.7 Å",
                        "claim_text": "attapulgite supplies 1-D confined proton channels with interfacial acid retention (MAT2).",
                        "confidence": "supported",
                    },
                    {
                        "component": "PVA",
                        "descriptor_ids": ["D4"],
                        "quantitative_anchor": "Tg ~ 85 °C, film-forming",
                        "claim_text": "PVA compatibilises the clay/acid matrix and resists sub-zero brittleness when plasticised (MAT2).",
                        "confidence": "supported",
                    },
                ],
                "supports_hypothesis_ids": [],
                "weakens_hypothesis_ids": [],
            },
            {
                "card_id": "MAT3",
                "title": "OH-rich polysaccharide matrix for proton-conducting membranes",
                "authors": "Mock I",
                "year": 2023,
                "doi": "10.0000/mock-mat3",
                "summary": "OH-rich polysaccharide matrix study covering D1, D2, D4 descriptors (glycerol plasticiser).",
                "relevance_to_descriptors": "D1, D2, D4",
                "component_descriptor_claims": [
                    {
                        "component": "glycerol",
                        "descriptor_ids": ["D4"],
                        "quantitative_anchor": "anti-freeze plasticiser, Tg depression ~40 K",
                        "claim_text": "glycerol suppresses sub-zero freezing of the polysaccharide+acid matrix (MAT3).",
                        "confidence": "supported",
                    },
                    {
                        "component": "starch",
                        "descriptor_ids": ["D1"],
                        "quantitative_anchor": "",
                        "claim_text": "starch provides OH-rich H-bond donor sites (MAT3).",
                        "confidence": "supported",
                    },
                ],
                "supports_hypothesis_ids": [],
                "weakens_hypothesis_ids": [],
            },
        ],
        "synthesis_notes": "Three family-level literature groups identified matching descriptors D1-D5, with D4 (cold-side) covered mainly by glycerol-plasticised polysaccharide systems and 1-D clay anchoring.",
    }


@register_mock("s08_summarize_batch")
def _mock_s08_summarize_batch(messages: list[dict]) -> dict:
    return {
        "synthesis_notes": (
            "Mock S08 batch synthesis: polysaccharide, phosphoric acid, PVA, "
            "plasticiser, and 1-D clay evidence provide component-level descriptor support."
        ),
        "component_descriptor_claims_by_card": {
            "MAT1": [
                {
                    "component": "starch",
                    "descriptor_ids": ["D1"],
                    "quantitative_anchor": "OH-rich polysaccharide backbone",
                    "claim_text": "Starch supplies dense OH H-bond donor/acceptor sites.",
                    "confidence": "supported",
                },
                {
                    "component": "H3PO4",
                    "descriptor_ids": ["D2"],
                    "quantitative_anchor": "strong acid dopant",
                    "claim_text": "Phosphoric acid supplies mobile protons retained by the matrix.",
                    "confidence": "supported",
                },
            ],
            "MAT2": [
                {
                    "component": "attapulgite",
                    "descriptor_ids": ["D3", "D5"],
                    "quantitative_anchor": "1-D clay scaffold",
                    "claim_text": "Attapulgite-like 1-D clay provides confinement and leakage control.",
                    "confidence": "supported",
                },
                {
                    "component": "PVA",
                    "descriptor_ids": ["D4"],
                    "quantitative_anchor": "film-forming polymer matrix",
                    "claim_text": "PVA improves matrix continuity and processability.",
                    "confidence": "supported",
                },
            ],
            "MAT3": [
                {
                    "component": "starch",
                    "descriptor_ids": ["D1", "D4"],
                    "quantitative_anchor": "high-amylose starch matrix",
                    "claim_text": "High-amylose starch supports OH-rich and cold-side matrix continuity descriptors.",
                    "confidence": "supported",
                },
                {
                    "component": "glycerol",
                    "descriptor_ids": ["D4"],
                    "quantitative_anchor": "plasticiser / freezing suppression motif",
                    "claim_text": "Glycerol-like plasticisation supports cold-window continuity.",
                    "confidence": "supported",
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# S09 Candidate Family Generator
# ---------------------------------------------------------------------------

@register_mock("s09")
def _mock_s09(messages: list[dict]) -> dict:
    return {
        "families": [
            {
                "family_id": "F1",
                "family_name": "OH-rich polysaccharide + strong acid",
                "family_description": "Starch/cellulose-class matrix doped with phosphoric or sulfuric acid",
                "descriptor_match": ["D1: high OH density", "D2: moderate acid anchoring", "D5: low leakage"],
                "literature_support_card_ids": ["MAT1", "MAT3"],
            },
            {
                "family_id": "F2",
                "family_name": "1D clay + polymer + acid",
                "family_description": "Fibrous clay scaffold embedded in polymer matrix with acid doping",
                "descriptor_match": ["D3: 1D confinement", "D4: thermal stability", "D5: low leakage"],
                "literature_support_card_ids": ["MAT2"],
            },
        ],
        "instances": [
            {
                "instance_id": "I1",
                "family_id": "F1",
                "instance_name": "Crosslinked PAAm-g-starch / H3PO4 hydrogel (literature baseline)",
                "composition_description": (
                    "PAAm-graft-starch network crosslinked with MBA; H3PO4 imbibed from aqueous solution. "
                    "Matches the MAT1 formulation; retained as control baseline."
                ),
                "components": [
                    "polyacrylamide-graft-starch network",
                    "phosphoric acid (H3PO4)",
                    "N,N'-methylenebisacrylamide (MBA)",
                ],
                "expected_properties": [
                    "conductivity_range: 1e-2 to 1e-1 S/cm after drying",
                    "acid_retention: high (3D network)",
                ],
                "risk_flags": ["brittleness after drying", "amide hydrolysis under prolonged heat"],
                "combination_novelty": "exact_match",
                "element_evidence": [
                    {
                        "component": "polyacrylamide-graft-starch network",
                        "role_in_formulation": "OH-rich 3D host + bound-population carrier",
                        "descriptor_satisfied": ["D1", "D4"],
                        "analog_paper_ids": ["MAT1"],
                        "analog_reason": "MAT1 reports exactly this crosslinked PAAm-g-starch + H3PO4 system",
                    },
                    {
                        "component": "phosphoric acid (H3PO4)",
                        "role_in_formulation": "mobile proton donor",
                        "descriptor_satisfied": ["D2", "D3"],
                        "analog_paper_ids": ["MAT1", "MAT3"],
                        "analog_reason": "H3PO4 proton conduction well established in both cards",
                    },
                ],
                "literature_support_card_ids": ["MAT1", "MAT3"],
                "novelty_rationale": (
                    "Control baseline: this formulation is essentially the MAT1 system. It is retained "
                    "to anchor the Top-list in a measured literature reference point, not because it "
                    "represents a new combination."
                ),
            },
            {
                "instance_id": "I2",
                "family_id": "F1",
                "instance_name": "biomass-starch-A / PVA / H3PO4 / 1D-clay composite membrane",
                "composition_description": (
                    "Biomass starch placeholder (OH-rich host) + PVA (film-forming compatibiliser) + "
                    "H3PO4 (proton donor) + attapulgite (1-D clay channel). No single literature card "
                    "reports this exact formulation; each component has an element-level analog."
                ),
                "components": [
                    "biomass-starch-A (placeholder)",
                    "poly(vinyl alcohol) (PVA)",
                    "phosphoric acid (H3PO4)",
                    "attapulgite (1-D clay)",
                ],
                "expected_properties": [
                    "conductivity_range: 1e-3 to 3e-2 S/cm at 200-340K",
                    "acid_retention: high (OH + 1-D channel synergy)",
                ],
                "risk_flags": ["batch variability of biomass", "acid-assisted hydrolysis of starch domain"],
                "combination_novelty": "novel_combination",
                "element_evidence": [
                    {
                        "component": "biomass-starch-A (placeholder)",
                        "role_in_formulation": "dense OH H-bond host + bound-population carrier",
                        "descriptor_satisfied": ["D1", "D4"],
                        "analog_paper_ids": ["MAT-biomass-A", "MAT3"],
                        "analog_reason": "MAT-biomass-A characterises the biomass placeholder; MAT3 establishes starch+H3PO4 conduction",
                    },
                    {
                        "component": "poly(vinyl alcohol) (PVA)",
                        "role_in_formulation": "film-forming compatibiliser, reduces host crystallinity",
                        "descriptor_satisfied": ["D2"],
                        "analog_paper_ids": ["MAT-pva"],
                        "analog_reason": "PVA/starch hydrogen bonding suppresses PVA crystallinity",
                    },
                    {
                        "component": "phosphoric acid (H3PO4)",
                        "role_in_formulation": "mobile proton donor",
                        "descriptor_satisfied": ["D3"],
                        "analog_paper_ids": ["MAT1", "MAT3"],
                        "analog_reason": "Standard proton carrier in literature-backed PA-PEM systems",
                    },
                    {
                        "component": "attapulgite (1-D clay)",
                        "role_in_formulation": "nanometric 1-D confinement + interfacial acid retention",
                        "descriptor_satisfied": ["D5"],
                        "analog_paper_ids": ["MAT2"],
                        "analog_reason": "MAT2 reports 1-D attapulgite proton channel with acid immobilisation",
                    },
                ],
                "literature_support_card_ids": ["MAT-biomass-A", "MAT3", "MAT-pva", "MAT1", "MAT2"],
                "novelty_rationale": (
                    "The full four-component formulation is not reported in the S08 pool. Relative to "
                    "the closest exact match (MAT2: PVA+H3PO4+modified MMT), this route (i) swaps "
                    "layered MMT for 1-D attapulgite to exploit tubular rather than sheet confinement, "
                    "and (ii) introduces a second OH-rich bound-water biomass starch placeholder. "
                    "Each component carries its own element-level literature analog."
                ),
            },
            {
                "instance_id": "I3",
                "family_id": "F2",
                "instance_name": "High-amylose plant starch / PVA / H3PO4 / sepiolite composite",
                "composition_description": (
                    "High-amylose plant starch source + PVA + H3PO4 + sepiolite. Four-component "
                    "archetype analogous to I2 but with a controlled botanical starch source (lower "
                    "batch variability) and sepiolite in place of attapulgite."
                ),
                "components": [
                    "high-amylose plant starch (e.g., corn or potato)",
                    "poly(vinyl alcohol) (PVA)",
                    "phosphoric acid (H3PO4)",
                    "sepiolite (1-D fibrous clay)",
                ],
                "expected_properties": [
                    "conductivity_range: 5e-3 to 5e-2 S/cm across wide T",
                    "acid_retention: high (sepiolite + OH synergy)",
                ],
                "risk_flags": ["sepiolite dispersion at high loading"],
                "combination_novelty": "novel_combination",
                "element_evidence": [
                    {
                        "component": "high-amylose plant starch",
                        "role_in_formulation": "dense OH H-bond host, low-variability starch source",
                        "descriptor_satisfied": ["D1", "D4"],
                        "analog_paper_ids": ["MAT3"],
                        "analog_reason": "Starch+H3PO4 proton channel established in MAT3",
                    },
                    {
                        "component": "poly(vinyl alcohol) (PVA)",
                        "role_in_formulation": "film-forming compatibiliser",
                        "descriptor_satisfied": ["D2"],
                        "analog_paper_ids": ["MAT-pva"],
                        "analog_reason": "PVA/starch hydrogen bonding",
                    },
                    {
                        "component": "phosphoric acid (H3PO4)",
                        "role_in_formulation": "mobile proton donor",
                        "descriptor_satisfied": ["D3"],
                        "analog_paper_ids": ["MAT1"],
                        "analog_reason": "Standard proton carrier",
                    },
                    {
                        "component": "sepiolite (1-D fibrous clay)",
                        "role_in_formulation": "1-D channel + acid-in-clay confinement",
                        "descriptor_satisfied": ["D5"],
                        "analog_paper_ids": ["MAT-sep"],
                        "analog_reason": "Wide-T acid-in-sepiolite proton electrolyte",
                    },
                ],
                "literature_support_card_ids": ["MAT3", "MAT-pva", "MAT1", "MAT-sep"],
                "novelty_rationale": (
                    "The four-component combination is not reported as a unit in the S08 pool. It is the "
                    "least-variability cousin of I2 (replacing biomass-starch placeholder with controlled "
                    "high-amylose corn/potato starch, and attapulgite with sepiolite), designed for "
                    "clean mechanism verification before biomass optimisation."
                ),
            },
        ],
    }


# ---------------------------------------------------------------------------
# S10 Instance Ranker
# ---------------------------------------------------------------------------

@register_mock("s10")
def _mock_s10(messages: list[dict]) -> dict:
    return {
        "step_id": "s10_ranking",
        "ranked_candidates": [
            {
                "rank": 1,
                "instance_id": "I3",
                "instance_name": "High-amylose plant starch / PVA / H3PO4 / sepiolite composite",
                "total_score": 0.82,
                "criteria_scores": [
                    {"criterion_name": "mechanism_consistency", "score": 0.85, "weight": 1.5, "rationale": "D3+D4"},
                    {"criterion_name": "conductivity_potential", "score": 0.88, "weight": 1.0, "rationale": "1D confinement"},
                    {"criterion_name": "cold_to_room_T_robustness", "score": 0.80, "weight": 1.0, "rationale": "Bound water in 1-D sepiolite channel persists below 253 K; PVA matrix tolerates cold-side (方案 L)"},
                    {"criterion_name": "acid_retention", "score": 0.78, "weight": 1.0, "rationale": "Scaffold immobilises acid"},
                    {"criterion_name": "processability", "score": 0.70, "weight": 0.8, "rationale": "Dispersion challenging"},
                    {"criterion_name": "literature_analog_support", "score": 0.75, "weight": 1.0, "rationale": "MAT2"},
                    {"criterion_name": "risk_penalty", "score": 0.85, "weight": 1.0, "rationale": "Low leakage"},
                ],
                "ranking_rationale": "Best overall mechanism consistency and conductivity potential.",
                "combination_novelty": "novel_combination",
                "literature_support_card_ids": ["MAT3", "MAT-pva", "MAT1", "MAT-sep"],
                "novelty_rationale": (
                    "The four-component combination (high-amylose plant starch + PVA + H3PO4 + "
                    "sepiolite) is not reported as a unit in the S08 pool; it is the low-variability "
                    "cousin of the biomass route, with controlled starch source and a 1-D sepiolite "
                    "channel in place of attapulgite. Each component carries an element-level analog "
                    "in the S08 pool."
                ),
                "risk_summary": "Sepiolite dispersion may be challenging at scale.",
            },
            {
                "rank": 2,
                "instance_id": "I1",
                "instance_name": "Crosslinked PAAm-g-starch / H3PO4 hydrogel (literature baseline)",
                "total_score": 0.79,
                "criteria_scores": [
                    {"criterion_name": "mechanism_consistency", "score": 0.88, "weight": 1.5, "rationale": "D1+D2 match"},
                    {"criterion_name": "conductivity_potential", "score": 0.76, "weight": 1.0, "rationale": "OH-rich backbone"},
                    {"criterion_name": "cold_to_room_T_robustness", "score": 0.55, "weight": 1.0, "rationale": "Gel hydration retained but no explicit anti-freeze cosolvent; partial cold-side mitigation (方案 L)"},
                    {"criterion_name": "acid_retention", "score": 0.72, "weight": 1.0, "rationale": "Moderate retention"},
                    {"criterion_name": "processability", "score": 0.80, "weight": 0.8, "rationale": "Readily gelatinised"},
                    {"criterion_name": "literature_analog_support", "score": 0.80, "weight": 1.0, "rationale": "MAT3"},
                    {"criterion_name": "risk_penalty", "score": 0.75, "weight": 1.0, "rationale": "Leakage risk at high humidity"},
                ],
                "ranking_rationale": "Strong mechanism match; retained as control baseline.",
                "combination_novelty": "exact_match",
                "literature_support_card_ids": ["MAT1", "MAT3"],
                "novelty_rationale": (
                    "Control baseline: reproduces the MAT1 crosslinked PAAm-g-starch + H3PO4 system. "
                    "Included to anchor the Top-list in a known reference point."
                ),
                "risk_summary": "Acid leakage risk under high humidity conditions.",
            },
            {
                "rank": 3,
                "instance_id": "I2",
                "instance_name": "biomass-starch-A / PVA / H3PO4 / 1D-clay composite membrane",
                "total_score": 0.68,
                "criteria_scores": [
                    {"criterion_name": "mechanism_consistency", "score": 0.72, "weight": 1.5, "rationale": "D1 partial match"},
                    {"criterion_name": "conductivity_potential", "score": 0.65, "weight": 1.0, "rationale": "Lower OH density"},
                    {"criterion_name": "cold_to_room_T_robustness", "score": 0.70, "weight": 1.0, "rationale": "Biomass OH host + 1-D attapulgite bound water; PVA plasticisable for sub-zero (方案 L)"},
                    {"criterion_name": "acid_retention", "score": 0.65, "weight": 1.0, "rationale": "Moderate"},
                    {"criterion_name": "processability", "score": 0.80, "weight": 0.8, "rationale": "Easy"},
                    {"criterion_name": "literature_analog_support", "score": 0.60, "weight": 1.0, "rationale": "Limited direct support"},
                    {"criterion_name": "risk_penalty", "score": 0.70, "weight": 1.0, "rationale": "Moderate risk"},
                ],
                "ranking_rationale": "Four-component biomass route with highest novelty-weighted score.",
                "combination_novelty": "novel_combination",
                "literature_support_card_ids": ["MAT-biomass-A", "MAT3", "MAT-pva", "MAT1", "MAT2"],
                "novelty_rationale": (
                    "No S08 card reports this four-component biomass-starch / PVA / H3PO4 / 1D-clay unit. "
                    "Relative to MAT2 (PVA+H3PO4+modified MMT), this route swaps layered MMT for 1-D "
                    "attapulgite and adds a biomass OH-rich starch host, each carrying its own "
                    "element-level analog."
                ),
                "risk_summary": "Batch variability of biomass; needs clean-source baseline first.",
            },
        ],
        "ranking_notes": "I2 ranked #1 on novelty + mechanism synergy; I3 is a controlled cousin; I1 is the literature control baseline.",
    }


# ---------------------------------------------------------------------------
# S11 Report Compiler
# ---------------------------------------------------------------------------

@register_mock("s11")
def _mock_s11(messages: list[dict]) -> dict:
    return {
        "step_id": "s11_report",
        "title": "Stage 3 Mechanism & Materials Report (Mock Run)",
        "sections": [
            {
                "section_id": "S1",
                "title": "Evidence Summary",
                "content": (
                    "Proton transport data across 200-340K shows thermally-activated behavior "
                    "with at least two distinct Ea regimes per sample. EIS arc disappearance near "
                    "T_arc=255-268K is heuristic and does not uniquely determine mechanism."
                ),
                "subsections": [],
            },
            {
                "section_id": "S2",
                "title": "Proposed Mechanism",
                "content": (
                    "Working mechanism: Multi-threshold confined acid-water H-bond reconnection (H4). "
                    "T_arc reflects interface impedance transition; T_break reflects bulk H-bond "
                    "network restructuring. These probe different physical processes."
                ),
                "subsections": [],
            },
            {
                "section_id": "S3",
                "title": "Materials Top List",
                "content": (
                    "Top 3 candidates ranked by mechanism consistency and conductivity potential. "
                    "Rank 1: 1D-scaffold/OH-polymer/H3PO4. Rank 2: OH-polysaccharide/H3PO4. "
                    "Rank 3: alternative polysaccharide/H3PO4."
                ),
                "subsections": [],
            },
        ],
        "top_candidates_summary": [
            {"rank": 1, "name": "1D-scaffold/OH-polymer/H3PO4", "score": 0.82, "literature_support_card_ids": ["MAT2"]},
            {"rank": 2, "name": "OH-polysaccharide/H3PO4", "score": 0.79, "literature_support_card_ids": ["MAT1", "MAT3"]},
            {"rank": 3, "name": "Alternative polysaccharide/H3PO4", "score": 0.68, "literature_support_card_ids": ["MAT1"]},
        ],
        "eis_disclaimer": (
            "EIS morphology is heuristic only and does not uniquely determine mechanism. "
            "All EIS-based interpretations should be treated as contextual hints."
        ),
        "audit_trail": [
            {"step_id": "s03", "status": "completed", "notes": "Deterministic evidence extraction"},
            {"step_id": "s04", "status": "completed", "notes": "4 hypotheses generated"},
            {"step_id": "s05", "status": "completed", "notes": "2 mechanism literature cards"},
            {"step_id": "s06", "status": "completed", "notes": "H4 selected"},
            {"step_id": "s07", "status": "completed", "notes": "5 descriptors extracted"},
            {"step_id": "s08", "status": "completed", "notes": "3 material literature cards"},
            {"step_id": "s09", "status": "completed", "notes": "2 families, 3 instances"},
            {"step_id": "s10", "status": "completed", "notes": "3 ranked candidates"},
            {"step_id": "s11", "status": "completed", "notes": "Report compiled"},
        ],
    }
