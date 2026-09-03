# exp_e2_20260512_projscalar1_abs_validation

## 目的

`projscalar1_abs` 在 A/B equal-budget 单点上表现很好，但这不足以证明它稳定优于 `projcos4`。本验证包把它作为低预算 bridge / hybrid 候选，补做 A/B 与 B/D hard pair，以及实验 C material-tamper focus 攻击。

## 协议

- Pair: t4strict_pair_a_vs_b_40_200, t4strict_pair_b_vs_d_40_200。
- 方法: `scalar16`、`projscalar1_abs`、`projcos4`。
- 选点: 只用 calibration split；优先满足 calib FPR <= 0.10，再最大化 TPR-FPR。
- `projscalar1_abs`: 16 tokens x d=1 random projection，比较 mean absolute projected gap，payload 为 16 fp32 scalars = 64B/checkpoint。
- Material focus attacks: gaussian, cross_prompt_stale_substitution, wrong_shard_output, layer_skip, scale_perturbation。

## Hard Pair Held-out Summary

| pair_id | variant | signature_bytes_per_checkpoint_fp32 | eval_honest_hetero_fpr | eval_tamper_tpr | eval_tamper_locacc |
| - | - | - | - | - | - |
| t4strict_pair_a_vs_b_40_200 | scalar16 | 64 | 0.15 | 1.0 | 1.0 |
| t4strict_pair_a_vs_b_40_200 | projscalar1_abs | 64 | 0.0 | 1.0 | 1.0 |
| t4strict_pair_a_vs_b_40_200 | projcos4 | 256 | 0.02 | 1.0 | 1.0 |
| t4strict_pair_b_vs_d_40_200 | scalar16 | 64 | 0.245 | 1.0 | 1.0 |
| t4strict_pair_b_vs_d_40_200 | projscalar1_abs | 64 | 0.0 | 1.0 | 1.0 |
| t4strict_pair_b_vs_d_40_200 | projcos4 | 256 | 0.075 | 1.0 | 1.0 |

## Material Tamper Focus Mean over A/B and B/D

| variant | attack_family | mean_detection_rate | mean_localization_acc |
| - | - | - | - |
| scalar16 | gaussian | 1.0 | 1.0 |
| scalar16 | cross_prompt_stale_substitution | 0.855 | 0.855 |
| scalar16 | wrong_shard_output | 0.855 | 0.855 |
| scalar16 | layer_skip | 0.915 | 0.915 |
| scalar16 | scale_perturbation | 0.62 | 0.62 |
| projscalar1_abs | gaussian | 1.0 | 1.0 |
| projscalar1_abs | cross_prompt_stale_substitution | 1.0 | 1.0 |
| projscalar1_abs | wrong_shard_output | 1.0 | 1.0 |
| projscalar1_abs | layer_skip | 1.0 | 1.0 |
| projscalar1_abs | scale_perturbation | 1.0 | 1.0 |
| projcos4 | gaussian | 1.0 | 1.0 |
| projcos4 | cross_prompt_stale_substitution | 1.0 | 1.0 |
| projcos4 | wrong_shard_output | 1.0 | 1.0 |
| projcos4 | layer_skip | 1.0 | 1.0 |
| projcos4 | scale_perturbation | 0.0 | 0.0 |

## 解读

- 如果 `projscalar1_abs` 在 A/B 和 B/D 上都保持低 FPR、高 TPR，说明它不是纯 A/B seed-specific 偶然点。
- 如果它在 material attacks 上接近 `projcos4`，它可以作为低预算候选或 hybrid 组件进入论文补充实验。
- 如果它只对 gaussian 或 scale 类攻击强、对 semantic substitution/layer skip 弱，则它更像 norm/projection-gap detector，不应替代 `projcos4` 主线。

## E5-style Profile Addendum

- 已补一个轻量 profile addendum，复用 E4 measured overhead 与本验证包的 A/B、B/D held-out FPR/material TPR。
- 这不是完整 E5 policy replay，不覆盖所有 6 个 pair，也不应替代正式 E5 主表。
- 它的作用是判断 `projscalar1_abs` 是否值得进入完整 placement profile：如果 `feasible_under_alpha_beta=1` 且 payload/latency 低，就值得补完整 E5。

## 产物

- Selected operating points: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_validation_selected_operating_points.csv
- Hard-pair summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_validation_hard_pair_summary.csv
- Material focus summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_validation_material_focus_summary.csv
- Material focus detail: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_validation_material_focus_detail.csv
- E5-style profile addendum: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_validation_e5_profile_addendum.csv
- Figure: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_projscalar1_abs_validation_hard_and_material_focus.png
