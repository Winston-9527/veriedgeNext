# Route B redesign: PACT

Date: 2026-08-24  
Status: design specification with local P0 geometry validation; not yet a paper claim  
Working name: **PACT — Post-commit Activation Consistency Test**

The first local experiment is recorded in
`experiments/pact_offline/P0_RESULTS_2026-08-24.md`. It supports the
full-coverage geometry at K >= 32, but also exposes a C3 calibration failure
caused by the six-prompt calibration subset. That result narrows the next work
to prompt-level uncertainty, abstention, semantic harm, and runtime overhead.

A follow-up experiment in
`experiments/pact_offline/GAUSSIAN_P0_RESULTS_2026-08-24.md` changes the default
candidate from Rademacher to Gaussian projections. Rotational invariance removes
the residual small-K support-shape dependence: the largest support-dependent
detection spread is 0.70 percentage points across all tested K and rho values,
at a 2--3.4x coefficient-generation cost in the local materialized NumPy path.
The Gaussian form is called PACT-G below; the original signed form is PACT-R.

The exact chi-square adaptive-policy simulation is recorded in
`experiments/pact_offline/ADAPTIVE_GAUSSIAN_RESULTS_2026-08-24.md`. C1/C2
rho=.02 attacks stop near K=8 and rho=.01 near K=19, while C3 remains dominated
by prompt-level calibration uncertainty. This separates the two uncertainty
layers: adaptive K controls projection error; new independent prompts are still
required to control the honest envelope.

The known-seed negative control in
`experiments/pact_offline/KNOWN_SEED_NEGATIVE_CONTROL_2026-08-24.md` constructs
a `(K+2)`-sparse, harm-preserving nullspace attack after seeing the realized
matrix. Its detection rate is exactly the honest rate at every tested rho. This
experiment makes seed ordering a demonstrated requirement: the property is
unpredictability at attack commitment, not refresh frequency by itself.

The exact conditional-power analysis in
`experiments/pact_offline/CONDITIONAL_POWER_2026-08-24.md` shows that K must be
boundary-aware. For rho=.01 and 95% conditional power, C1/C2 need median K=8
and at most 19--20 over the observed prompts; C3 needs median K=303 and up to
928. A global Kmax=256 is therefore both wasteful at shallow boundaries and
insufficient for the hardest deep-boundary target.

The coefficient implementation study in
`experiments/pact_offline/QUANTIZED_GAUSSIAN_RESULTS_2026-08-24.md` identifies a
16-bit inverse-CDF lookup table as the current implementation candidate. Its
worst high-precision support spread is 0.368% versus 0.302% for ideal Gaussian,
its tested simultaneous coverage matches Gaussian, and it is 37%--43% faster
than online Gaussian generation locally. Ideal Gaussian remains the analysis
model; LUT16 requires a frozen PRG/table specification and conservative or
formally justified finite-table intervals.

The executable transcript in
`experiments/pact_offline/PACT_G16_PROTOCOL_RESULTS_2026-08-24.md` implements
canonical tensor commitments, context-bound post-commit seed derivation,
row-addressable SHAKE256/LUT16 projections, authenticated receiver/reference
receipts, and adjudicator cross-checks. All binding, replay, prefix, linearity,
and six-real-boundary tests pass. HMAC is used only because the local environment
lacks Ed25519; public signatures, a real beacon, durable replay state, and
cross-hardware accumulation tests remain deployment requirements.

The transactional control prototype in
`experiments/pact_offline/PACT_G16_STATE_MACHINE_RESULTS_2026-08-24.md` adds a
two-party context-bound commit-reveal beacon, immutable roots, deadlines,
durable replay protection, conflict freezing, and explicit abort states. All 15
valid/adversarial/restart paths pass. A last revealer can still cause an abort;
timeout must never become PASS, and deployment needs a public beacon,
threshold protocol, penalty, or committed fallback for availability.

## 1. Why the previous design is retired

The coordinate-opening prototype combined spike, energy, and directional
statistics over the same random set of `q` coordinates. This improved coverage
of different attack geometries but did not change the event that dominates a
sparse attack: whether any attacked coordinate is opened.

