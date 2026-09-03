# Table Index

本目录保存交付包中的 CSV。为避免 38 个表看起来混乱，下面按“主表”“辅助表”“复现/明细表”分组。

## 主表

这些表可以直接作为论文主结果或主文叙事依据。

| 表 | 对应实验 | 内容 | 建议用途 |
|---|---|---|---|
| [exp_e2_20260512_experiment_a_pair_family_projcos_paper_main_table.csv](exp_e2_20260512_experiment_a_pair_family_projcos_paper_main_table.csv) | A | A/B、A/C、A/D、B/D 上 scalar/projcos 的 selected operating point、FPR、TPR、LocAcc | Experiment A 主表 |
| [exp_e2_20260512_equal_budget_live_ab_selected_summary.csv](exp_e2_20260512_equal_budget_live_ab_selected_summary.csv) | B | scalar16、scalar64、projscalar1_abs、projcos4、projcos16 的 equal-budget 对照 | Experiment B 主表 |
| [exp_e2_20260512_material_tamper_full_matrix_attack_summary.csv](exp_e2_20260512_material_tamper_full_matrix_attack_summary.csv) | C | 6 pairs x methods x attack families 的 material tamper TPR/LocAcc 汇总 | Experiment C 主表 |
| [exp_e4_20260512_equal_budget_live_ab_main_table.csv](exp_e4_20260512_equal_budget_live_ab_main_table.csv) | D | equal-budget verifier payload、commitment size、challenge latency、detection rate | Experiment D 主表 |
| [exp_e5_20260512_verification_profile_matrix.csv](exp_e5_20260512_verification_profile_matrix.csv) | E | pair/signature-level verification risk profile | E5 profile 输入主表 |
| [exp_e5_20260512_measured_profile_mainline_policy_compare.csv](exp_e5_20260512_measured_profile_mainline_policy_compare.csv) | E | random/cost/network/reputation/risk-constrained/adaptive policy 对照 | Experiment E 主表 |

## 重点补充表

这些表不一定放主文，但用于支撑主结论、补充说明边界或 rebuttal。

| 表 | 对应实验 | 内容 | 建议用途 |
|---|---|---|---|
| [exp_e2_20260512_projscalar1_abs_multiseed_stability_overall_summary.csv](exp_e2_20260512_projscalar1_abs_multiseed_stability_overall_summary.csv) | B 补充 | projscalar1_abs 在 6 pairs x 5 seeds 上的总体稳定性 | 证明不是单 seed/pair 偶然结果 |
| [exp_e2_20260512_projscalar1_abs_multiseed_stability_pair_summary.csv](exp_e2_20260512_projscalar1_abs_multiseed_stability_pair_summary.csv) | B 补充 | projscalar1_abs 分 pair 稳定性 | appendix 或 rebuttal |
| [exp_e2_20260512_projscalar1_abs_validation_hard_pair_summary.csv](exp_e2_20260512_projscalar1_abs_validation_hard_pair_summary.csv) | B 补充 | A/B、B/D hard-pair validation | 解释 projscalar1_abs 的低预算表现 |
| [exp_e2_20260512_projscalar1_abs_validation_material_focus_summary.csv](exp_e2_20260512_projscalar1_abs_validation_material_focus_summary.csv) | C 补充 | projscalar1_abs material focus attack 检测 | 支撑 norm-sensitive sketch 的动机 |
| [exp_e2_20260512_projscalar1_abs_experiment_c_attack_summary.csv](exp_e2_20260512_projscalar1_abs_experiment_c_attack_summary.csv) | C 补充 | projscalar1_abs 完整 attack-family summary | 展示 scale perturbation 与 null-space boundary |
| [exp_e2_20260512_material_tamper_full_matrix_strength_sweep.csv](exp_e2_20260512_material_tamper_full_matrix_strength_sweep.csv) | C | Gaussian/scale strength sweep | 说明 TPR 随 strength 的变化 |
| [exp_e2_20260512_output_affecting_subset_summary.csv](exp_e2_20260512_output_affecting_subset_summary.csv) | C-output | output-affecting subset 的 detection/LocAcc/logit/top-k 指标 | 回答 material attack 是否影响输出 |
| [exp_e4_20260512_equal_budget_live_ab_summary.csv](exp_e4_20260512_equal_budget_live_ab_summary.csv) | D | E4 按 scenario 聚合的 summary | 主表的补充解释 |
| [exp_e5_20260512_measured_profile_mainline_placement_mix.csv](exp_e5_20260512_measured_profile_mainline_placement_mix.csv) | E | 每个 policy 选择了哪些 pair/signature | 解释 E5 policy 为什么改变风险 |

## 复现与明细表

这些表主要用于审计、复现和 debug，不建议直接放主文。

