# Experiment C Material Tamper Report (2026-05-12)

## Status

- This report supersedes `E2_material_tamper_full_matrix_report_20260507.md`.
- Completed: expanded attack family, statistical/material attack-layer split, localization fields, calibration-feasibility flags, detection-vs-strength sweep, and a replay-to-logits **next-token top-k output-affecting** subset on the focus matrix (`scalar16`, `projcos4`).
- Boundary: output-affecting subset is not yet a full-variant-family result.
- Interpretation change: Experiment C should be written as a tamper-family differentiation study, not as a single scalar-vs-projcos win/loss table.

## Scope

- This rerun is an offline replay experiment on real checkpoint captures, not an online adversarial deployment.
- Main attack families now include gaussian, same_prompt_old_run_replay, cross_prompt_stale_substitution, wrong_shard_output, scale_perturbation, and layer_skip.
- Statistical tamper and material tamper are explicitly separated via `attack_layer`.
- `same_prompt_old_run_replay` is treated as a negative control / rerun-consistency test, not as primary material-tamper evidence.
- `scale_perturbation` is a direction-preserving attack; cosine-only projected-token verification is expected to be weak on it.

## Artifacts

- Selected operating points: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_selected_operating_points.csv
- Attack summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_attack_summary.csv
- Detail table: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_detail.csv
- Strength sweep: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_strength_sweep.csv
- Strength figure: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_material_tamper_full_matrix_strength_sweep_focus.png
- Material focus figure: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_material_tamper_full_matrix_material_focus_panel.png

## Calibration Feasibility

- t4strict_pair_a_vs_b_40_200 / scalar16: no calibration-feasible point; selected calibration FPR=0.125.
- t4strict_pair_a_vs_b_40_200 / scalar64: no calibration-feasible point; selected calibration FPR=0.475.
- t4strict_pair_a_vs_b_rtxint8_40_200 / scalar64: no calibration-feasible point; selected calibration FPR=0.45.
- t4strict_pair_a_vs_c_40_200 / scalar16: no calibration-feasible point; selected calibration FPR=0.175.
- t4strict_pair_a_vs_c_40_200 / scalar64: no calibration-feasible point; selected calibration FPR=0.5.
- t4strict_pair_a_vs_d_40_200 / scalar64: no calibration-feasible point; selected calibration FPR=0.175.
- t4strict_pair_b_vs_d_40_200 / scalar16: no calibration-feasible point; selected calibration FPR=0.2.
- t4strict_pair_b_vs_d_40_200 / scalar64: no calibration-feasible point; selected calibration FPR=0.625.
- t4strict_pair_e_vs_f_40_200 / scalar16: no calibration-feasible point; selected calibration FPR=0.225.
- t4strict_pair_e_vs_f_40_200 / scalar64: no calibration-feasible point; selected calibration FPR=0.55.

## Focus Results