The harm-preserving white-box experiment confirms the limitation. At
`q = 64, rho = .05`, the adaptive attack is detected only 9.70% of the time;
even at `q = 512`, it is detected only 36.26%, while the held-out honest rate is
already 13.80%. The optimizer usually selects a 16-coordinate support. Adding
more statistics over the same opening therefore cannot solve the problem.

The redesign imposes a hard requirement:

> Every randomized measurement must depend on every tensor coordinate. Sparse
> perturbations may change the measurement distribution, but they may not evade
> merely because their support was not sampled.

## 2. Design scope

PACT checks whether a transmitted shard-boundary activation is materially
different from a committed reference execution under heterogeneous floating
point drift. It is not a proof of semantic correctness.

PACT targets an **execute-once, commit-first adversary**:

1. the adversary knows the protocol, projection family, thresholds, evidence
   budget, and seed distribution;
2. it fixes and commits the boundary tensor before the realized projection seed
   exists;
3. it may optimize against the distribution of future seeds;
4. it does not control every witness on the checked boundary.

PACT does not claim security when the seed is known before tensor commitment,
when the same seed is reused across adaptive tasks, or when all relevant
producer, receiver, and reference witnesses collude.

## 3. Core idea

Let the transmitted activation and reference activation at boundary `k` be

`h, h_ref in R^N`.

Both are fixed before a public beacon derives a fresh seed `s`. The seed defines
a full-coverage random matrix

`A_s in R^(K x N),  (A_s)_(j,i) iid~ Normal(0, 1/K)`.

This Gaussian form is PACT-G. PACT-R, with coefficients in
`{-1/sqrt(K), +1/sqrt(K)}`, remains a lower-generation-cost ablation but does
not have exact support-shape invariance at small K.

The actual and reference witnesses compute

`y = A_s h`,  `y_ref = A_s h_ref`.

By linearity,

`d = y - y_ref = A_s (h - h_ref)`.

PACT uses the normalized projected energy

`T_K = ||d||_2^2 / N`

as an estimator of the full residual energy

`F_2 = ||h - h_ref||_2^2 / N`.

Because every column of `A_s` is nonzero, every coordinate contributes to every
projection row. In particular, a one-coordinate perturbation changes all `K`
rows. Its detection is no longer limited by `q/N`.

The random projection is classical AMS/JL machinery, not the contribution. The
contribution must be the protocol that makes its randomness arrive after a
position-binding tensor commitment, ties its value to the tensor actually sent
between two providers, calibrates heterogeneous drift, and converts statistical
uncertainty into an explicit abstain/escalate decision.

## 4. Protocol entities and assumption

For boundary `k`:

- `P_k`: upstream shard provider and tensor producer;
- `P_(k+1)`: downstream provider and tensor receiver;
- `W_ref`: the policy-committed reference/replay witness;
- `B`: an unpredictable public beacon or commit--reveal coin-toss service;
- `V`: the adjudicator;
- `L`: the tamper-evident task record.

Required honesty condition:

> At least one receipt issuer for each checked tensor and the committed
> reference path do not collude with the tensor producer.

The ordinary pipeline receiver is the default receipt issuer because it already
possesses the exact tensor bytes. The requester acts as receiver for the final
output. High-assurance placements may assign a second receipt witness. A
placement that cannot satisfy this witness condition is inadmissible for PACT.

This is stronger and more precise than saying only that the group is “not fully
colluding.” It identifies exactly which non-collusion edge the check needs.

## 5. Committed policy

Before task access, the placement record fixes:

- checked boundaries and producer/receiver identities;
- reference/replay path;
- canonical tensor serialization, dtype, shape, and accumulator rule;
- commitment hash and domain separation;
- beacon source and seed deadline;
- projection family and PRG version;
- initial and maximum rows `(K_0, K_max)`;
- sequential expansion schedule;
- execution-signature-specific honest profile;
- false-dispute budget `alpha`;
- declared material-discrepancy floor `eta`;
- miss budget `gamma`;
- receipt timeout and withholding penalty;
- escalation mode and settlement rule.

No protocol parameter that affects the challenged subspace may be selected
after seeing the committed tensor or its verdict.

## 6. Wire protocol

### Phase 0: tensor commitment

`P_k` canonicalizes its completed boundary tensor and commits

