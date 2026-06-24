# Results · Discussion · Abstract — final draft (nature-writing style; no code/implementation names)

> ① 产物(2026-06-21)。承接 `MANUSCRIPT_INTRO_METHODS.md`。规范:每段首句点题、一段一意;
> 英式拼写;无缩写优先、首次定义;数值+空格+单位;范围 en-dash;**避免 prove/best/first/superior**;
> 负/null 结果如实写;不出现任何代码/文件名/内部管线名。所有数字均为真实结果。

---

## Abstract (final, ~210 words, Version 3 multi-contribution)

Autonomous and self-driving laboratories are usually demonstrated under rich structural
characterisation, yet most laboratories observe only an inexpensive transport probe. We ask what
an autonomous agent can credibly claim from electrochemical impedance data alone, and we make the
boundaries of those claims explicit in a family of biopolymer–clay–phosphoric-acid proton
conductors. First, using dense variable-temperature impedance across 13 independent repeats of
four material families, we establish a sub-zero proton-transport transition that is common to all
conducting families, with a break temperature between −22 and −39 °C, and whose sharpness is
tunable by composition; a lotus-root-starch family shows the sharpest transition with a
reproducible low-temperature activation energy of 0.69 ± 0.07 eV across seven repeats, whereas a
chitosan family forms a boundary case without a clean transition. Second, we measure the
fabrication reproducibility floor directly from independent repeats and show, under a
leave-one-dataset-out test, that single-curve quality control does not predict cross-sample
reproducibility (area under the receiver-operating curve ≈ 0.5), so reproducibility must be
certified by repeats, although a calibrator trained on repeats lowers the expected calibration
error from 0.78 to 0.13 (leave-one-dataset-out), chiefly by removing over-confidence. Third, a
structural-identifiability analysis shows that transport data
license descriptor-level but not mechanism-level claims. A closed optimisation loop is reported
as an honest null, with leading candidates separated by less than the reproducibility floor.

---

## 3. Results

### 3.1 A sub-zero proton-transport transition is common across families and tunable by composition

Dense variable-temperature impedance reveals a reproducible change in transport regime below
0 °C in every conducting composition we examined. Across 15 measured data sets spanning four
material families, 13 are described decisively by a segmented conductivity–temperature model with
a single dominant break, located between −22 and −39 °C, above which transport is nearly
athermal and below which it is thermally activated (Fig. 2). The break is therefore not a
property of one composition but a shared feature of the biopolymer–clay–acid family. The two
chitosan data sets do not support a clean two-regime description and are retained as a boundary
case, which indicates that the transition is characteristic of, but not universal to, every clay
composite.

The sharpness of the transition varies systematically with composition, which makes the
descriptor tunable rather than incidental. The lotus-root-starch family shows the sharpest
contrast between a near-athermal high-temperature regime and a strongly activated low-temperature
regime, with a mean high-temperature activation energy of 0.037 eV and a low-temperature
activation energy of 0.69 ± 0.07 eV reproduced across seven independent repeats; the starch
family shows a milder contrast, and the attapulgite host lies between them (Fig. 2). Ordering the
families by the ratio of low- to high-temperature activation energy yields a monotonic trend,
which we report as an empirical design rule relating composition to transition sharpness.

### 3.2 Independent repeats reveal a fabrication reproducibility floor

Repeating an identical composition as separately prepared discs exposes a reproducibility floor
that bounds every downstream claim. Across independent repeats, the conductivity at matched
temperatures reproduces to a median factor of about 1.8 for the standardised-thickness batch and
about 2.1 when earlier thinner discs are included, corresponding to 0.245 and 0.32 decades
respectively, and the floor is somewhat wider in the cold regime than in the warm regime. When
propagated into the scalar objective used for optimisation, the floor corresponds to 0.26–0.33
decades (Fig. 3a). This floor is a property of sample fabrication rather than of the
measurement, because the discs differ in pressed geometry and densification even when the
nominal composition is fixed.

### 3.3 Single-curve quality control does not predict cross-sample reproducibility

A central negative result is that the quality of a single spectrum carries little information
about whether that measurement will reproduce in an independent disc. Using the agreement of each
point with the consensus of the remaining repeats as the target, and evaluating predictors under
a leave-one-dataset-out protocol, the single-curve validity score discriminates reproducible from
non-reproducible points at an area under the receiver-operating curve of approximately 0.5, and
augmenting it with the resistance magnitude and temperature does not lift this value above chance
(Fig. 4). Reproducibility therefore cannot be certified from one spectrum and instead requires
independent repeats. The same repeats nevertheless support calibration: fitting an isotonic
mapping to the replication outcomes, evaluated leave-one-dataset-out, lowers the expected
calibration error from 0.78 to 0.13 and removes the over-confidence. This gain is one of
reliability—a re-centring of the reported confidence—rather than of resolution; the calibrated
score is trustworthy in aggregate but does not acquire new power to rank individual measurements
by reproducibility (Fig. 3b).

### 3.4 Transport data license descriptor-level but not mechanism-level claims

