# E2 Output-Affecting Subset Report

- Scope: output-affecting replay over 6 pair(s): t4strict_pair_a_vs_b_40_200, t4strict_pair_a_vs_b_rtxint8_40_200, t4strict_pair_a_vs_c_40_200, t4strict_pair_a_vs_d_40_200, t4strict_pair_b_vs_d_40_200, t4strict_pair_e_vs_f_40_200.
- Variant coverage: focus matrix only (`scalar16, projcos4`), not the full variant family.
- Method: replace/perturb C2, replay layers 16-23 to logits using QwenShardRunner, then label next-token top-k changes.
- Output-affecting label: `top1_changed == 1` or clean/attacked top-5 token set differs.
- Scope boundary: this is a next-token top-k output-affecting study, not a full-generation output benchmark.
- Labels: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_output_affecting_subset_labels.csv
- Joined verifier detail: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_output_affecting_subset_joined_detail.csv
- Summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_output_affecting_subset_summary.csv

## Summary

| pair_id | variant | attack_family | prompt_count | output_affecting_prompt_count | output_affecting_rate | all_sample_detection_rate | all_sample_localization_acc | output_affecting_detection_rate | output_affecting_localization_acc | mean_logit_l2_delta | mean_top5_jaccard |
| - | - | - | - | - | - | - | - | - | - | - | - |
| t4strict_pair_a_vs_b_40_200 | projcos4 | cross_prompt_stale_substitution | 200 | 188 | 0.94 | 1.0 | 1.0 | 1.0 | 1.0 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_b_40_200 | projcos4 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.92218 | 0.001667 |
| t4strict_pair_a_vs_b_40_200 | projcos4 | layer_skip | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 571.219005 | 0.174087 |
| t4strict_pair_a_vs_b_40_200 | projcos4 | scale_perturbation | 200 | 78 | 0.39 | 0.0 | 0.0 | 0.0 | 0.0 | 56.753905 | 0.897619 |
| t4strict_pair_a_vs_b_40_200 | projcos4 | wrong_shard_output | 200 | 188 | 0.94 | 1.0 | 1.0 | 1.0 | 1.0 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_b_40_200 | scalar16 | cross_prompt_stale_substitution | 200 | 188 | 0.94 | 0.76 | 0.76 | 0.75 | 0.75 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_b_40_200 | scalar16 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.92218 | 0.001667 |
| t4strict_pair_a_vs_b_40_200 | scalar16 | layer_skip | 200 | 200 | 1.0 | 0.83 | 0.83 | 0.83 | 0.83 | 571.219005 | 0.174087 |
| t4strict_pair_a_vs_b_40_200 | scalar16 | scale_perturbation | 200 | 78 | 0.39 | 0.52 | 0.52 | 0.525641 | 0.525641 | 56.753905 | 0.897619 |
| t4strict_pair_a_vs_b_40_200 | scalar16 | wrong_shard_output | 200 | 188 | 0.94 | 0.76 | 0.76 | 0.75 | 0.75 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | projcos4 | cross_prompt_stale_substitution | 200 | 188 | 0.94 | 1.0 | 1.0 | 1.0 | 1.0 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | projcos4 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.92218 | 0.001667 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | projcos4 | layer_skip | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 571.219005 | 0.174087 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | projcos4 | scale_perturbation | 200 | 78 | 0.39 | 0.0 | 0.0 | 0.0 | 0.0 | 56.753905 | 0.897619 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | projcos4 | wrong_shard_output | 200 | 188 | 0.94 | 1.0 | 1.0 | 1.0 | 1.0 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | scalar16 | cross_prompt_stale_substitution | 200 | 188 | 0.94 | 0.655 | 0.655 | 0.654255 | 0.654255 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | scalar16 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.92218 | 0.001667 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | scalar16 | layer_skip | 200 | 200 | 1.0 | 0.6 | 0.6 | 0.6 | 0.6 | 571.219005 | 0.174087 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | scalar16 | scale_perturbation | 200 | 78 | 0.39 | 0.37 | 0.37 | 0.448718 | 0.448718 | 56.753905 | 0.897619 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | scalar16 | wrong_shard_output | 200 | 188 | 0.94 | 0.655 | 0.655 | 0.654255 | 0.654255 | 270.313745 | 0.502758 |
| t4strict_pair_a_vs_c_40_200 | projcos4 | cross_prompt_stale_substitution | 200 | 186 | 0.93 | 1.0 | 1.0 | 1.0 | 1.0 | 270.539603 | 0.505 |
| t4strict_pair_a_vs_c_40_200 | projcos4 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.195143 | 0.001667 |
| t4strict_pair_a_vs_c_40_200 | projcos4 | layer_skip | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 570.898384 | 0.170694 |
| t4strict_pair_a_vs_c_40_200 | projcos4 | scale_perturbation | 200 | 75 | 0.375 | 0.0 | 0.0 | 0.0 | 0.0 | 56.83921 | 0.89381 |
| t4strict_pair_a_vs_c_40_200 | projcos4 | wrong_shard_output | 200 | 186 | 0.93 | 1.0 | 1.0 | 1.0 | 1.0 | 270.539603 | 0.505 |
| t4strict_pair_a_vs_c_40_200 | scalar16 | cross_prompt_stale_substitution | 200 | 186 | 0.93 | 0.645 | 0.645 | 0.634409 | 0.634409 | 270.539603 | 0.505 |
| t4strict_pair_a_vs_c_40_200 | scalar16 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.195143 | 0.001667 |
| t4strict_pair_a_vs_c_40_200 | scalar16 | layer_skip | 200 | 200 | 1.0 | 0.585 | 0.585 | 0.585 | 0.585 | 570.898384 | 0.170694 |
| t4strict_pair_a_vs_c_40_200 | scalar16 | scale_perturbation | 200 | 75 | 0.375 | 0.355 | 0.355 | 0.373333 | 0.373333 | 56.83921 | 0.89381 |
| t4strict_pair_a_vs_c_40_200 | scalar16 | wrong_shard_output | 200 | 186 | 0.93 | 0.645 | 0.645 | 0.634409 | 0.634409 | 270.539603 | 0.505 |
| t4strict_pair_a_vs_d_40_200 | projcos4 | cross_prompt_stale_substitution | 200 | 190 | 0.95 | 1.0 | 1.0 | 1.0 | 1.0 | 270.972116 | 0.497044 |
| t4strict_pair_a_vs_d_40_200 | projcos4 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.438142 | 0.001667 |
| t4strict_pair_a_vs_d_40_200 | projcos4 | layer_skip | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 571.173167 | 0.173175 |
| t4strict_pair_a_vs_d_40_200 | projcos4 | scale_perturbation | 200 | 79 | 0.395 | 0.0 | 0.0 | 0.0 | 0.0 | 56.864813 | 0.890476 |
| t4strict_pair_a_vs_d_40_200 | projcos4 | wrong_shard_output | 200 | 190 | 0.95 | 1.0 | 1.0 | 1.0 | 1.0 | 270.972116 | 0.497044 |
| t4strict_pair_a_vs_d_40_200 | scalar16 | cross_prompt_stale_substitution | 200 | 190 | 0.95 | 0.555 | 0.555 | 0.557895 | 0.557895 | 270.972116 | 0.497044 |
| t4strict_pair_a_vs_d_40_200 | scalar16 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.438142 | 0.001667 |
| t4strict_pair_a_vs_d_40_200 | scalar16 | layer_skip | 200 | 200 | 1.0 | 0.51 | 0.51 | 0.51 | 0.51 | 571.173167 | 0.173175 |
| t4strict_pair_a_vs_d_40_200 | scalar16 | scale_perturbation | 200 | 79 | 0.395 | 0.22 | 0.22 | 0.227848 | 0.227848 | 56.864813 | 0.890476 |
| t4strict_pair_a_vs_d_40_200 | scalar16 | wrong_shard_output | 200 | 190 | 0.95 | 0.555 | 0.555 | 0.557895 | 0.557895 | 270.972116 | 0.497044 |
| t4strict_pair_b_vs_d_40_200 | projcos4 | cross_prompt_stale_substitution | 200 | 190 | 0.95 | 1.0 | 1.0 | 1.0 | 1.0 | 270.972116 | 0.497044 |
| t4strict_pair_b_vs_d_40_200 | projcos4 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.438142 | 0.001667 |
| t4strict_pair_b_vs_d_40_200 | projcos4 | layer_skip | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 571.173167 | 0.173175 |
| t4strict_pair_b_vs_d_40_200 | projcos4 | scale_perturbation | 200 | 79 | 0.395 | 0.0 | 0.0 | 0.0 | 0.0 | 56.864813 | 0.890476 |
| t4strict_pair_b_vs_d_40_200 | projcos4 | wrong_shard_output | 200 | 190 | 0.95 | 1.0 | 1.0 | 1.0 | 1.0 | 270.972116 | 0.497044 |
| t4strict_pair_b_vs_d_40_200 | scalar16 | cross_prompt_stale_substitution | 200 | 190 | 0.95 | 0.95 | 0.95 | 0.947368 | 0.947368 | 270.972116 | 0.497044 |
| t4strict_pair_b_vs_d_40_200 | scalar16 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1740.438142 | 0.001667 |
| t4strict_pair_b_vs_d_40_200 | scalar16 | layer_skip | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 571.173167 | 0.173175 |
| t4strict_pair_b_vs_d_40_200 | scalar16 | scale_perturbation | 200 | 79 | 0.395 | 0.72 | 0.72 | 0.734177 | 0.734177 | 56.864813 | 0.890476 |
| t4strict_pair_b_vs_d_40_200 | scalar16 | wrong_shard_output | 200 | 190 | 0.95 | 0.95 | 0.95 | 0.947368 | 0.947368 | 270.972116 | 0.497044 |
| t4strict_pair_e_vs_f_40_200 | projcos4 | cross_prompt_stale_substitution | 200 | 187 | 0.935 | 1.0 | 0.985 | 1.0 | 0.983957 | 270.386347 | 0.504524 |
| t4strict_pair_e_vs_f_40_200 | projcos4 | gaussian | 200 | 200 | 1.0 | 1.0 | 0.985 | 1.0 | 0.985 | 1737.242824 | 0.001667 |
| t4strict_pair_e_vs_f_40_200 | projcos4 | layer_skip | 200 | 200 | 1.0 | 1.0 | 0.985 | 1.0 | 0.985 | 571.240253 | 0.172282 |
| t4strict_pair_e_vs_f_40_200 | projcos4 | scale_perturbation | 200 | 78 | 0.39 | 0.06 | 0.01 | 0.064103 | 0.012821 | 56.828947 | 0.890952 |
| t4strict_pair_e_vs_f_40_200 | projcos4 | wrong_shard_output | 200 | 187 | 0.935 | 1.0 | 0.985 | 1.0 | 0.989305 | 270.386347 | 0.504524 |
| t4strict_pair_e_vs_f_40_200 | scalar16 | cross_prompt_stale_substitution | 200 | 187 | 0.935 | 1.0 | 1.0 | 1.0 | 1.0 | 270.386347 | 0.504524 |
| t4strict_pair_e_vs_f_40_200 | scalar16 | gaussian | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1737.242824 | 0.001667 |
| t4strict_pair_e_vs_f_40_200 | scalar16 | layer_skip | 200 | 200 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 571.240253 | 0.172282 |
| t4strict_pair_e_vs_f_40_200 | scalar16 | scale_perturbation | 200 | 78 | 0.39 | 1.0 | 1.0 | 1.0 | 1.0 | 56.828947 | 0.890952 |
| t4strict_pair_e_vs_f_40_200 | scalar16 | wrong_shard_output | 200 | 187 | 0.935 | 1.0 | 1.0 | 1.0 | 1.0 | 270.386347 | 0.504524 |