- t4strict_pair_a_vs_b_40_200 / scalar16 / gaussian: layer=statistical_tamper, strength=0.15, TPR=1.0, LocAcc=1.0.
- t4strict_pair_a_vs_b_40_200 / scalar16 / same_prompt_old_run_replay: layer=material_tamper, TPR=0.0, LocAcc=0.0.
- t4strict_pair_a_vs_b_40_200 / scalar16 / cross_prompt_stale_substitution: layer=material_tamper, TPR=0.76, LocAcc=0.76.
- t4strict_pair_a_vs_b_40_200 / scalar16 / wrong_shard_output: layer=material_tamper, TPR=0.76, LocAcc=0.76.
- t4strict_pair_a_vs_b_40_200 / scalar16 / scale_perturbation: layer=material_tamper, strength=0.15, TPR=0.52, LocAcc=0.52.
- t4strict_pair_a_vs_b_40_200 / scalar16 / layer_skip: layer=material_tamper, TPR=0.83, LocAcc=0.83.
- t4strict_pair_a_vs_b_40_200 / projcos4 / gaussian: layer=statistical_tamper, strength=0.15, TPR=1.0, LocAcc=1.0.
- t4strict_pair_a_vs_b_40_200 / projcos4 / same_prompt_old_run_replay: layer=material_tamper, TPR=0.0, LocAcc=0.0.
- t4strict_pair_a_vs_b_40_200 / projcos4 / cross_prompt_stale_substitution: layer=material_tamper, TPR=1.0, LocAcc=1.0.
- t4strict_pair_a_vs_b_40_200 / projcos4 / wrong_shard_output: layer=material_tamper, TPR=1.0, LocAcc=1.0.
- t4strict_pair_a_vs_b_40_200 / projcos4 / scale_perturbation: layer=material_tamper, strength=0.15, TPR=0.0, LocAcc=0.0.
- t4strict_pair_a_vs_b_40_200 / projcos4 / layer_skip: layer=material_tamper, TPR=1.0, LocAcc=1.0.
- t4strict_pair_b_vs_d_40_200 / scalar16 / gaussian: layer=statistical_tamper, strength=0.15, TPR=1.0, LocAcc=1.0.
- t4strict_pair_b_vs_d_40_200 / scalar16 / same_prompt_old_run_replay: layer=material_tamper, TPR=0.0, LocAcc=0.0.
- t4strict_pair_b_vs_d_40_200 / scalar16 / cross_prompt_stale_substitution: layer=material_tamper, TPR=0.95, LocAcc=0.95.
- t4strict_pair_b_vs_d_40_200 / scalar16 / wrong_shard_output: layer=material_tamper, TPR=0.95, LocAcc=0.95.
- t4strict_pair_b_vs_d_40_200 / scalar16 / scale_perturbation: layer=material_tamper, strength=0.15, TPR=0.72, LocAcc=0.72.
- t4strict_pair_b_vs_d_40_200 / scalar16 / layer_skip: layer=material_tamper, TPR=1.0, LocAcc=1.0.
- t4strict_pair_b_vs_d_40_200 / projcos4 / gaussian: layer=statistical_tamper, strength=0.15, TPR=1.0, LocAcc=1.0.
- t4strict_pair_b_vs_d_40_200 / projcos4 / same_prompt_old_run_replay: layer=material_tamper, TPR=0.0, LocAcc=0.0.
- t4strict_pair_b_vs_d_40_200 / projcos4 / cross_prompt_stale_substitution: layer=material_tamper, TPR=1.0, LocAcc=1.0.
- t4strict_pair_b_vs_d_40_200 / projcos4 / wrong_shard_output: layer=material_tamper, TPR=1.0, LocAcc=1.0.
- t4strict_pair_b_vs_d_40_200 / projcos4 / scale_perturbation: layer=material_tamper, strength=0.15, TPR=0.0, LocAcc=0.0.
- t4strict_pair_b_vs_d_40_200 / projcos4 / layer_skip: layer=material_tamper, TPR=1.0, LocAcc=1.0.

## Main Interpretation

- `projcos4` is strong on material attacks that change representation direction or semantic content: cross-prompt stale substitution, wrong-shard substitution, and layer skip.
- `same_prompt_old_run_replay` is mostly undetected because it is close to an honest rerun. It should be reported as a negative control rather than a successful tamper benchmark.
- `scale_perturbation` exposes a real blind spot: projected cosine removes norm information, so pure scaling can evade it even when scalar-coordinate checks detect increasing scale strength.
- The correct claim is therefore not 'projcos universally dominates material tamper', but 'projcos is much stronger for direction-changing material tamper; scale-only attacks require a norm-sensitive or hybrid component.'

## Strength Sweep Takeaways

- Gaussian tamper is detected strongly by projcos4 across the tested strengths on A/B and B/D.
- Scale perturbation is intentionally hard for cosine-based projcos, because pure scaling preserves direction; scalar variants detect it better as strength grows.
- This is useful for the paper: projcos is strong for direction-changing material substitutions, but scale-only attacks require either norm information or a hybrid signature.

## Output-Affecting Subset

- Output-affecting subset is now computed by replaying clean/attacked `C2` through layers 16-23 and comparing next-token logits.
- The label marks a prompt as output-affecting when `top1_changed == 1` or the clean/attacked top-5 token sets differ.
- Coverage is intentionally limited to the focus matrix: `scalar16` vs `projcos4`, over 6 pairs and 5 attack families.
- This should be written as a **focus-matrix next-token output-affecting study**, not as a full-variant-family matrix and not as a full-generation output benchmark.

## Remaining Boundary

- This is still an offline controlled replay benchmark. It supports verifier sensitivity analysis, but should not be described as a complete online adversarial deployment.
- `scale_perturbation` remains a formal limitation of cosine-only projected-token sketches: output-affecting scale-only attacks can still evade `projcos4`.
