# Figure Index

本目录保存交付包中的 PNG 主图。PDF 版本在 `../pdf/` 中；若要插入论文草稿，优先使用 PDF，若要快速预览，使用 PNG。

## 主图

| 图 | 对应实验 | 说明 | 主要结论 |
|---|---|---|---|
| [exp_e2_20260512_experiment_a_pair_family_projcos_pair_family_fpr_tpr.png](exp_e2_20260512_experiment_a_pair_family_projcos_pair_family_fpr_tpr.png) | A | hard pair projected-token TSTC 的 FPR/TPR 对照 | `projcos4` 将 B/D hard pair FPR 从 scalar16 的 `0.245` 降到 `0.075`，TPR 保持 `1.0` |
| [exp_e2_20260512_equal_budget_live_ab_fpr_tpr_vs_budget.png](exp_e2_20260512_equal_budget_live_ab_fpr_tpr_vs_budget.png) | B | equal-budget baseline | 同为 `256B/checkpoint` 时，`projcos4` 明显优于 `scalar64` |
| [exp_e2_20260512_material_tamper_full_matrix_material_focus_panel.png](exp_e2_20260512_material_tamper_full_matrix_material_focus_panel.png) | C | material tamper focus panel | `projcos4` 对方向/语义改变类攻击强，对 `scale_perturbation` 失败 |
| [exp_e2_20260512_material_tamper_full_matrix_strength_sweep_focus.png](exp_e2_20260512_material_tamper_full_matrix_strength_sweep_focus.png) | C | tamper strength sweep | Gaussian strength 上升时检测稳定；scale-only attack 暴露 cosine-only 盲点 |
| [exp_e4_20260512_equal_budget_live_ab_payload_latency.png](exp_e4_20260512_equal_budget_live_ab_payload_latency.png) | D | payload 与 challenge latency | projected-token 增加 payload，但 overhead 仍在 challenge-time 可接受范围 |
| [exp_e5_20260512_measured_profile_mainline_queued_8_policy_compare.png](exp_e5_20260512_measured_profile_mainline_queued_8_policy_compare.png) | E | queued workload policy comparison | verification-aware policy 降低 infeasible/high-risk placement，但不一定最低延迟 |
| [exp_e5_20260512_measured_profile_mainline_queued_8_pareto.png](exp_e5_20260512_measured_profile_mainline_queued_8_pareto.png) | E | queued workload Pareto view | 展示 goodput、risk-adjusted goodput 与 verification risk 的 tradeoff |
| [exp_e5_20260512_measured_profile_mainline_queued_8_risk_stack.png](exp_e5_20260512_measured_profile_mainline_queued_8_risk_stack.png) | E | queued workload risk-class stack | 普通策略会选择大量 high-risk/infeasible placement，verification-aware policy 避开它们 |

## 补充图

| 图 | 对应实验 | 说明 | 用途 |
|---|---|---|---|
| [exp_e2_20260512_material_tamper_full_matrix_focus_tpr.png](exp_e2_20260512_material_tamper_full_matrix_focus_tpr.png) | C | full matrix 中重点 attack family 的 TPR 汇总 | 可作为 material tamper 的补充图 |
| [exp_e2_20260512_projscalar1_abs_validation_hard_and_material_focus.png](exp_e2_20260512_projscalar1_abs_validation_hard_and_material_focus.png) | B/C 补充 | projscalar1_abs 在 A/B、B/D 和 material focus 上的表现 | 支撑 low-budget norm-sensitive bridge 的动机 |
| [exp_e2_20260512_projscalar1_abs_multiseed_stability_stability.png](exp_e2_20260512_projscalar1_abs_multiseed_stability_stability.png) | B 补充 | 6 pairs x 5 seeds 稳定性 | 排除 projscalar1_abs 只在单一 seed/pair 上碰巧有效 |
| [exp_e2_20260512_projscalar1_abs_experiment_c_attack_and_sweep.png](exp_e2_20260512_projscalar1_abs_experiment_c_attack_and_sweep.png) | C 补充 | projscalar1_abs attack-family 与 strength sweep | 展示它覆盖 scale perturbation，同时暴露 null-space adaptive attack 边界 |
| [exp_e5_20260512_measured_profile_mainline_single_task_policy_compare.png](exp_e5_20260512_measured_profile_mainline_single_task_policy_compare.png) | E | single-task workload policy comparison | 补充展示非队列 workload 下的 policy tradeoff |
| [exp_e5_20260512_measured_profile_mainline_single_task_pareto.png](exp_e5_20260512_measured_profile_mainline_single_task_pareto.png) | E | single-task Pareto view | 补充展示 single-task setting |
| [exp_e5_20260512_measured_profile_mainline_single_task_risk_stack.png](exp_e5_20260512_measured_profile_mainline_single_task_risk_stack.png) | E | single-task risk-class stack | 补充展示 single-task risk composition |

## 论文插图建议

建议主文优先放：

1. Experiment A pair-family FPR/TPR 图
2. Experiment B equal-budget 图
3. Experiment C material focus 或 strength sweep 图
4. Experiment D overhead 图
5. Experiment E queued policy compare 或 Pareto 图

其余图可放 appendix 或 rebuttal material。