| 表 | 对应实验 | 内容 |
|---|---|---|
| [exp_e2_20260512_experiment_a_pair_family_projcos_candidate_grid.csv](exp_e2_20260512_experiment_a_pair_family_projcos_candidate_grid.csv) | A | calibration candidate grid |
| [exp_e2_20260512_experiment_a_pair_family_projcos_selected_summary.csv](exp_e2_20260512_experiment_a_pair_family_projcos_selected_summary.csv) | A | selected operating points 全量版 |
| [exp_e2_20260512_experiment_a_pair_family_projcos_fallback_baselines.csv](exp_e2_20260512_experiment_a_pair_family_projcos_fallback_baselines.csv) | A | fallback baseline 记录 |
| [exp_e2_20260512_experiment_a_pair_family_projcos_gap_distribution.csv](exp_e2_20260512_experiment_a_pair_family_projcos_gap_distribution.csv) | A | gap distribution |
| [exp_e2_20260512_experiment_a_pair_family_projcos_hetero_mismatch_detail.csv](exp_e2_20260512_experiment_a_pair_family_projcos_hetero_mismatch_detail.csv) | A | honest-hetero mismatch detail |
| [exp_e2_20260512_experiment_a_pair_family_projcos_tamper_mismatch_detail.csv](exp_e2_20260512_experiment_a_pair_family_projcos_tamper_mismatch_detail.csv) | A | tamper mismatch detail |
| [exp_e2_20260512_equal_budget_live_ab_candidate_grid.csv](exp_e2_20260512_equal_budget_live_ab_candidate_grid.csv) | B | equal-budget candidate grid |
| [exp_e2_20260512_material_tamper_full_matrix_detail.csv](exp_e2_20260512_material_tamper_full_matrix_detail.csv) | C | full matrix per-trace detail |
| [exp_e2_20260512_material_tamper_full_matrix_selected_operating_points.csv](exp_e2_20260512_material_tamper_full_matrix_selected_operating_points.csv) | C/E | material tamper selected operating points |
| [exp_e2_20260512_output_affecting_subset_labels.csv](exp_e2_20260512_output_affecting_subset_labels.csv) | C-output | output-affecting labels |
| [exp_e2_20260512_output_affecting_subset_joined_detail.csv](exp_e2_20260512_output_affecting_subset_joined_detail.csv) | C-output | output-affecting joined detail |
| [exp_e2_20260512_projscalar1_abs_validation_material_focus_detail.csv](exp_e2_20260512_projscalar1_abs_validation_material_focus_detail.csv) | B/C 补充 | projscalar1_abs material focus detail |
| [exp_e2_20260512_projscalar1_abs_validation_selected_operating_points.csv](exp_e2_20260512_projscalar1_abs_validation_selected_operating_points.csv) | B/C 补充 | validation selected points |
| [exp_e2_20260512_projscalar1_abs_validation_e5_profile_addendum.csv](exp_e2_20260512_projscalar1_abs_validation_e5_profile_addendum.csv) | E addendum | projscalar1_abs 的 E5 profile addendum |
| [exp_e2_20260512_projscalar1_abs_multiseed_stability_selected_operating_points.csv](exp_e2_20260512_projscalar1_abs_multiseed_stability_selected_operating_points.csv) | B 补充 | multiseed selected points |
| [exp_e2_20260512_projscalar1_abs_multiseed_stability_hard_pair_detail.csv](exp_e2_20260512_projscalar1_abs_multiseed_stability_hard_pair_detail.csv) | B 补充 | multiseed hard-pair detail |
| [exp_e2_20260512_projscalar1_abs_multiseed_stability_material_focus_detail.csv](exp_e2_20260512_projscalar1_abs_multiseed_stability_material_focus_detail.csv) | C 补充 | multiseed material focus detail |
| [exp_e2_20260512_projscalar1_abs_experiment_c_selected_operating_points.csv](exp_e2_20260512_projscalar1_abs_experiment_c_selected_operating_points.csv) | C 补充 | Experiment C extension selected points |
| [exp_e2_20260512_projscalar1_abs_experiment_c_focus_detail.csv](exp_e2_20260512_projscalar1_abs_experiment_c_focus_detail.csv) | C 补充 | Experiment C extension focus detail |
| [exp_e2_20260512_projscalar1_abs_experiment_c_strength_sweep_detail.csv](exp_e2_20260512_projscalar1_abs_experiment_c_strength_sweep_detail.csv) | C 补充 | strength sweep detail |
| [exp_e2_20260512_projscalar1_abs_experiment_c_strength_sweep_summary.csv](exp_e2_20260512_projscalar1_abs_experiment_c_strength_sweep_summary.csv) | C 补充 | strength sweep summary |
| [exp_e4_20260512_equal_budget_live_ab_detail.csv](exp_e4_20260512_equal_budget_live_ab_detail.csv) | D | E4 per-trace detail |
| [exp_e5_20260512_measured_profile_mainline_per_task.csv](exp_e5_20260512_measured_profile_mainline_per_task.csv) | E | E5 per-task trace |

## 快速定位

- 想看主结论：先读“主表”分组。
- 想解释为什么选这个 operating point：看 candidate grid、selected summary。
- 想审计 first mismatch / LocAcc：看 mismatch detail、full matrix detail。
- 想复现 E5 policy 行为：看 profile matrix、policy compare、placement mix、per-task trace。
