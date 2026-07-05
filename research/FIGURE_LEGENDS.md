# Figure legends (journal-grade, ≤300 words each, British spelling, no code/implementation names)

> ③ 产物(2026-06-22)。套 `nature-figure` legend 规范:首句为图标题句;逐 panel 说明所示内容与符号;
> 含真实数值;英式拼写;hedged(无 prove/best/first);不出现任何代码/文件名。面板字母 a/b 与生成图一致。

---

**Fig. 1 | Evidence-constrained, characterisation-frugal credible-discovery framework.**
Schematic of the workflow. Three material roles enter from the left: a mother system
(sepiolite with phosphoric acid) that supplies prior evidence only and is never mixed into the
optimisation history; a source system (attapulgite with phosphoric acid) on which a real closed
loop is run; and a transfer family (lotus-root starch, starch and chitosan) used for prospective
validation. Variable-temperature electrochemical impedance spectroscopy, acquired between +25
and −90 °C, converts each sample into transport evidence—conductivity, segment activation
energies and a sub-zero transition temperature. A single governed core then operates in two
coupled modes, transfer reasoning and closed-loop Bayesian optimisation with a language-model
screening step, with every statement passed through a calibrated claim ladder. Governed outputs
(design rules and prospective candidates) are bounded from below by a reproducibility floor and
from above by an identifiability ceiling, beyond which mechanism cannot be claimed. A guardrail
strip records the operating discipline: a retrospective replay is not treated as a new
measurement, each system keeps a separate optimisation history, and every claim is audited.

---

**Fig. 2 | A composition-tunable sub-zero proton-transport transition across material families.**
(a) Transition-sharpness map. For every data set with a resolved transition, the activation
energy of the low-temperature, thermally activated segment is plotted against that of the
high-temperature, near-athermal segment; markers denote material family (lotus-root starch,
n = 7; starch, n = 4; attapulgite, n = 2) and the dashed line marks equal activation energies.
Lotus-root-starch samples cluster towards the upper left (sharp transition: low high-temperature
and high low-temperature activation energy, mean 0.037 and 0.69 eV respectively), starch samples
are milder, and attapulgite lies between them. (b) Main transition temperature for the 13 data
sets that show a clean two-regime response, ordered within family; all values fall below 0 °C,
between −22 and −39 °C. Two chitosan data sets did not support a clean transition and are
therefore excluded here and treated as a boundary case. Independent repeats of each composition
are included, so the spread within a family also reflects fabrication variability rather than
measurement noise alone. Values are derived from competitive segmented modelling of conductivity
against inverse temperature; one-point terminal segments at the coldest extreme were excluded
from the activation-energy estimates.

---

**Fig. 3 | Closed-loop candidates differ by less than the fabrication reproducibility floor.**
(a) For each prospective and retrospective candidate of the source system, the gap in the scalar
transport objective below the best previously measured candidate is shown as a bar; the shaded
band and the two horizontal lines mark the reproducibility floor propagated from independent
repeats (0.26 decade-equivalents for the standardised-thickness estimate and 0.33 for the
all-repeats estimate). Candidates whose gap lies within the floor (highlighted) cannot be
reliably distinguished from the optimum given fabrication variability; the prospective rounds sit
within about two floor widths of the best. (b) Cross-check on conductivity alone: the absolute
difference in logarithmic conductivity of each candidate from the highest-conductivity candidate,
compared with the conductivity floor. The three highest-conductivity candidates span only about
0.26 decades, comparable to the floor, so they are not separable by conductivity. The floor used
here is a biopolymer proxy for the source system; measuring it directly on same-composition
source-system repeats is identified as the most immediate extension. Together the panels indicate
that the optimisation operates near or below its own resolution, which we report as the
quantitative basis for the honest null in Fig. 7 rather than as evidence of method failure.

---

