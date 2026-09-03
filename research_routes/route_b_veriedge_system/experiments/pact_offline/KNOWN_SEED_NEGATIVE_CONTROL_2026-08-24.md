# PACT-G known-seed nullspace negative control

Date: 2026-08-24  
Status: completed; validates the commit-before-seed threat boundary

## Question

Does Gaussian projection remain sound if the adversary learns the realized
matrix before committing its boundary tensor?

## Attack

For each realized `K x N` matrix `A`, choose `K+2` tensor coordinates. On those
coordinates solve:

- `A delta = 0` (`K` projection constraints);
- `<delta, r_honest> = 0` (one harm-preservation constraint).

There are `K+2` variables and at most `K+1` independent constraints, so a
nonzero solution exists with probability one. Scale it to any requested
relative L2 strength rho. The construction is sparse, does not cancel measured
heterogeneous drift, and is exactly invisible to the realized projection.

This attack is intentionally outside PACT-G's commit-before-seed model: it is a
negative control that tests whether seed ordering is actually necessary.

## Result

Across six prompt/checkpoints, 64 fresh matrices per K, and rho in
`.01, .02, .05`:

| K | Attack support | Honest detection | Known-seed attack detection |
|---:|---:|---:|---:|
| 8 | 10 | 3.91% | 3.91% |
| 32 | 34 | 11.98% | 11.98% |
| 64 | 66 | 13.28% | 13.28% |

The rates are identical for every rho, and the maximum per-pair rate difference
is exactly zero.

Constraint audit:

- maximum relative-L2 error: `1.39e-17`;
- maximum relative nullspace residual: `9.66e-15`;
- maximum absolute cosine with honest residual: `1.47e-15`.

By contrast, attacks fixed before the unknown seed in the Gaussian P0 run are
detected according to their energy: at K=8 the mean rates for rho `.01/.02/.05`
are about `39.3%/69.2%/99.0%`, and they rise with K. Absolute rates remain
smoke-calibrated, but the timing contrast is unambiguous.

## Consequence

The paper must not present dense Gaussian projection alone as the defense. Any
K-row linear sketch has an `(N-K)`-dimensional nullspace once its matrix is
known. PACT-G's security unit is the ordering protocol:

1. bind the exact transmitted tensor to an immutable commitment;
2. obtain an unpredictable, task/boundary-specific seed afterward;
3. reject late or replaceable commitments;
4. never reuse a revealed matrix for a new adaptive commitment.

“Frequently refreshed” is insufficient wording. The required property is
**unpredictability at attack commitment**.

## Artifacts

- `known_seed_nullspace.py`: attack and constraint audit.
- `results/known_seed/known_seed_by_pair.csv`: complete results.
- `results/known_seed/known_seed_aggregate.csv`: aggregate table.
- `results/known_seed/constraint_audit.csv`: numerical validation.
