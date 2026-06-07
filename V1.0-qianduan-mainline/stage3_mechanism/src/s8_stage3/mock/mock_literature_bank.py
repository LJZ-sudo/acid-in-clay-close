"""Mock 文献库 — 用于 mock 模式下的 S05/S08。

注意：以下均为 mock 文献摘要，不是真实文献。真实联网检索由 literature/providers 实现。
"""

from __future__ import annotations

from s8_stage3.contracts.literature import LiteratureCard


def get_mechanism_literature() -> list[LiteratureCard]:
    """返回机理侧 mock 文献卡片（用于 S05）。"""
    return [
        LiteratureCard(
            card_id="ML1",
            title="Proton transport in acid-polymer hydrogels: Grotthuss vs. vehicle mechanism",
            authors="Mock, A.; Test, B.",
            year=2021,
            doi="10.0000/mock-ml1",
            summary=(
                "Studies of PA-PVA systems show that Grotthuss-type proton hopping dominates "
                "below 270K, while vehicular transport becomes significant above 280K. "
                "The transition temperature correlates with H-bond network restructuring."
            ),
            relevance_to_mechanism="Supports H-bond network threshold hypothesis",
            supports_hypothesis_ids=["H1", "H4"],
        ),
        LiteratureCard(
            card_id="ML2",
            title="Temperature-dependent EIS of proton-conducting membranes",
            authors="Mock, C.",
            year=2020,
            doi="10.0000/mock-ml2",
            summary=(
                "EIS arc disappearance near 260-270K in PA-containing membranes "
                "is consistent with grain boundary contribution becoming negligible. "
                "The effect is heuristic and does not uniquely determine mechanism."
            ),
            relevance_to_mechanism="Contextual support for T_arc interpretation (heuristic only)",
            supports_hypothesis_ids=["H2"],
        ),
        LiteratureCard(
            card_id="ML3",
            title="Cooperative rearrangement in supercooled acid-water networks",
            authors="Mock, D.; Test, E.",
            year=2022,
            doi="10.0000/mock-ml3",
            summary=(
                "VTF behavior in acid-water mixtures suggests cooperative segmental motion "
                "as rate-limiting step above glass transition."
            ),
            relevance_to_mechanism="Supports VTF / cooperative rearrangement hypothesis",
            supports_hypothesis_ids=["H3"],
        ),
    ]


def get_materials_literature() -> list[LiteratureCard]:
    """返回材料侧 mock 文献卡片（用于 S08）。"""
    return [
        LiteratureCard(
            card_id="MAT1",
            title="Polysaccharide-based proton exchange membranes: a review",
            authors="Mock, F.",
            year=2021,
            doi="10.0000/mock-mat1",
            summary=(
                "OH-rich polysaccharide matrices provide dense H-bond networks suitable "
                "for Grotthuss-type proton transport. Starch derivatives show wide-temperature "
                "stability when combined with strong acid dopants."
            ),
            relevance_to_descriptors="Matches: OH-rich host, dense H-bond network",
        ),
        LiteratureCard(
            card_id="MAT2",
            title="Clay-polymer composite membranes for proton conduction",
            authors="Mock, G.; Test, H.",
            year=2020,
            doi="10.0000/mock-mat2",
            summary=(
                "1D clay nanorods (e.g., attapulgite-type) as scaffold provide confined "
                "acid-water channels, enhancing proton conductivity while reducing leakage risk."
            ),
            relevance_to_descriptors="Matches: hydrated 1D scaffold, low leakage risk",
        ),
        LiteratureCard(
            card_id="MAT3",
            title="High-amylose starch matrices with tuneable OH density for proton conductors",
            authors="Mock, I.",
            year=2023,
            doi="10.0000/mock-mat3",
            summary=(
                "High-amylose starch matrices exhibit high OH-density and moderate crystallinity, "
                "enabling strong acid anchoring with minimal leakage. Composites with "
                "H3PO4 show Arrhenius behaviour below 270K."
            ),
            relevance_to_descriptors="Matches: OH-rich host, moderate acid anchoring, low leakage",
        ),
    ]
