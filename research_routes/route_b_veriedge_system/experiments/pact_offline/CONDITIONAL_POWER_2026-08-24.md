# PACT-G exact conditional power and boundary-aware K sizing

Date: 2026-08-24  
Status: exact projection-layer calculation; excludes prompt-distribution error

## Purpose

This experiment removes the six-prompt calibration problem by asking an ideal
conditional question: if the honest full residual energy of each prompt were
known, how many Gaussian projection rows would be required for a 1% conditional
false-positive rate and a target detection power?

For honest energy `F_h`, attack energy `F_a = F_h + rho^2`, and K rows, the 1%
threshold and attack power follow exactly from chi-square quantiles. No Monte
Carlo approximation and no support assumption are involved.

## Result

Projection rows required across the 12 evaluation prompts:

| Boundary | rho | Median energy ratio | K for 90% power, median/max | K for 95% power, median/max |
|---|---:|---:|---:|---:|
| C1 | .01 | 7.83x | 6 / 15 | 8 / 19 |
| C1 | .02 | 28.32x | 3 / 5 | 4 / 6 |
| C1 | .05 | 171.77x | 2 / 2 | 2 / 3 |
| C2 | .01 | 7.60x | 7 / 16 | 8 / 20 |
| C2 | .02 | 27.39x | 3 / 5 | 4 / 6 |
| C2 | .05 | 165.93x | 2 / 2 | 2 / 3 |
| C3 | .01 | 1.38x | 247 / 760 | 303 / 928 |
| C3 | .02 | 2.51x | 30 / 72 | 37 / 89 |
| C3 | .05 | 10.44x | 5 / 8 | 6 / 10 |

## Interpretation

C1 and C2 have low honest residual energy, so even rho=.01 creates a large
energy ratio and needs at most about K=20 for 95% conditional power. At C3, the
same attack is only a 1.38x increase over honest drift. Median 95% power needs
K=303 and the worst observed prompt needs K=928.

This proves that one global K policy is inefficient and, at Kmax=256,
insufficient for the hardest C3 rho=.01 cases even under perfect calibration.
The adaptive-policy experiment's C3 inconclusive rate is therefore not merely
an implementation artifact; it reflects an intrinsic signal-to-drift limit.

Strong Route B should make K boundary- and target-aware:

- C1/C2: start near K=8 and cap around K=32 for the tested range;
- C3, rho>=.02 target: a cap around K=128 covers the observed conditional
  requirement;
- C3, rho=.01 target: permit K near 1024, invoke a stronger per-block/full
  verifier, or explicitly decline that sensitivity target.

The calculation is optimistic: it assumes prompt-specific honest energy and
therefore excludes prompt-distribution uncertainty. Real deployment requires
additional calibration data on top of these projection budgets.

## Artifacts

- `conditional_power.py`: exact chi-square power calculation.
- `results/conditional_power/power_by_prompt.csv`: prompt-level K requirements.
- `results/conditional_power/power_curves.csv`: selected-K power curves.
- `results/conditional_power/power_aggregate.csv`: table above.
