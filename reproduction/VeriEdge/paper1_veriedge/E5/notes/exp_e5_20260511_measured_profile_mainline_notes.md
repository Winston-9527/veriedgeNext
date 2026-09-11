# exp_e5_20260511_measured_profile_mainline

- This is the current recommended `E5` result line.
- It is built from:
  - `exp_e2_20260511_material_tamper_full_matrix_selected_operating_points.csv`
  - `exp_e2_20260511_material_tamper_full_matrix_attack_summary.csv`
  - `exp_e4_20260511_equal_budget_live_ab_main_table.csv`
  - `exp_e5_20260511_verification_profile_matrix.csv`
- The measured-profile policy replay replaces the older `20260504` strict/semistrict `E5` lines for final reporting.

## Why older E5 runs are stale

- Older `E5` runs consumed verifier profiles derived before:
  - `relative-std` tamper
  - per-prompt independent tamper seeds
  - refreshed `E4` equal-budget overhead
- They remain useful as exploratory references, but should not be cited as the final policy result.

## Current interpretation

- `risk_constrained` and `adaptive_verifier` now provide the cleanest verification-aware policies.
- They substantially lower false-dispute risk and eliminate unverifiable placements.
- They trade off some latency/goodput against stronger verification feasibility.
