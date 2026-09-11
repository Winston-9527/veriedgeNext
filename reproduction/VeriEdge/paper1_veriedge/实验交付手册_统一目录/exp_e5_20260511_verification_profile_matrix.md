# exp_e5_20260511_verification_profile_matrix

- Built from current strict measured results.
- Selected operating points source: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260511_material_tamper_full_matrix_selected_operating_points.csv
- Material tamper summary source: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260511_material_tamper_full_matrix_attack_summary.csv
- Overhead source: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E4/tables/exp_e4_20260511_equal_budget_live_ab_main_table.csv
- Manifest: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E5/notes/exp_e5_20260511_verification_profile_matrix_manifest.json

## Coverage

- rows: 30
- feasible rows under alpha=0.10, beta=0.90: 16

## Notes

- `eval_honest_hetero_fpr` is recomputed on held-out eval captures using the selected operating point for each pair x variant.
- `material_*` metrics come from the full material-tamper matrix (gaussian, stale_replay, wrong_prompt).
- `challenge_latency_ms` is exact for variants with E4 equal-budget measurements and estimated by interpolation for `projcos8`.
- `eval_honest_homo_fpr` is only filled when a compatible rerun/absrepro donor exists.
