# PACT prompt-level calibration audit

Date: 2026-08-24  
Status: completed local audit; identifies a data/calibration blocker

## Result

The high held-out honest rate in P0 is not primarily random-projection error.
It remains when projection uncertainty is removed completely and the exact
full residual energy is used.

Using the maximum exact energy among the six calibration prompts as the most
conservative finite empirical threshold gives:

| Boundary | Honest eval prompts above threshold | Ideal attack detection, rho=.01 | Ideal attack detection, rho>=.02 |
|---|---:|---:|---:|
| C1 | 8.3% | 100% | 100% |
| C2 | 16.7% | 100% | 100% |
| C3 | 33.3% | 83.3% | 100% |

The attack column is an optimistic infinite-K oracle for an orthogonal attack:
its exact normalized residual energy is the honest energy plus `rho^2`. It is
not a deployable result because the same finite threshold already misclassifies
too many honest prompts.

## Why six prompts cannot support a 1% claim

For a one-sided, distribution-free split-conformal threshold with `n`
independent calibration scores, the smallest nonzero miscoverage resolution is
`1/(n+1)`. Six prompts therefore support no finer level than 14.3%. Repeated
projection seeds do not increase `n`; they resample the check randomness for
the same six prompt residuals.

A nontrivial finite 1% threshold requires at least 99 independent calibration
prompts. With fewer, the valid distribution-free choice is effectively an
infinite threshold, which detects nothing.

This sample-size statement is about a distribution-free guarantee. A
parametric tail model could use fewer prompts, but would add a modeling
assumption that must be validated independently.

## Rerun audit

The directory `stack_02_rerun_eval_12` does not add replication: every candidate
NPZ is hash-identical to its counterpart in `stack_02_eval_12`, and all loaded
tensors are value-identical. It must not be counted as a second execution or as
12 additional calibration prompts.

## Consequence for strong Route B

PACT's check geometry remains promising, but `INCONCLUSIVE` cannot manufacture
information absent from calibration. With only six prompts, a high observed
energy is statistically compatible with either an attack or unseen honest
prompt drift. Relabeling every exceedance as `INCONCLUSIVE` would suppress false
failures only by abstaining on precisely the cases the detector must decide.

The next defensible experiment therefore requires new data:

1. at least 99 independent calibration prompts per claimed deployment
   distribution for a distribution-free 1% target;
2. separate held-out prompts for FPR reporting;
3. genuine repeat executions to separate prompt variation from runtime
   nondeterminism;
4. boundary-conditional calibration, since C3 has a materially wider and less
   stable honest-energy distribution than C1/C2.

Until then, the valid claim is limited to sparse-support geometry under the
observed captures, not calibrated end-to-end verification.

## Artifacts

- `calibration_audit.py`: exact-energy audit.
- `results/calibration_audit/energy_by_prompt.csv`: all prompt energies.
- `results/calibration_audit/calibration_summary.csv`: boundary-level shift.
- `results/calibration_audit/infinite_k_oracle.csv`: optimistic attack oracle.
- `results/calibration_audit/prompt_energy.png`: prompt distributions.
