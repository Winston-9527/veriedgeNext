# exp_e5_20260512_measured_profile_mainline

- This is the refreshed `E5` summary after fixing the infeasible placement accounting.
- It is built from:
  - `exp_e2_20260511_material_tamper_full_matrix_selected_operating_points.csv`
  - `exp_e2_20260511_material_tamper_full_matrix_attack_summary.csv`
  - `exp_e4_20260511_equal_budget_live_ab_main_table.csv`
  - `exp_e5_20260511_verification_profile_matrix.csv`
- The policy replay itself was rerun on `20260512` so the summary table now reports both:
  - `unverifiable_placement_rate`
  - `infeasible_under_alpha_beta_rate`

## Current interpretation

- `unverifiable_placement_rate` is narrow: it only counts placements whose `risk_class == unverifiable`.
- `infeasible_under_alpha_beta_rate` is the policy-facing constraint metric and should be used in the paper.
- Under this corrected metric, ordinary policies still choose many infeasible placements:
  - `single_task`: about `29.5%` to `48%`
  - `queued_8`: about `30%` to `48%`
- `risk_constrained` and `adaptive_verifier` reduce the infeasible rate to `0.0` in both workloads.
- This makes the E5 conclusion stronger and clearer: verification-aware policies are valuable primarily because they avoid infeasible / high-risk placements, not because older summaries happened to show low `unverifiable` rates.