**Fig. 4 | Calibration of measurement confidence against independent-replication outcomes.**
(a) Conductivity–temperature curves for the lotus-root-starch repeats, overlaid to show the
between-disc spread that defines the reproducibility floor. (b) Reliability diagram relating the
single-curve confidence to the observed independent-replication rate, where a replication outcome
is defined as agreement of a measured point with the consensus of the remaining repeats at the
same temperature within a fixed tolerance; the confidence is poorly resolved before
recalibration and markedly over-confident. (c) Replication rate as a function of temperature,
showing that reproducibility is somewhat lower in the cold regime than in the warm regime. (d)
Expected calibration error as a function of the number of calibration points; an isotonic
recalibration fitted on the replication outcomes reduces the error from 0.78 to approximately
0.13 under a leave-one-dataset-out protocol, chiefly by removing over-confidence (a gain in
reliability rather than in resolution). All quantities are computed across
the full set of independent repeats (882 points overall; 456 for the standardised-thickness
subset). The panels together show that, although a single spectrum cannot certify
reproducibility, the repeats themselves support a usable calibrator.

---

**Fig. 5 | Single-curve quality control does not predict cross-sample reproducibility.**
Discrimination of reproducible from non-reproducible points, measured as the area under the
receiver-operating curve under a leave-one-dataset-out protocol, in which a model is trained on
all but one repeat and evaluated on the held-out repeat. (a) All repeats (n = 882; replication
rate 0.18) and (b) the standardised-thickness subset (n = 456; replication rate 0.38). Bars
compare the existing single-curve confidence (M0), a model using only the validity score (M1),
a model adding the resistance magnitude and temperature (M2), and a model adding within-curve
residual, conductivity level and resistance-extraction descriptors (M3); the dashed line marks
chance (0.5). None of the reproducibility-aware models exceeds chance on held-out repeats, and
the validity score alone generalises below chance, which indicates that the information needed to
anticipate cross-sample reproducibility is not present in a single spectrum. We report this as a
negative result that motivates certifying reproducibility through independent repeats, consistent
with the floor in Fig. 3.

---

**Fig. 6 | Transport data license descriptor-level but not mechanism-level claims.**
(a) Mechanism is not identifiable. On the low-temperature branch of a representative dense data
set, three physically distinct conduction laws—simple thermally activated transport,
three-dimensional variable-range hopping and a Vogel–Tammann–Fulcher form—are fitted to the
logarithmic conductivity; the three describe the data within a difference in explained variance
of 0.006, so the conductivity response cannot select among them. (b) Descriptor is identifiable.
The competitive model selection assigns essentially unit probability to the three-segment
transition description over single-regime and two-regime alternatives, so the transition
temperature and the segment activation energies are recoverable from the same data. The contrast
establishes the basis for the claim ladder: an agent constrained to transport data may state the
descriptor but should treat the underlying mechanism as a hypothesis. This conclusion is
reinforced by the observation that distribution-of-relaxation-times inversion is ill-posed on
these spectra.

---

**Fig. 7 | The closed loop returns an honest null on a short trajectory.**
Retrospective analysis of the real ten-point source-system campaign together with the two
recorded prospective rounds, replaying the logic of the closed loop without any new measurement.
The measured trajectory does not show growth of the dominated objective region, and neither
prospective round exceeds the best previously measured candidate. A leave-future-out surrogate,
fitted prefix by prefix with the same kernel used in the loop, predicts the next measured outcome
only weakly (rank correlation ≈ 0.2). We therefore make no claim of convergence or of an
expanded optimum; the outcome is reported faithfully as a null and is interpreted, through
Fig. 3, as a consequence of a response surface that is flatter near the optimum than the
reproducibility floor. The trajectory is short (ten measured points and two prospective rounds),
which we state as a scope limitation rather than a property of the approach.

---

**Graphical abstract (TOC, ≤ 250 characters of caption text).**
An autonomous agent works from impedance data alone to locate a tunable sub-zero proton-transport
transition, while making its limits explicit: a reproducibility floor from below and an
identifiability ceiling from above.