Transport data determine the descriptor but not the microscopic mechanism, which sets a ceiling
on admissible interpretation. The competitive model selection assigns essentially unit
probability to the transition model over single-regime and alternative two-regime descriptions,
so the descriptor—the transition temperature and the two activation energies—is recoverable from
the data (Fig. 5b). The mechanism is not: on the low-temperature branch of a representative dense
data set, simple thermally activated transport, three-dimensional variable-range hopping and a
Vogel–Tammann–Fulcher form describe the data within a difference in explained variance of 0.006
(Fig. 5a), so the conductivity response cannot select among physically distinct conduction
pictures. We therefore restrict conclusions to the descriptor level and treat mechanistic
statements as hypotheses rather than findings.

### 3.5 A closed optimisation loop returns an honest null bounded by the floor

A real optimisation loop, run prospectively with timestamped proposals, did not produce a
candidate that exceeds the previously measured optimum, and the outcome is interpretable in terms
of the reproducibility floor. Placing candidate-to-candidate differences in the scalar objective
on the same scale as the floor shows that the leading candidates differ by less than, or
comparable to, one floor width, so they are not reliably distinguishable from one another given
fabrication variability (Figs 3, 7). We report this as an honest null rather than as evidence of
failure: near the optimum the response surface is flatter than the reproducibility floor, which
quantitatively explains why additional rounds did not yield a distinguishable improvement.

### 3.6 Baselines and ablations

We benchmarked the optimisation and governance components against simpler alternatives, using the
existing data only. First, a strategy comparison on the ten-point source-system pool shows that a
plain Bayesian-optimisation strategy—a Gaussian-process surrogate with an upper-confidence-bound
selection rule—reaches the campaign optimum in 4.1 experiments on average, against 5.5 for random
selection, because the objective varies monotonically with the acid-loading parameter; surrogate
guidance therefore locates the optimum faster than chance (Fig. 7a). The same surrogate, optimised
without constraints over the design box, drives the proposal to the low-acid edge—matching the
recorded unconstrained optimiser proposal—at a composition that is not reliably synthesisable; the
language-model screening step returns the proposal to a feasible regime, the regime in which the
measured optimum actually lies (Fig. 7b). The value of the language-model arm is thus feasibility
and safety rather than an improved objective.

Second, ablating the credibility components confirms their roles. Replacing the calibrated
confidence with the raw single-curve score raises the expected calibration error from 0.13 to 0.78
and reintroduces severe over-confidence; a variance decomposition attributes the calibrated gain to
reliability (a re-centring of the reported confidence) rather than to resolution, consistent with
§3.3. A candidate-generation agent constrained by the evidence pool admitted none of a set of
high-citation, off-topic distractor materials, whereas a frequency-driven baseline admitted all of
them; a produce–critique–revise guardrail reduced an induced set of over-claims to zero; and an
independent cross-model blind assessment scored evidence-constrained candidates well above
frequency-driven ones. Taken together, the surrogate adds search efficiency, the language-model and
guardrail layers add feasibility and claim discipline, and none of these components crosses the
reproducibility floor—reinforcing, rather than contradicting, the honest-null reading.

---

## 4. Discussion

This work reframes autonomous discovery under restricted characterisation as a problem with two
measurable boundaries. A reproducibility floor bounds claims from below, and a structural
identifiability ceiling bounds them from above; both are obtained from the same transport data
used for discovery, and together they define the band within which an agent may make credible
statements. The strongest evidence for this framing is the combination of a composition-tunable
transition established over many independent repeats with a quantitative demonstration that the
mechanism is not recoverable from the same data.

The practical message is that reproducibility should be certified by independent repeats rather
than inferred from single-spectrum quality scores. Our leave-one-dataset-out result indicates
that single-curve confidence and cross-sample reproducibility are largely orthogonal in this
system, which cautions against trusting per-measurement confidence as a stand-in for
reproducibility in autonomous loops; the calibration that does work is the one trained on real
repeats. Reporting the closed-loop outcome as an honest null, rather than selecting a favourable
narrative, follows from the same principle.

Several limitations bound the scope of these conclusions. First, the study is transport-only by
design, so the mechanism of the transition remains a hypothesis; resolving it would require
structural or spectroscopic probes outside the present setting. Second, the reproducibility floor
is measured directly on the biopolymer families, whereas for the optimisation host it is used as
a proxy, because the prospective campaign did not include same-composition repeats; measuring the
host-system floor directly is the most immediate extension. Third, the optimisation trajectory is
short and its surrogate is weak, so we make no claim about convergence. Fourth, the
reproducibility-aware predictor is presently a negative result, which indicates that the features
available from a single spectrum are insufficient and that informative features would likely
require repeated or paired measurements. Finally, the material families are not themselves new;
the contribution is the descriptor and the explicit boundaries, not the chemistry.

A natural next step is to measure the host-system reproducibility floor directly and to make it
an explicit term in the acquisition decision, so that an autonomous loop allocates effort between
replication and exploration in a way that respects its own resolution. We expect the
floor-and-ceiling framing to transfer to other transport-limited, characterisation-frugal
settings, and to be useful wherever an autonomous agent must state not only what it found but
also what it is entitled to claim.
