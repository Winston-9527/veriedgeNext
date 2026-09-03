# exp_e5_20260512_verification_profile_matrix

- Built from current strict measured results.
- Selected operating points source: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_selected_operating_points.csv
- Material tamper summary source: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_attack_summary.csv
- Overhead source: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E4/tables/exp_e4_20260512_equal_budget_live_ab_main_table.csv
- Manifest: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E5/notes/exp_e5_20260512_verification_profile_matrix_manifest.json

## Coverage

- rows: 30
- feasible rows under alpha=0.10, beta=0.90: 15

## Notes

- `eval_honest_hetero_fpr` is recomputed on held-out eval captures using the selected operating point for each pair x variant.
- `material_*` risk metrics use the paper-main attack scope: gaussian, cross_prompt_stale_substitution, wrong_shard_output, and layer_skip.
- `same_prompt_old_run_replay` is retained only as a negative control and is not used for placement risk classification.
- `scale_perturbation` is retained as a direction-preserving limitation column and is not mixed into the main material-risk threshold.
- `challenge_latency_ms` is exact for variants with E4 equal-budget measurements and estimated by interpolation for `projcos8`.
- The exact E4 equal-budget overhead measurement comes from the A/B live setup; this profile matrix generalizes that overhead model across pairs for placement replay.
- This table is therefore an input to measured-profile placement replay, not evidence of per-pair live online scheduler deployment.
- `eval_honest_homo_fpr` is only filled when a compatible rerun/absrepro donor exists.
