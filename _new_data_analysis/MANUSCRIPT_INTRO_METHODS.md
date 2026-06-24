# Introduction & Methods — full draft (journal prose; no code/implementation names)

> D1 续(2026-06-21)。套用 nature-writing/polishing 规范:每段首句点题、一段一意;英式拼写;
> 无缩写优先、首次出现定义缩写;数值+空格+单位;范围用 en-dash;**避免 prove/best/first/superior**,
> 改用 show/establish/indicate/to our knowledge。**正文不出现任何代码、文件名、函数名、内部管线名**。
> 目标刊:Digital Discovery(备选 Machine Learning: Science and Technology)。所有数字均为真实结果。

---

## 1. Introduction

Autonomous experimentation promises to compress the design–make–measure–learn cycle of
materials research, and self-driving laboratories have begun to demonstrate closed-loop
discovery across catalysis, photovoltaics and electrolytes. Most demonstrations, however,
assume access to rich structural characterisation, so that an autonomous agent can attribute a
measured property to an underlying structure. In practice the majority of laboratories operate
under a far more constrained regime, in which a single, inexpensive probe—electrochemical
impedance spectroscopy (EIS)—is the only routinely available read-out, and structural
characterisation is slow, costly or simply unavailable. The central question of this work is
therefore not how fast an agent can optimise, but what an autonomous agent can *credibly claim*
when it observes only transport data.

This question exposes a gap that current autonomous-discovery systems leave open. Agentic and
self-driving pipelines are typically evaluated by the performance of the materials they return,
yet they rarely separate what has genuinely been discovered from what has merely been fitted to
noisy observations, and they rarely quantify the physical limit imposed by sample-to-sample
fabrication variability. Work on uncertainty quantification and calibration, in turn, is usually
developed on simulated benchmarks or on textual self-evaluation, rather than on independent
physical repeats of the same wet-lab protocol. As a result, the confidence reported by an
autonomous agent and the reproducibility actually achievable in the laboratory are seldom
connected, and the boundary between a defensible descriptor-level statement and an
over-reaching mechanistic claim is left to informal judgement.

Establishing credibility from transport data alone is difficult for three connected reasons.
First, impedance data are mechanistically ambiguous: distinct microscopic transport pictures can
reproduce the same conductivity–temperature response, and the inversion of a spectrum into a
unique relaxation structure is ill-posed, so a mechanism cannot in general be recovered from
transport observables. Second, nominally identical samples differ because pressing and casting
introduce uncontrolled geometric and densification variation; this imposes a reproducibility
floor on any measured property, and the floor is invisible to the single-curve quality-control
scores that an agent computes from one spectrum. Third, a closed optimisation loop that is
unaware of this floor can expend its budget resolving candidate-to-candidate differences that
are smaller than the floor itself, producing apparent progress that does not survive
re-fabrication. Each of these obstacles limits what may honestly be asserted, yet none is
routinely measured in autonomous-discovery studies.

In this work we study characterisation-frugal credible discovery in a family of
biopolymer–clay–phosphoric-acid proton conductors, using dense variable-temperature EIS as the
sole experimental evidence, and we make the limits of the resulting claims explicit and
quantitative. The agent operates in two coupled modes that share one governed analysis core: a
transfer-reasoning mode that locates and validates a transport descriptor across material
families, and a closed-loop optimisation mode that proposes new compositions in a single host
system. Our contributions are threefold. (i) Across 13 independent repeats spanning four
material families, we establish a universal sub-zero proton-transport transition, with a
break temperature between −22 and −39 °C, whose sharpness is tunable by composition; a low
lotus-root-starch family shows the sharpest transition, with a reproducible low-temperature
activation energy of 0.69 ± 0.07 eV across seven repeats, while a chitosan family forms a
boundary case that does not show a clean transition. (ii) We measure the fabrication
reproducibility floor directly from independent repeats and show, under a leave-one-dataset-out
protocol, that single-curve quality-control confidence does not predict cross-sample
reproducibility; reproducibility must therefore be certified by independent repeats, although a
calibrator trained on those repeats reduces the expected calibration error from 0.78 to 0.13
(leave-one-dataset-out), chiefly by removing over-confidence rather than by adding resolution.
(iii) We derive a structural-identifiability bound which shows that transport data license
claims only at the level of descriptors, not mechanisms, and we use it to justify a graded claim
policy. Finally, we report a real multi-objective optimisation loop with a language-model
proposal-screening step as an honest null result, in which the leading candidates differ by less
than the measured reproducibility floor.

Taken together, these results frame autonomous discovery under restricted characterisation as a
problem with two explicit boundaries—a reproducibility floor from below and an identifiability
ceiling from above—and show that both can be measured from the same transport data used for
discovery. We argue that reporting these boundaries, including negative and null outcomes, is a
prerequisite for trustworthy self-driving laboratories rather than an afterthought.

---

## 2. Methods

### 2.1 Overview

