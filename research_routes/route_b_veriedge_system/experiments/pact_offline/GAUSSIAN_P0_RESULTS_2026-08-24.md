# PACT-G P0: support-invariant post-commit projections

Date: 2026-08-24  
Status: completed local statistical experiment and CPU microbenchmark

## Design change

The first PACT prototype used iid Rademacher coefficients. It removed the
coordinate-opening support-hit ceiling, but its small-K estimator distribution
still depended on attack shape. A one-sparse Rademacher perturbation contributes
fixed energy to every row, while a diffuse perturbation produces a variable
signed sum.

PACT-G instead derives iid Gaussian coefficients after tensor commitment. For
any vector `v` fixed before the seed,

`<g, v> ~ Normal(0, ||v||_2^2)`.

Consequently the projected-energy distribution depends on the committed
vector's total L2 energy, not its support, direction, or coordinate allocation.
This is classical rotational invariance; the protocol contribution would be
commit-before-seed execution, receiver-bound evidence, drift calibration, and
explicit escalation rather than Gaussian projection itself.

## Experiment

The attack construction and real heterogeneous residuals are identical to the
Rademacher P0 experiment:

- supports 1, 16, and 256;
- rho = .01, .02, and .05;
- K = 1, 2, 4, 8, 16, 32, and 64;
- eight distribution-aware candidate tensors per setting;
- 256 candidate-selection challenges and 4,096 independent final challenges;
- 512 calibration projections per prompt/checkpoint.

For efficiency, the offline experiment samples the exact joint Gaussian
distribution from the honest/attack Gram matrix. A separate validation compares
this sampler with materialized dense Gaussian matrices; maximum scaled
covariance error is 0.0053 for the Gram sampler and 0.0349 for the finite dense
sample, both below the predeclared 0.06 tolerance.

## Result

Support dependence disappears within Monte Carlo error at every tested K. The
largest max--min detection spread among supports 1, 16, and 256 is 0.70
percentage points over all 21 `(K, rho)` settings.

Representative mean detection rates across six prompt/checkpoints:

| K | rho | support 1 | support 16 | support 256 | max--min |
|---:|---:|---:|---:|---:|---:|
| 1 | .01 | .1263 | .1211 | .1248 | .0052 |
| 1 | .02 | .3560 | .3568 | .3540 | .0028 |
| 1 | .05 | .6703 | .6680 | .6657 | .0046 |
| 4 | .02 | .6292 | .6271 | .6225 | .0068 |
| 8 | .02 | .6918 | .6918 | .6879 | .0039 |
| 16 | .02 | .7129 | .7122 | .7122 | .0007 |
| 32 | .01 | .6444 | .6435 | .6448 | .0013 |
| 64 | .01 | .6663 | .6663 | .6663 | .0001 |
| 64 | .05 | 1.0000 | 1.0000 | 1.0000 | .0000 |

The analogous Rademacher P0 spread reached 26.0 points at `K=1, rho=.02` and
21.2 points at `K=1, rho=.05`. Gaussian projection therefore solves a real
small-K shape effect rather than merely increasing K until it averages away.

Absolute detection rates across the two runs should not yet be compared as a
power claim: the Gaussian run used substantially more calibration draws and
the six-prompt calibration set remains inadequate. The valid comparison here
is support spread within each calibrated family.

## Local materialized-projection cost

On the local NumPy CPU path with `N=16,384` float32 values:

| K | Rademacher median | Gaussian median | Gaussian/Rademacher | Two sketches |
|---:|---:|---:|---:|---:|
| 8 | 0.442 ms | 1.499 ms | 3.39x | 64 B |
| 16 | 1.507 ms | 5.041 ms | 3.35x | 128 B |
| 32 | 3.107 ms | 7.312 ms | 2.35x | 256 B |
| 64 | 7.008 ms | 14.324 ms | 2.04x | 512 B |

Coefficient generation dominates both paths. Gaussian improves statistical
symmetry without increasing evidence bytes, but costs roughly 2--3.4x in this
unoptimized materialized implementation. This is a microbenchmark, not the
three-node deployment overhead. A production implementation should use a
specified counter-based PRG and fused generation/matvec before making a systems
claim.

## Decision

PACT-G is the stronger statistical design and should be the default candidate
for strong Route B. PACT-R remains a cheaper ablation. Neither fixes the
six-prompt calibration failure, and neither is secure if the realized seed is
known before attack commitment.

## Artifacts

- `pact_projection.py --family gaussian`: matched experiment.
- `validate_gaussian_sampler.py`: dense-versus-Gram validation.
- `benchmark_projection_cost.py`: local materialized cost benchmark.
- `results/gaussian_p0/`: complete Gaussian results and plot.
- `results/projection_benchmark/`: timing CSV and metadata.
