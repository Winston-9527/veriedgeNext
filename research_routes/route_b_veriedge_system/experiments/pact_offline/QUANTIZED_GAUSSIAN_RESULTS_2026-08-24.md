# PACT-G coefficient implementation study

Date: 2026-08-24  
Status: completed local geometry, coverage, real-residual, and cost experiments

## Question

Can a protocol generate deterministic Gaussian-like coefficients from fixed
lookup tables without losing PACT-G's support invariance or interval coverage?

The lookup construction maps uniform PRG output to fixed inverse-normal
mid-quantiles, normalizes the table to unit variance, and contains no zero
coefficient. LUT8 consumes one PRG byte per coefficient; LUT16 consumes two.

## Coefficient geometry

Independent calibration/test experiments use supports 1, 16, and 256, K from 1
to 32, and conditional energy ratios 1.4, 2, and 8. High-precision LUT/Gaussian
runs use 100,000 calibration and 100,000 test draws.

| Family | Worst attack support spread | Interpretation |
|---|---:|---|
| Rademacher | 65.51% | reject for small-K support invariance |
| 3-bit mid-rise Gaussian | 7.88% | reject |
| 4-bit mid-rise Gaussian | 5.30% | reject |
| 8-bit mid-rise Gaussian | 0.434% | statistically close, but still generated from normals |
| 8-bit inverse-CDF LUT | 0.777% | fast implementation candidate |
| 16-bit inverse-CDF LUT | 0.368% | nearly Gaussian |
| Ideal Gaussian | 0.302% | Monte Carlo reference |

All quantized/LUT families are normalized to variance one and have zero
empirical zero-coefficient rate.

## Chi-square interval audit

LUT coefficients are not mathematically Gaussian, so exact chi-square intervals
do not follow automatically.

- LUT8's worst marginal nominal-99% coverage is 98.461% at K=1, support=1.
  It therefore must not inherit the exact marginal claim.
- With the six-look Bonferroni intervals used by the adaptive protocol, LUT8's
  simultaneous empirical coverage is 99.15%--99.49% over tested supports.
- LUT16's worst marginal coverage is 98.960%, indistinguishable at this sample
  size from ideal Gaussian's 98.968%--99.014% range.
- LUT16's simultaneous coverage is 99.12%--99.18%, matching Gaussian.

These are empirical coverage results, not a proof. The ideal-Gaussian model
retains the exact chi-square statement; a LUT implementation needs either a
finite-table concentration argument or conservatively validated intervals.

## Real heterogeneous residuals

The full adaptive-candidate P0 pipeline was run with LUT8 and LUT16 on six real
prompt/checkpoints. A 512-draw LUT16 run showed an apparent 2.38-point spread at
the weakest K=4, rho=.01 setting. A focused rerun with 256 selection draws and
4,096 independent final draws resolved it as sampling noise:

| K | rho | support 1 | support 16 | support 256 | max--min |
|---:|---:|---:|---:|---:|---:|
| 1 | .01 | .1660 | .1654 | .1624 | .0036 |
| 1 | .05 | .6724 | .6708 | .6732 | .0024 |
| 4 | .01 | .3886 | .3859 | .3853 | .0033 |
| 4 | .05 | .9545 | .9572 | .9567 | .0027 |

Thus LUT16 preserves support invariance on the measured real residuals under
the same white-box candidate selection and harm-preservation constraints.

## Local materialized cost

Same-run NumPy CPU medians for N=16,384:

| K | Rademacher | LUT8 | LUT16 | online Gaussian |
|---:|---:|---:|---:|---:|
| 8 | 0.387 ms | 0.467 ms | 0.638 ms | 1.110 ms |
| 16 | 0.962 ms | 1.134 ms | 1.516 ms | 2.435 ms |
| 32 | 2.710 ms | 2.505 ms | 3.499 ms | 5.225 ms |
| 64 | 4.939 ms | 5.273 ms | 6.663 ms | 10.591 ms |

LUT16 is about 37%--43% faster than online Gaussian in this path and remains
within roughly 1.3--1.7x of Rademacher. Evidence bytes are unchanged. Timings
are microbenchmarks, not three-node deployment overhead.

## Design decision

- **PACT-G model:** ideal iid Gaussian coefficients, preserving exact
  rotational invariance and chi-square analysis.
- **PACT-G16 implementation candidate:** a frozen 65,536-entry float32 LUT fed
  by a counter-based cryptographic PRG. Current little-endian table SHA-256 is
  `8babbcaf96568f10165a1eab530c0e5c92d04de96761b6dbb3dadfa94baba37f`.
- **PACT-G8 optimization:** acceptable only with conservative, separately
  validated intervals.
- 3/4-bit and Rademacher coefficients remain ablations, not defaults.

Before a protocol claim, the LUT values, byte ordering, PRG, counter derivation,
and accumulation order must be frozen. LUT16's interval coverage also needs a
formal bound or a much broader preregistered validation corpus.

## Artifacts

- `quantized_gaussian.py`: coefficient and coverage experiments.
- `results/lut8_high_precision/`: LUT8 high-precision results.
- `results/lut16_high_precision/`: LUT16 high-precision results.
- `results/lut16_p0/`: full real-residual run.
- `results/lut16_focused/`: focused 4,096-draw real-residual confirmation.
- `results/projection_benchmark_lut16/`: same-run cost comparison.