We study proton-conducting composites assembled from a biopolymer, a clay mineral and
phosphoric acid, and we treat a separately reported acid-in-clay system only as prior evidence
that is never mixed into the optimisation history of the host system. All experimental evidence
is variable-temperature EIS acquired between room temperature and approximately −90 °C. The
analysis core converts each spectrum into a bulk conductivity with an associated validity score,
detects transport transitions by competitive segmented modelling, quantifies reproducibility
from independent repeats, bounds the admissible level of mechanistic interpretation by
structural identifiability, and feeds a governed closed optimisation loop. Sections 2.2–2.7
describe these components in the order in which evidence flows through them.

### 2.2 Sample preparation and impedance measurement

Composite pellets were prepared by combining the biopolymer, the clay mineral and phosphoric
acid in fixed molar proportions, followed by pressing into discs of documented thickness; the
thickness of every disc was recorded from its preparation record and used without substitution.
Impedance spectra were acquired in a two-electrode configuration over a wide frequency range at
each set-point temperature. The temperature was varied in steps from above room temperature down
to approximately −90 °C, and the sample was allowed to equilibrate at each set point before
acquisition, so that every spectrum corresponds to a near-isothermal state. Independent repeats
of a given composition were obtained as separately pressed discs measured in separate sessions,
which is the appropriate unit for assessing fabrication reproducibility.

### 2.3 Conductivity extraction and quality control

For each spectrum the bulk resistance was obtained from the high-frequency response and
converted to a conductivity using the recorded disc geometry. Each spectrum received a
Kramers–Kronig validity score, which tests the internal consistency of the real and imaginary
parts and serves as a single-curve quality-control signal; spectra were ordered by temperature
and screened for physically implausible behaviour. The validity score and the magnitude of the
extracted resistance were retained as candidate predictors for the reproducibility analysis of
Section 2.5.

### 2.4 Transition detection by competitive segmented analysis

To locate transport transitions without assuming their number in advance, we modelled the
logarithm of conductivity against inverse temperature with one, two and three linear segments
and let the data select among them. Models were compared using the Akaike information criterion
with small-sample correction, which penalises additional segments, and the resulting weights
were interpreted as model probabilities. A discontinuous two-segment alternative was admitted
only when a structural-break test indicated a statistically significant change and the implied
jump exceeded the residual scatter, which guards against spurious breaks. For each accepted
model we report the transition temperature and the activation energy of the high-temperature and
low-temperature segments; one-point terminal segments that can arise at the coldest extreme were
excluded from the activation-energy estimates and flagged.

### 2.5 Reproducibility floor and reproducibility-aware confidence

We quantified reproducibility from independent repeats of identical compositions. For every pair
of repeats we computed the absolute difference in logarithmic conductivity at matched
temperatures, and summarised the distribution by its median and ninetieth percentile, separately
for the warm and cold regimes. To test whether single-curve quality control predicts
reproducibility, we defined an independent-replication outcome for each measured point as
agreement, within a fixed tolerance, with the consensus of the remaining repeats at the same
temperature. We then compared predictors of this outcome under a leave-one-dataset-out protocol,
in which a logistic model trained on all but one repeat is evaluated on the held-out repeat, so
that the reported discrimination reflects generalisation rather than within-dataset fitting.
Calibration was assessed with the expected calibration error and reliability diagrams, and an
isotonic recalibration was fitted on the replication outcomes of the repeats; a learning curve
was constructed by varying the number of calibration points.

### 2.6 Structural-identifiability analysis

To determine the level at which transport data support interpretation, we distinguished
descriptor identifiability from mechanism identifiability. Descriptor identifiability was
assessed from the model competition of Section 2.4, where a decisive selection of the
transition model indicates that the descriptor is recoverable from the data. Mechanism
identifiability was tested by fitting, to the low-temperature branch of a representative dense
data set, three physically distinct conduction laws—simple thermally activated transport,
three-dimensional variable-range hopping and a Vogel–Tammann–Fulcher form—and comparing their
goodness of fit. When several mechanistically different laws describe the same data to within a
negligible difference in explained variance, the mechanism is not identifiable from the
conductivity response, and interpretation must be restricted to the descriptor level.

### 2.7 Governed closed-loop optimisation and claim policy

The optimisation mode proposes compositions in a single host system by multi-objective Bayesian
optimisation over a scalarised transport objective, with a language-model step that screens and,
where necessary, adjusts each raw proposal against pre-specified safety and feasibility
constraints. Prospective proposals were frozen with a timestamp before synthesis, and outcomes
were reported whether or not they improved upon the best previously measured candidate, so that
null results are recorded faithfully. To interpret the loop, candidate-to-candidate differences
in the objective were placed on the same scale as the reproducibility floor of Section 2.5.
Throughout, statements produced by the agent were constrained by a graded claim policy that
admits descriptor-level conclusions, treats inconclusive evidence as inconclusive, and withholds
mechanistic claims that the identifiability analysis of Section 2.6 shows to be unsupported.

### 2.8 Data and code availability

All processed spectra, derived quantities and analysis scripts that reproduce the figures are
provided in the project repository, together with the timestamped prospective records of the
optimisation loop. No quantitative value was altered after the fact, and confidence statements
were not re-weighted to favour positive outcomes.
