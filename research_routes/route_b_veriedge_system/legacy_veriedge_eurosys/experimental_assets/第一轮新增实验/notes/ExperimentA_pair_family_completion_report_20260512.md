# Experiment A Pair-Family Completion Report (2026-05-12)

## What Was Added

This run closes the audit gap that the previous Experiment A artifact only formalized the `B/D` hard pair.

New script:

- [`build_e2_experiment_a_pair_family_projcos.py`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/build_e2_experiment_a_pair_family_projcos.py)

New artifacts:

- candidate grid:
  [`exp_e2_20260512_experiment_a_pair_family_projcos_candidate_grid.csv`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_experiment_a_pair_family_projcos_candidate_grid.csv)
- selected held-out summary:
  [`exp_e2_20260512_experiment_a_pair_family_projcos_selected_summary.csv`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_experiment_a_pair_family_projcos_selected_summary.csv)
- honest-hetero first-mismatch detail:
  [`exp_e2_20260512_experiment_a_pair_family_projcos_hetero_mismatch_detail.csv`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_experiment_a_pair_family_projcos_hetero_mismatch_detail.csv)
- tamper first-mismatch detail:
  [`exp_e2_20260512_experiment_a_pair_family_projcos_tamper_mismatch_detail.csv`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_experiment_a_pair_family_projcos_tamper_mismatch_detail.csv)
- gap distribution:
  [`exp_e2_20260512_experiment_a_pair_family_projcos_gap_distribution.csv`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_experiment_a_pair_family_projcos_gap_distribution.csv)
- figure:
  [`exp_e2_20260512_experiment_a_pair_family_projcos_pair_family_fpr_tpr.png`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_experiment_a_pair_family_projcos_pair_family_fpr_tpr.png)
- run notes:
  [`exp_e2_20260512_experiment_a_pair_family_projcos_notes.md`](/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/notes/exp_e2_20260512_experiment_a_pair_family_projcos_notes.md)

## Coverage

The new artifact covers the required pair family under the same strict `40 calibration / 200 held-out evaluation` protocol:

- `A/B`
- `A/C`
- `A/D`
- `B/D`

Methods:

- `scalar16`
- `scalar64`
- `projcos4`
- `projcos8`
- `projcos16`

Coverage checks:

- candidate rows: `800`
- selected summary rows: `20`
- honest-hetero detail rows: `4000`
- tamper detail rows: `4000`
- gap distribution rows: `12000`

## Main Held-Out Results

| Pair | Variant | Feasible calib points | Selected feasible | Eval FPR | Tamper TPR | LocAcc |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A/B | scalar16 | 0 | 0 | 0.150 | 1.000 | 1.000 |
| A/B | scalar64 | 0 | 0 | 0.415 | 1.000 | 1.000 |
| A/B | projcos4 | 35 | 1 | 0.020 | 1.000 | 1.000 |
| A/B | projcos8 | 30 | 1 | 0.080 | 1.000 | 1.000 |
| A/B | projcos16 | 30 | 1 | 0.120 | 1.000 | 1.000 |
| A/C | scalar16 | 0 | 0 | 0.110 | 1.000 | 1.000 |
| A/C | scalar64 | 0 | 0 | 0.305 | 1.000 | 1.000 |
| A/C | projcos4 | 30 | 1 | 0.045 | 1.000 | 1.000 |
| A/C | projcos8 | 30 | 1 | 0.075 | 1.000 | 1.000 |
| A/C | projcos16 | 30 | 1 | 0.135 | 1.000 | 1.000 |
| A/D | scalar16 | 3 | 1 | 0.090 | 1.000 | 1.000 |
| A/D | scalar64 | 0 | 0 | 0.380 | 1.000 | 1.000 |
| A/D | projcos4 | 35 | 1 | 0.020 | 1.000 | 1.000 |
| A/D | projcos8 | 35 | 1 | 0.065 | 1.000 | 1.000 |
| A/D | projcos16 | 30 | 1 | 0.065 | 1.000 | 1.000 |
| B/D | scalar16 | 0 | 0 | 0.245 | 1.000 | 1.000 |
| B/D | scalar64 | 0 | 0 | 0.590 | 1.000 | 1.000 |
| B/D | projcos4 | 34 | 1 | 0.075 | 1.000 | 1.000 |
| B/D | projcos8 | 30 | 1 | 0.075 | 1.000 | 1.000 |
| B/D | projcos16 | 30 | 1 | 0.065 | 1.000 | 1.000 |

## Audit Issues Addressed

### P1: Pair-family coverage

Resolved. Experiment A now has one same-protocol artifact for `A/B`, `A/C`, `A/D`, and `B/D`.

### P2: Silent fallback when no feasible calibration point exists

Resolved. The selected summary now includes:

- `calib_feasible_count`
- `selected_from_feasible`
- `selection_fallback_reason`

The run notes also list every fallback row explicitly.

### P2: First-mismatch and gap distributions

Resolved for the Experiment A artifact.

First-mismatch data:

- honest-hetero detail table records per-prompt first mismatch
- tamper detail table records per-prompt first mismatch and localization correctness
- selected summary includes C1/C2/C3 mismatch counts

Gap data:

- projected-token variants report `mean_projected_cosine_gap`
- scalar variants report `mean_sampled_abs_gap`
- each row includes the selected threshold and whether the gap exceeded it

## Important Interpretation Note

The new family artifact recomputes scalar operating points using the shared current selection rule. Some scalar rows therefore differ from the older B/D-only script. This is intentional: the new artifact is the replacement same-protocol Experiment A table, and it makes infeasible fallback rows explicit.

The key projected-token B/D results remain consistent with the previous hard-pair result:

- `projcos4`: `FPR = 0.075`, `TPR = 1.0`, `LocAcc = 1.0`
- `projcos8`: `FPR = 0.075`, `TPR = 1.0`, `LocAcc = 1.0`
- `projcos16`: `FPR = 0.065`, `TPR = 1.0`, `LocAcc = 1.0`

## Remaining Caveat

The script emits the previously observed `projcos` matmul runtime warnings for a small number of non-finite or extreme activation values. The run completes and outputs are self-consistent, but final camera-ready artifact generation should either suppress these warnings after sanitization or add a stronger numeric clipping guard in `project_prefill_signature`.