`c_send = H(task || boundary || shape || dtype || Ser(h))`.

The reference path similarly commits `c_ref`. Both commitments must be durable
before the beacon cutoff. A Merkle/chunked hash is preferable when later
availability audits are required; a flat cryptographic hash suffices for the
first prototype.

This hash is not compared across heterogeneous executions. It binds each
execution to its own exact bytes, so honest numerical drift causes no hash
failure.

### Phase 1: post-commit seed

Only after all required roots are recorded does the beacon derive

`s = H_beacon(task || boundary || c_send || c_ref || beacon_value)`.

The seed is one-time. It is never reused at the same boundary for another task.
The provider may learn `s` now, but collision/second-preimage resistance prevents
it from changing the tensor already bound by `c_send`.

### Phase 2: receiver-bound measurement

`P_k` transfers the committed tensor to `P_(k+1)`. The receiver:

1. recomputes `c_recv` from the exact bytes it consumes;
2. rejects immediately if `c_recv != c_send`;
3. computes `y = A_s h` using the committed canonical order;
4. signs a receipt containing task, boundary, both roots, seed identifier,
   projection prefix, and timestamp.

The reference witness computes `y_ref = A_s h_ref` and signs the analogous
receipt. The suspicious producer does not self-report the evidence on which its
own settlement depends; an actual tensor consumer reports it.

The projection can be fused with receipt-side tensor handling. A deterministic
PACT-G prototype should specify a counter-based PRG and Gaussian transform,
use float32 input, fixed index order, and float64 accumulation. PACT-R replaces
the Gaussian transform with PRG-generated signs. A GPU implementation may
replace either path only after demonstrating equivalent calibration behavior.

### Phase 3: risk-controlled decision

The verifier checks signatures, roots, context, shape, seed, and receipt timing,
then computes `T_K` from the two sketches.

The result is three-valued:

- **PASS**: the upper uncertainty bound remains inside the calibrated honest
  region;
- **FAIL**: the lower uncertainty bound exceeds the committed material boundary;
- **INCONCLUSIVE**: the intervals overlap or the execution signature lacks
  sufficient calibration support.

INCONCLUSIVE is not silently converted to PASS. The policy expands `K`, invokes
the reference replay, requests a second witness, or escalates to a full/per-block
check.

### Phase 4: localization and settlement

- `c_recv != c_send`: the sender equivocated in transit or sent bytes different
  from its commitment; charge the sender unless availability evidence shows a
  receiver-side protocol fault.
- roots match but projected residual fails: localize to the first failing
  checked boundary whose predecessor passed; interpret attribution through the
  committed shard map.
- missing or late roots/receipts: protocol violation, not honest numerical drift.
- conflicting receiver receipts: freeze automatic settlement and run the
  committed full-tensor/second-witness escalation.

The basic receipt is evidence under a non-collusion assumption, not a succinct
cryptographic proof that a projection was computed correctly. This limitation
must be stated explicitly.

## 7. Why sparse attacks no longer get a free blind spot

For a residual vector `v = h - h_ref` fixed before the seed and a Gaussian row
`g`,

`<g, v> ~ Normal(0, ||v||_2^2)`.

Therefore the normalized PACT-G estimator has the exact distribution

`K T_K / F_2 ~ chi-square_K`.

It depends on total residual energy and K, not the residual's support or
direction. Exact chi-square quantiles give projection-confidence intervals;
standard concentration also gives a bound of the form

`Pr[ |T_K - F_2| > epsilon F_2 ] <= 2 exp(-c K epsilon^2)`

for a universal constant `c` and the appropriate matrix normalization.

The important scope is “fixed before `s`.” If the adversary sees `A_s` before
choosing the tensor, it can again choose a vector in `ker(A_s)`. If one matrix is
reused and detailed answers are exposed across adaptive queries, classical
adaptive-linear-sketch attacks become relevant. PACT therefore uses a fresh
post-commit seed for every task/boundary and records only the receipt digest and
verdict outside the adjudicator.

Every Gaussian coefficient is nonzero with probability one, so the old
`1 - choose(N-s,q)/choose(N,q)` support-hit ceiling disappears entirely. Random
cross terms with honest drift can still mask a perturbation; K and the
honest/attack separation margin control that probability. PACT-R retains the
coverage property but, unlike PACT-G, its finite-K distribution can depend on
the residual's coordinate shape.

