# Harm-preserving adaptive attack: local results

Date: 2026-08-24

## Question

Can an attacker that knows the thresholds, all three statistics, and the
coordinate distribution commit a harmful fixed perturbation before the random
opening and still evade the combined check?

## Protocol controls

- The attacker optimizes spike, energy, and directional tests jointly using
  expectation over transformation (EOT).
- Optimization challenges, candidate-selection challenges, and final test
  challenges are disjoint.
- One perturbation is frozen before the 2,048 final challenges are sampled.
- Candidate supports are 16, 256, and dense; the attacker selects the candidate
  with the lowest rate on the separate selection set.
- Every perturbation is projected orthogonal to the measured honest residual.
  Therefore it cannot evade by repairing heterogeneous drift, and
  `||r + delta||^2 = ||r||^2 + ||delta||^2`.
- Six held-out prompt/checkpoint pairs are used: two prompts at C1--C3.

## Main result

Mean combined rates across the six pairs are:

| q | rho | honest FPR | adaptive joint | fixed diffuse | fixed 16-sparse |
|---:|---:|---:|---:|---:|---:|
| 64 | .01 | 3.87% | 7.19% | 72.19% | 9.66% |
| 64 | .02 | 3.87% | 9.11% | 89.83% | 9.62% |
| 64 | .05 | 3.87% | 9.70% | 100% | 9.75% |
| 128 | .01 | 5.33% | 6.14% | 9.80% | 9.02% |
| 128 | .02 | 5.33% | 9.84% | 35.30% | 15.58% |
| 128 | .05 | 5.33% | 14.28% | 100% | 16.32% |
| 256 | .01 | 8.54% | 11.08% | 16.07% | 15.22% |
| 256 | .02 | 8.54% | 18.69% | 40.57% | 28.69% |
| 256 | .05 | 8.54% | 24.67% | 100% | 28.20% |
| 512 | .01 | 13.80% | 17.11% | 24.94% | 23.32% |
| 512 | .02 | 13.80% | 30.49% | 45.24% | 46.93% |
| 512 | .05 | 13.80% | 36.26% | 100% | 48.62% |

The directional baseline is 94.4% at `q=64, rho=.01` and at least 99.5% for
all larger q or strengths. It is omitted from the table only for compactness.

## Validity checks

- Mean absolute selection--test gap for the adaptive attack: 1.48 percentage
  points; maximum: 7.08 points.
- Maximum absolute cosine between injected perturbation and honest residual:
  `4.1e-8`.
- Maximum relative-L2 constraint error: `4.9e-9`.
- At `q=64`, 17 of 18 adaptive configurations select a 16-coordinate support.
  At larger q, the optimizer switches between 16-sparse, 256-support, and dense
  candidates depending on strength and boundary.

## Go/no-go interpretation

The current three-statistic coordinate-opening check does **not** pass the
white-box adaptive stress test at `q <= 512`. Post-commit unpredictability
prevents exact nulling of the realized opening, but the attacker can concentrate
energy on a small support and accept the low support-hit probability. Increasing
attack strength barely changes detection at `q=64`, because a sampled spike is
already obvious and the limiting event is whether the support is sampled at all.

This does not yet establish semantic harm: the local subset has no prompts,
model weights, or downstream generation path. It does establish that fixed
relative L2 energy, even when forced not to cancel honest drift, can remain
mostly unseen by the proposed low-cost coordinate portfolio.

## Consequence for Route B

Route B should not proceed by merely tuning thresholds or adding more statistics
over the same small coordinate opening. A stronger design needs at least one of:

1. a non-local randomized measurement after commitment, such as a dense random
   projection with a proof that it was computed from the committed tensor;
2. an opening size derived from an explicit sparse-support miss budget, which is
   likely too expensive for very sparse attacks;
3. escalation to a full/per-block check when the policy cannot certify the
   declared attack envelope;
4. a narrower threat model that explicitly excludes highly sparse perturbations,
   with that limitation stated rather than hidden.

The next productive design task is therefore a verifiable post-commit random
linear measurement, not another parameter sweep of the current coordinate test.
