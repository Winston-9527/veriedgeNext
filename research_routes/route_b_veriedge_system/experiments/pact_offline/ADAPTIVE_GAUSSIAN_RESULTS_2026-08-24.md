# PACT-G adaptive evidence experiment

Date: 2026-08-24  
Status: projection-policy simulation; calibration threshold remains smoke-only

## Policy

PACT-G starts with `K=8` and expands through `16, 32, 64, 128, 256` only while
the confidence interval for full residual energy crosses the boundary threshold.
For a committed residual,

`K T_K / F_2 ~ chi-square_K`,

so each interval uses exact chi-square quantiles. A total two-sided projection
error budget `beta=.01` is divided by Bonferroni across the six looks, giving
simultaneous coverage without treating repeated looks as independent evidence.

- `PASS` when the upper confidence endpoint is at or below the threshold.
- `FAIL` when the lower endpoint is above the threshold.
- `INCONCLUSIVE` after K=256 if neither condition holds.

The boundary threshold is still the maximum exact energy among only six
calibration prompts. The experiment evaluates projection uncertainty and
adaptive evidence cost; it does not repair or validate that threshold.

## Aggregate results

Each prompt/strength uses 50,000 Monte Carlo trials.

| Boundary | Input | PASS | FAIL | INCONCLUSIVE | Mean K |
|---|---|---:|---:|---:|---:|
| C1 | honest | 75.1% | 0.10% | 24.8% | 96 |
| C1 | rho=.01 | 0.001% | 100.0% | 0.0% | 19 |
| C1 | rho=.02 | 0.0% | 100.0% | 0.0% | 8.3 |
| C2 | honest | 75.1% | 0.12% | 24.8% | 98 |
| C2 | rho=.01 | 0.001% | 100.0% | 0.0% | 19 |
| C2 | rho=.02 | 0.0% | 100.0% | 0.0% | 8.3 |
| C3 | honest | 31.8% | 15.6% | 52.6% | 216 |
| C3 | rho=.01 | 0.61% | 33.6% | 65.7% | 212 |
| C3 | rho=.02 | 0.006% | 99.99% | 0.004% | 50 |
| C3 | rho=.05 | 0.0% | 100.0% | 0.0% | 8.7 |

## Interpretation

The adaptive mechanism is useful when calibration separates the regimes:
strong attacks stop near K=8, rho=.01 attacks at C1/C2 stop near K=19, and the
policy avoids charging every task for K=256.

The C3 result is equally important. Its honest distribution is not covered by
the six-prompt threshold, producing 15.6% false failures. The policy correctly
leaves most borderline C3 cases inconclusive, but cannot distinguish unseen
honest drift from rho=.01 attack energy: both consume about K=212 and the latter
remains inconclusive 65.7% of the time.

Thus adaptive K solves projection uncertainty and evidence allocation. It does
not solve calibration uncertainty. Strong Route B needs both layers:

1. exact/time-uniform projection intervals for the realized seed;
2. a separately justified prompt-level honest envelope with enough independent
   calibration prompts.

## Artifacts

- `adaptive_gaussian_policy.py`: exact sequential simulation.
- `results/adaptive_gaussian/adaptive_by_prompt.csv`: prompt-level outcomes.
- `results/adaptive_gaussian/adaptive_aggregate.csv`: table above.
- `results/adaptive_gaussian/adaptive_verdicts.png`: verdict/cost plot.