## 8. Risk accounting

PACT separates three risks.

### Honest drift risk

For execution signature `sigma` (model, boundary, producer/receiver hardware,
backend, dtype, projection implementation), use independent calibration prompts
and seeds to estimate an upper honest envelope `U_sigma`.

Use held-out or split-conformal calibration rather than a pooled empirical
percentile. If the number of independent calibration prompts is too small for
the requested `alpha`, the only valid output is INCONCLUSIVE/admission failure.
Repeated seeds improve projection Monte Carlo precision but do not create new
independent prompts.

### Projection risk

Let the task declare material discrepancy

`F_2 >= eta^2`.

Choose `K` so that the lower JL bound on `eta^2` remains above the upper honest
envelope with miss probability at most `gamma_proj`. If no such gap exists below
`K_max`, PACT cannot certify this signature at the requested cost.

### Composition risk

Budget separately for:

- calibration/shift error;
- random-projection error;
- sequential looks;
- multiple checked boundaries.

Use a confidence sequence or precommitted alpha-spending schedule when expanding
`K`; do not repeatedly apply a fixed 1% threshold. The task-level budgets should
satisfy, conservatively,

`alpha_task <= sum_k alpha_k`,

`gamma_task <= sum_k gamma_k`.

## 9. Sequential policy

Recommended first prototype:

- `K_0 = 8` rows;
- expansions `8 -> 16 -> 32 -> 64`;
- median-of-means aggregation over precommitted row groups;
- `K_max = 64` initially;
- immediate FAIL on root/signature/context mismatch;
- INCONCLUSIVE when the confidence interval overlaps the decision boundary at
  `K_max`.

The tensor must remain available until expansion ends. In an inline deployment,
expansion occurs while the receiver already holds the activation for its shard.
In an optimistic post-hoc deployment, retaining full tensors through the
challenge window is an explicit storage/privacy cost and must be measured.

## 10. Privacy and evidence placement

Random projections of activations may leak information. They should not be
placed on a public ledger. Store only:

- root/receipt digests;
- policy and seed identifiers;
- PASS/FAIL/INCONCLUSIVE;
- localized boundary and settlement outcome.

Projection values remain encrypted to the adjudicator or are deleted after the
challenge window. PACT does not reduce what the downstream receiver learns: that
provider already holds the complete boundary activation.

## 11. Expected costs

- producer: one full-tensor commitment pass unless hashing is fused with tensor
  production;
- receiver: one root/hash pass plus `K` signed additions per coordinate, which
  can be fused with receipt or transfer;
- reference path: the same projection work;
- evidence: `K` float values plus roots/signatures per checked boundary;
- state: tensor retention until seed/expansion completes;
- latency: beacon round plus projection and reference comparison.

This is deliberately more expensive than the failed coordinate check. Its value
proposition is not “free verification,” but eliminating support-sampling failure
while keeping evidence far smaller than the tensor.

A structured or sparse projection may later reduce arithmetic from `K*N`, but
it should be treated as an optimization only after dense PACT-G establishes the
security curve; otherwise the optimization may reintroduce support dependence.

## 12. Security claims PACT may and may not make

### Candidate claims

1. **No support-coverage ceiling for commit-first attacks.** Every coordinate
   affects each measurement; miss probability depends on projection dimension
   and signal-to-drift margin, not on support-hit probability.
2. **Execute-once adaptive soundness.** For a tensor fixed before a fresh seed,
   the projected residual estimates full L2 discrepancy with an explicit
   probability bound.
3. **Transmission binding under a witness assumption.** A non-colluding receiver
   binds the measurement to the tensor bytes actually consumed.
4. **Risk-aware abstention.** Unsupported hardware signatures and overlapping
   drift/attack envelopes return INCONCLUSIVE rather than an unjustified PASS.

### Non-claims

- semantic correctness of the generated text;
- detection below the committed L2 materiality floor;
- security when the seed is known before commitment;
- robustness to reuse of one sketch matrix across adaptive tasks;
- protection against colluding producer, receiver, and reference witnesses;
- cryptographic proof of receiver projection correctness in the base mode;
- privacy of boundary activations from their legitimate receiver.

