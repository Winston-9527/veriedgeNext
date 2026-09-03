# exp_e2_20260512_projscalar1_abs_experiment_c

## 目的

`projscalar1_abs` 已经在多 seed / 全 pair 上表现稳定。本实验补齐它在实验 C 语境下的必要证据：不同攻击家族、弱到强 strength sweep，以及 projection-aware null-space attack 边界。

## 协议

- Pair: 6 strict pairs。
- Projection seed: 777。
- Variant: `projscalar1_abs`，64B/checkpoint。
- Focus attacks: gaussian, cross_prompt_stale_substitution, wrong_shard_output, layer_skip, scale_perturbation, projection_aware_nullspace。
- Sweep attacks: gaussian, scale_perturbation, projection_aware_nullspace over strengths [0.01, 0.02, 0.05, 0.1, 0.15, 0.2]。

## Attack-family Summary

| attack_family | pair_count | mean_detection_rate | min_detection_rate | mean_localization_acc | min_localization_acc |
| - | - | - | - | - | - |
| gaussian | 6 | 1.0 | 1.0 | 1.0 | 1.0 |
| cross_prompt_stale_substitution | 6 | 1.0 | 1.0 | 1.0 | 1.0 |
| wrong_shard_output | 6 | 1.0 | 1.0 | 1.0 | 1.0 |
| layer_skip | 6 | 1.0 | 1.0 | 1.0 | 1.0 |
| scale_perturbation | 6 | 1.0 | 1.0 | 1.0 | 1.0 |
| projection_aware_nullspace | 6 | 0.0 | 0.0 | 0.0 | 0.0 |

## Projection-aware Null-space Boundary

| attack_family | attack_strength | mean_detection_rate | min_detection_rate |
| - | - | - | - |
| projection_aware_nullspace | 0.01 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.02 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.05 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.1 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.15 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.2 | 0.0 | 0.0 |

## Weak-to-strong Sweep

| attack_family | attack_strength | mean_detection_rate | min_detection_rate |
| - | - | - | - |
| gaussian | 0.01 | 1.0 | 1.0 |
| gaussian | 0.02 | 1.0 | 1.0 |
| gaussian | 0.05 | 1.0 | 1.0 |
| gaussian | 0.1 | 1.0 | 1.0 |
| gaussian | 0.15 | 1.0 | 1.0 |
| gaussian | 0.2 | 1.0 | 1.0 |
| scale_perturbation | 0.01 | 0.239167 | 0.0 |
| scale_perturbation | 0.02 | 0.941667 | 0.685 |
| scale_perturbation | 0.05 | 1.0 | 1.0 |
| scale_perturbation | 0.1 | 1.0 | 1.0 |
| scale_perturbation | 0.15 | 1.0 | 1.0 |
| scale_perturbation | 0.2 | 1.0 | 1.0 |
| projection_aware_nullspace | 0.01 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.02 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.05 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.1 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.15 | 0.0 | 0.0 |
| projection_aware_nullspace | 0.2 | 0.0 | 0.0 |

## 解读

`projscalar1_abs` 对普通实验 C 攻击家族依然很强，包含语义替换、layer skip、scale perturbation。它能检测 scale 的原因是 absolute projected gap 保留了幅值信息。弱攻击 sweep 显示：Gaussian 在 `0.01` 已经稳定检出；scale 在 `0.01` 时平均 TPR 只有约 `0.239`，到 `0.02` 上升到约 `0.942`，`0.05` 及以上为 `1.0`。因此它不是只在强 scale attack 上有效，但极弱 scale 仍存在灰区。

但 projection-aware null-space attack 展示了它的理论边界：如果攻击者知道 projection vector，可以构造几乎落在投影核空间的扰动，使被保留的 d=1 投影值变化很小。这个结果不削弱它作为低预算 hybrid candidate 的价值，反而说明论文中不应把它写成单独通用 verifier；更合理的系统设计是 `projcos` 方向统计 + `projscalar/norm` 幅值统计的混合 verifier。

## 产物

- Selected operating points: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_experiment_c_selected_operating_points.csv
- Focus detail: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_experiment_c_focus_detail.csv
- Strength sweep detail: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_experiment_c_strength_sweep_detail.csv
- Attack summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_experiment_c_attack_summary.csv
- Sweep summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_experiment_c_strength_sweep_summary.csv
- Figure: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_projscalar1_abs_experiment_c_attack_and_sweep.png
