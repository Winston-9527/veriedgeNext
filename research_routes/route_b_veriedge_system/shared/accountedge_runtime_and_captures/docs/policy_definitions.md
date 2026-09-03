# Placement Policy Definitions

## Network-Aware Baseline

This policy ranks candidate placements by network and queue cost. It does not
reject candidates whose verifier signatures fail the task's FPR/TPR/size/cost
targets.

Purpose:
Shows what happens when placement ignores measured verifiability.

## Cost-Only Baseline

This policy ranks candidate placements by latency and challenge cost. It uses a
fixed verifier mode and therefore may select candidates that remain infeasible
under the target verifier thresholds.

Purpose:
Separates cost minimization from verifiability-aware admission.

## Verifiability-Constrained Policy

This policy first applies hard admission:

- FPR <= alpha
- TPR >= beta
- sketch size <= Smax
- challenge cost <= Cmax
- resource and support constraints hold

Only admitted candidates are ranked by latency, queue cost, or availability.

Purpose:
Shows the effect of treating verifiability as a placement-time feasibility
constraint.

## Adaptive Verifier Policy

This policy tries to keep a candidate group but upgrades the sketch mode to the
cheapest verifier profile that satisfies the task target. If no sketch mode is
feasible, the candidate is rejected.

Purpose:
Shows whether sketch-mode selection can preserve goodput while eliminating
inadmissible placements.

## Homogeneous-Only Baseline

This policy restricts candidates to homogeneous device/backend signatures.

Purpose:
Tests the alternative of avoiding heterogeneity rather than making heterogeneous
placements adjudicable.