## 13. Relationship to adjacent work

- AMS/JL sketches already provide streaming L2 estimation and dimension
  reduction. PACT uses this known primitive.
- TensorCommitments provides tensor-native position binding and succinct point
  openings. PACT instead needs a tolerance-aware real-valued distance check on
  heterogeneous boundary tensors and uses an actual receiver as the base-mode
  measurement witness.
- TAO provides Merkle-anchored optimistic, tolerance-aware operator dispute
  resolution. PACT operates at cross-provider activation boundaries and targets
  a different failure: a white-box adversary exploiting a fixed low-dimensional
  sketch/nullspace.
- Work on adaptive linear sketches shows that public/reused linear maps are not
  generally robust to adaptive inputs. PACT's guarantee is intentionally the
  narrower one-shot ordering: commit first, derive a fresh seed second.

Relevant starting points:

- TensorCommitments: https://arxiv.org/abs/2602.12630
- TAO: https://arxiv.org/abs/2510.16028
- Hardt--Woodruff adaptive linear sketches: https://arxiv.org/abs/1211.1056

The paper must claim the protocol/risk/system co-design, not random projection,
hash commitment, or tolerance calibration in isolation.

## 14. Implementation plan

### P0: local offline feasibility

Use the existing raw activation subset.

- `K in {1, 2, 4, 8, 16, 32, 64}`;
- independent seed per tensor/challenge;
- fixed 1-sparse, 16-sparse, diffuse, directional, and harm-preserving EOT
  attacks committed before the seed;
- C1--C3 separately;
- compare projected-energy PACT against the failed coordinate portfolio;
- report FPR, TPR, selection--test gap, and estimate error versus exact full L2.

This experiment can be implemented immediately and does not need model weights.

### P1: full-corpus risk calibration

- restore the full calibration/evaluation prompt corpus;
- add hardware/backend pairs and model widths;
- split by execution signature;
- use prompt-clustered confidence intervals;
- test drift shift and calibration staleness;
- demonstrate when the result must be INCONCLUSIVE.

### P2: end-to-end receiver receipt

Instrument the three-node pipeline.

- canonical root at every boundary;
- beacon after roots;
- receiver recomputes root and projections;
- signed receipts and first-mismatch localization;
- withholding, wrong-root, replay, and malformed-receipt tests;
- measure latency, memory bandwidth, retained state, evidence bytes, and energy.

### P3: semantic harm

With the complete model environment, inject attacks that survive the checker and
measure generated-output harm. The final paper must not use relative L2 alone as
a semantic-harm claim.

### P4: witness and collusion study

- one malicious producer, honest receiver;
- honest producer, malicious receiver/false accusation;
- adjacent collusion;
- second witness or full-tensor escalation;
- clearly separate detection from attribution.

## 15. Go/no-go gates

Do not build the full paper unless P0/P1 satisfy all of the following at a
predeclared materiality floor:

1. adaptive detection no longer collapses with support size;
2. at some practical `K <= 64`, held-out detection reaches the target (initially
   90%) with a prompt-clustered lower confidence bound;
3. held-out honest false disputes meet the committed alpha with an upper
   confidence bound;
4. increasing attack strength produces a monotone separation from honest drift;
5. the same policy works across more than one checkpoint/hardware signature or
   correctly abstains;
6. receiver-side root/projection work stays within a predeclared overhead target
   (initially 5% of boundary handling time);
7. EOT optimization against the seed distribution does not recover a new
   low-cost escape route.

If PACT needs hundreds of dense rows, cannot control C3 false disputes, or only
works by excluding realistic semantic attacks from the materiality envelope,
Route B should be stopped rather than reframed after the fact.

## 16. Bottom line

The previous design randomized **which coordinates were inspected**. PACT
randomizes **how all coordinates are combined**, after the tensor is bound.
That is the minimum architectural change needed to remove the sparse support-hit
failure observed locally.

PACT is promising enough for a P0 experiment, but it is not yet a contribution.
The contribution exists only if the receiver-bound protocol, risk bounds,
heterogeneous calibration, adaptive-attack results, and measured end-to-end cost
work together.
