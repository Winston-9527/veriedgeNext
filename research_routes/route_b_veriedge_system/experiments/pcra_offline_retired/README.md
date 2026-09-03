# PCRA offline experiment (retired)

> Historical negative-result asset. PCRA is not the active Route B protocol.
> Its sparse-support detection ceiling motivated the move to dense randomized
> PACT projections. Preserve this directory for provenance; start new work in
> `../pact_offline/`.

This directory contains the first executable experiment for the stronger Route
B check design. It evaluates three statistics over the same post-commit random
opening:

- `spike`: maximum absolute normalized residual;
- `energy`: mean squared normalized residual;
- `directional`: absolute sign-aligned mean residual.

The honest residual is measured from two real heterogeneous execution stacks.
Thresholds are calibrated on 6 prompt pairs and evaluated on 12 held-out prompt
pairs, across checkpoints C1--C3. Synthetic perturbations are added after the
measured residual at a fixed relative L2 budget.

The default uses 2,048 coordinate challenges per calibration prompt and 64 per
evaluation prompt. The comparatively large calibration count is deliberate:
with a 1% combined false-dispute budget split across three statistics, the
per-statistic tail probability is roughly 0.33%, and smaller Monte Carlo runs
gave visibly unstable thresholds in the presence of rare drift outliers.

The key protocol contrast is `sample_null`:

- `known_coordinates`: the attacker sees the exact opening coordinates before
  committing and places all attack energy outside them;
- `post_commit`: the attacker commits against a guessed coordinate set, after
  which the verifier independently draws the actual opening coordinates.

Run a fast validation:

```powershell
python research_routes/route_b_veriedge_system/experiments/pcra_offline_retired/pcra_offline.py --smoke `
  --output-dir research_routes/route_b_veriedge_system/experiments/pcra_offline_retired/results/smoke
```

Run the default experiment:

```powershell
python research_routes/route_b_veriedge_system/experiments/pcra_offline_retired/pcra_offline.py
```

Outputs include calibrated thresholds, per-checkpoint and aggregate rates, an
experiment summary, and a detection-curve figure.

## White-box adaptive attack

`adaptive_attack.py` optimizes one fixed perturbation against all three tests
using expectation over random challenges. Optimization, candidate selection,
and final evaluation use disjoint coordinate draws, so the attack cannot learn
the realized test opening.

All tested perturbations are projected orthogonal to the measured honest
residual. Consequently the optimizer cannot lower detection merely by repairing
heterogeneous drift: the final squared discrepancy is the sum of the honest
residual energy and the injected perturbation energy.

```powershell
python research_routes/route_b_veriedge_system/experiments/pcra_offline_retired/adaptive_attack.py --smoke
python research_routes/route_b_veriedge_system/experiments/pcra_offline_retired/adaptive_attack.py
```

The local default deliberately covers only two held-out prompts at C1--C3. It
is a go/no-go stress test, not the final full-corpus evaluation.

The harm-preserving four-q run and its interpretation are recorded in
`ADAPTIVE_RESULTS_2026-08-24.md`. Generate its figure with:

```powershell
python research_routes/route_b_veriedge_system/experiments/pcra_offline_retired/plot_adaptive_results.py
```

## Scope limitation

This is a protocol/statistic smoke test over the small anonymized raw-capture
subset included in the repository. Repeated challenge draws increase Monte
Carlo precision but do not create additional independent prompts. Consequently,
the results must not be reported as the paper's final FPR/TPR numbers. The full
claim requires the complete calibration/evaluation corpus, end-to-end attacks,
and confidence intervals clustered by prompt and hardware pair.
