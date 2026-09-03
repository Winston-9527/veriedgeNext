# PCRA offline experiment: first results

Date: 2026-08-24

## Status

The first Route B experiment is executable and has completed. It uses measured
honest residuals from two heterogeneous stacks, calibrates on 6 prompt pairs,
and evaluates on 12 held-out prompt pairs at checkpoints C1--C3. Each synthetic
attack is added on top of the measured heterogeneous residual at a declared
relative L2 strength.

This is a protocol/statistic smoke test, not a paper-level E2-R result. The raw
subset is too small to establish a 1% false-dispute guarantee.

## Experiment matrix

- Opening sizes: `q = 64, 128, 256, 512`.
- Statistics over the same opening: spike, energy, and directional.
- Relative L2 strengths: `0.002, 0.005, 0.01, 0.02, 0.05, 0.10`.
- Attack families: 1-sparse, 16-sparse, diffuse balanced, directional, and
  sample-null.
- Threat timing for sample-null:
  - `known_coordinates`: the attacker sees the true opening before committing;
  - `post_commit`: the attacker nulls a guessed opening and commits before the
    verifier independently draws the true opening.
- Calibration: 2,048 challenges per calibration prompt and checkpoint.
- Evaluation: 64 challenges per held-out prompt and checkpoint.

## Finding 1: commitment-time unpredictability removes deterministic evasion

When the attacker knows the opening coordinates, the sample-null attack has
exactly the honest decision rate at every attack strength. At `rho = 0.10`, the
combined rates are:

| q | Honest FPR | Known-coordinate sample-null | Post-commit sample-null |
|---:|---:|---:|---:|
| 64 | 1.69% | 1.69% | 100% |
| 128 | 2.08% | 2.08% | 100% |
| 256 | 3.04% | 3.04% | 100% |
| 512 | 5.30% | 5.30% | 100% |

Thus the useful protocol property is not refresh frequency by itself. It is
that the opening remains unpredictable until after the attacker is committed
to one tensor. This experiment directly encodes that ordering.

The result does **not** imply universal detection. At `rho = 0.002`, the
post-commit sample-null rates remain close to the honest FPR. At `rho = 0.01`,
the observed rates are 68.8%, 4.0%, 7.4%, and 11.9% for increasing q; this
non-monotonicity is a calibration effect discussed below and must not be
presented as evidence that smaller q is intrinsically better.

## Finding 2: sparse detection is coverage-limited

For an s-sparse attack in a tensor of size N, the probability that a uniformly
sampled opening intersects its support is

`1 - choose(N - s, q) / choose(N, q)`.

Averaged over the held-out tensor sizes, the exact coverage probabilities and
the observed high-strength detection rates are:

| q | 1-sparse coverage | observed at rho=.10 | 16-sparse coverage | observed at rho=.10 |
|---:|---:|---:|---:|---:|
| 64 | 0.40% | 1.95% | 6.25% | 8.12% |
| 128 | 0.81% | 2.91% | 12.12% | 13.67% |
| 256 | 1.61% | 4.38% | 22.83% | 25.43% |
| 512 | 3.22% | 8.29% | 40.63% | 44.40% |

The gap is largely the honest FPR plus occasional interactions with measured
drift. The main conclusion is structural: post-commit randomness removes a
known-coordinate blind subspace, but it does not remove sampling coverage risk.
The protocol must choose q from an explicit `(support envelope, gamma)` miss
budget or escalate to a stronger check.

## Finding 3: the statistic portfolio has distinct roles

At `q = 64, rho = 0.01`:

- the directional attack is detected at 95.6% by the combined check, with the
  directional statistic providing nearly all of the power;
- the diffuse balanced attack is detected at 68.9%, primarily by the energy
  statistic;
- spike detection cannot compensate for failure to sample sparse support.

This supports using several statistics on one committed opening instead of
claiming that one scalar summary handles all attack geometries.

## Finding 4: the present calibration does not control held-out FPR

The target combined alpha is 1%, but aggregate held-out FPR ranges from 1.69%
to 5.30%. The excess is concentrated at C3:

| checkpoint | q=64 | q=128 | q=256 | q=512 |
|---|---:|---:|---:|---:|
| C1 | 0.78% | 0.26% | 0.26% | 0.52% |
| C2 | 0.78% | 0.52% | 0.26% | 0.78% |
| C3 | 3.52% | 5.47% | 8.59% | 14.58% |

C3 evaluation prompts exhibit larger normalized residual energy and maxima
than the six C3 calibration prompts. More repeated coordinate draws make the
Monte Carlo quantile stable but cannot repair prompt-level distribution shift.
Therefore the current threshold rule is not yet deployable.

Required correction for the strong protocol:

1. collect substantially more independent calibration prompts and hardware
   pairs;
2. calibrate per execution signature and checkpoint;
3. report prompt-clustered confidence intervals;
4. use a held-out risk-control method for the false-dispute budget;
5. return `INCONCLUSIVE` or escalate when the signature lacks enough calibration
   support, rather than silently applying a global threshold.

## Immediate interpretation for Route B

The experiment supports a narrower but stronger thesis:

> A useful low-cost check is a commit--challenge protocol whose post-commit
> opening eliminates deterministic coordinate-aware evasion, whose statistic
> portfolio covers distinct dense attack geometries, and whose sampling budget
> is derived from a declared miss-risk envelope. It must abstain when its honest
> drift calibration cannot support the promised false-dispute risk.

It does not yet establish the full PCRA system. Missing pieces are end-to-end
tensor commitments/openings, an adaptive attacker optimized jointly against all
three statistics, sequential expansion with alpha spending, and full-corpus
calibration.
