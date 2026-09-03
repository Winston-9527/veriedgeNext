# exp_e5_20260512_measured_profile_mainline

This is the refreshed E5 risk-constrained placement run aligned with the latest 20260512 Experiment C/D outputs and the handbook 7.6 requirement.

It should be described as a **measured-profile policy replay under a modeled placement workload**, not as a live online scheduler deployment.

## Inputs

- Verification profile matrix: `paper1_veriedge/E5/tables/exp_e5_20260512_verification_profile_matrix.csv`
- Experiment C selected operating points: `paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_selected_operating_points.csv`
- Experiment C material-tamper summary: `paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_attack_summary.csv`
- Experiment D overhead table: `paper1_veriedge/E4/tables/exp_e4_20260512_equal_budget_live_ab_main_table.csv`

## Risk Scope

- Placement risk classification uses the paper-main attack scope: `gaussian`, `cross_prompt_stale_substitution`, `wrong_shard_output`, and `layer_skip`.
- `same_prompt_old_run_replay` is retained as a negative control, not as a main material-tamper benchmark.
- `scale_perturbation` is retained as a direction-preserving limitation column. It is not mixed into the main placement threshold because the paper claim is now scoped to direction-changing / semantic material tamper, with scale-only attacks discussed as a boundary case.

## Profile Matrix Coverage

- Rows: 30 = 6 pairs x 5 variants.
- Feasible rows under alpha=0.10 and beta=0.90: 15.
- Risk classes: 15 low-risk, 4 medium-risk, 5 high-risk, 6 unverifiable.
- Overhead sources: exact E4 measurements for 24 rows; interpolated `projcos8` overhead for 6 rows.

## Adaptive-Verifier Scope

- The current adaptive prototype selects among the placement candidates present in the measured-profile input set.
- In this run, that means the meaningful verifier upgrade path is primarily `scalar16 -> projcos4`.
- Although the profile matrix contains `projcos8` and `projcos16`, the replayed placement candidate set is not yet a full multilevel online verifier scheduler.

## Policy Result Summary

The result supports the intended E5 claim: verification-aware placement is not optimized to minimize latency. Under similar latency/goodput SLO, it avoids infeasible/high-risk placements and reduces false-dispute risk.

| workload | policy | latency_s | success | goodput | challenge_rate | expected_challenge_work_ms | false_dispute_risk | infeasible_rate | risk_adjusted_goodput |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| single_task | random | 1.042742 | 0.920 | 0.184689 | 0.055 | 0.295493 | 0.056100 | 0.315 | 0.174328 |
| single_task | cost_only | 0.971796 | 0.890 | 0.178667 | 0.025 | 0.145264 | 0.027000 | 0.300 | 0.173843 |
| single_task | reputation_aware | 1.007899 | 0.940 | 0.188704 | 0.060 | 0.284592 | 0.054000 | 0.480 | 0.178514 |
| single_task | network_aware | 1.007899 | 0.950 | 0.190712 | 0.045 | 0.284592 | 0.054000 | 0.480 | 0.180413 |
| single_task | risk_constrained | 1.007899 | 0.945 | 0.189708 | 0.005 | 0.054005 | 0.009600 | 0.000 | 0.187887 |
| single_task | adaptive_verifier | 1.007899 | 0.930 | 0.186697 | 0.005 | 0.054005 | 0.009600 | 0.000 | 0.184905 |
| queued_8 | random | 12.781498 | 0.915 | 4.741068 | 0.085 | 0.327945 | 0.062425 | 0.335 | 4.445107 |
| queued_8 | cost_only | 51.636917 | 0.880 | 1.485707 | 0.015 | 0.145264 | 0.027000 | 0.300 | 1.445593 |
| queued_8 | reputation_aware | 36.310436 | 0.945 | 2.160597 | 0.070 | 0.284592 | 0.054000 | 0.480 | 2.043924 |
| queued_8 | network_aware | 36.310436 | 0.945 | 2.160597 | 0.055 | 0.284592 | 0.054000 | 0.480 | 2.043924 |
| queued_8 | risk_constrained | 36.310436 | 0.945 | 2.160597 | 0.025 | 0.054005 | 0.009600 | 0.000 | 2.139855 |
| queued_8 | adaptive_verifier | 36.310436 | 0.980 | 2.240619 | 0.010 | 0.054005 | 0.009600 | 0.000 | 2.219109 |

## Figures

- `paper1_veriedge/E5/figures/exp_e5_20260512_measured_profile_mainline_single_task_pareto.png`
- `paper1_veriedge/E5/figures/exp_e5_20260512_measured_profile_mainline_single_task_policy_compare.png`
- `paper1_veriedge/E5/figures/exp_e5_20260512_measured_profile_mainline_single_task_risk_stack.png`
- `paper1_veriedge/E5/figures/exp_e5_20260512_measured_profile_mainline_queued_8_pareto.png`
- `paper1_veriedge/E5/figures/exp_e5_20260512_measured_profile_mainline_queued_8_policy_compare.png`
- `paper1_veriedge/E5/figures/exp_e5_20260512_measured_profile_mainline_queued_8_risk_stack.png`

## Caveats

- `projcos8` challenge overhead is interpolated from `projcos4` and `projcos16`; avoid making it the main headline unless an exact E4 measurement is added.
- The placement replay uses measured verification profiles plus modeled latency/success placement parameters. It is a measured-profile policy replay, not a fully online deployment trace or live scheduler deployment.
- The placement latency/success path is driven by modeled parameters such as `base_fixed_ms`, `per_char_ms`, and `base_success`, so E5 should be presented as a profile-driven simulator anchored by measured verifier data.
- E4 overhead is measured on the A/B live equal-budget setup and then generalized through the verification profile matrix; do not imply that every pair has its own direct overhead measurement.
- `mean_verifier_workload_ms_per_task` remains in the machine-readable CSV for compatibility. The paper-facing challenge workload metric is `expected_challenge_workload_ms_per_task`.
