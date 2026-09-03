# exp_e2_20260512_projscalar1_abs_multiseed_stability

## 目的

验证 `projscalar1_abs` 是否只是 A/B 或单一 projection seed 的偶然好点。实验覆盖 6 个 strict pair 与 5 个 projection seed，每个 pair/seed 都只用 calibration split 选 operating point，再在 held-out eval 上报告 FPR/TPR/LocAcc，并在 material tamper focus 上报告检测率。

## 协议

- Pair 数：6。
- Projection seeds：777, 1001, 2027, 3407, 9001。
- Variant：`projscalar1_abs`，即 16 个 token，每个 token 保留 1 维随机投影值，比较 mean absolute projected gap。
- Payload：16 fp32 scalars = 64B/checkpoint；3 个 checkpoint 的 reveal payload 是 192B/trace。
- 选点规则：calibration-only；优先 `calib FPR <= 0.10`，再最大化 `TPR - FPR`。
- Material attacks：gaussian、cross_prompt_stale_substitution、wrong_shard_output、layer_skip、scale_perturbation。

## Overall Summary

| pair_count | seed_count | run_count | selected_feasible_rate | mean_eval_fpr | max_eval_fpr | min_eval_tpr | min_primary_material_tpr | min_scale_tpr |
| - | - | - | - | - | - | - | - | - |
| 6 | 5 | 30 | 1.0 | 0.007333 | 0.025 | 1.0 | 1.0 | 1.0 |

## Pair Summary

| pair_id | seed_count | selected_feasible_rate | mean_eval_fpr | max_eval_fpr | min_eval_tpr | min_primary_material_tpr | min_scale_tpr |
| - | - | - | - | - | - | - | - |
| t4strict_pair_a_vs_b_40_200 | 5 | 1.0 | 0.014 | 0.025 | 1.0 | 1.0 | 1.0 |
| t4strict_pair_a_vs_b_rtxint8_40_200 | 5 | 1.0 | 0.004 | 0.005 | 1.0 | 1.0 | 1.0 |
| t4strict_pair_a_vs_c_40_200 | 5 | 1.0 | 0.006 | 0.01 | 1.0 | 1.0 | 1.0 |
| t4strict_pair_a_vs_d_40_200 | 5 | 1.0 | 0.01 | 0.02 | 1.0 | 1.0 | 1.0 |
| t4strict_pair_b_vs_d_40_200 | 5 | 1.0 | 0.006 | 0.01 | 1.0 | 1.0 | 1.0 |
| t4strict_pair_e_vs_f_40_200 | 5 | 1.0 | 0.004 | 0.01 | 1.0 | 1.0 | 1.0 |

## 为什么 projscalar1_abs 会好

从数学上看，`projscalar1_abs` 不是旧 TSTC 那种只抽少量坐标的 sparse coordinate check。它先用随机投影把一个 token 的完整 hidden vector 压成 1 个标量，因此每个标量都混合了 1024 维 hidden state 的全局信息。对独立或分散在多维上的漂移，随机投影的期望平方差与原向量 L2 差成比例；也就是说，即使只保留 d=1，它仍然比“只看 16 个原始坐标”更不容易漏掉分布在很多维度上的变化。

同时它比较的是 absolute projected gap，而不是 cosine。这个选择保留了幅值/norm 信息，所以它能检测 `scale_perturbation`；而 `projcos4` 会归一化方向，对纯 scale-only 攻击天然不敏感。换句话说，`projscalar1_abs` 在这里更像一个低维 Johnson-Lindenstrauss 风格的 norm-sensitive sketch：它牺牲了一部分方向几何解释性，但保留了幅值敏感性，并且比 sparse scalar coordinate 更充分地覆盖 hidden vector。

不过它还不能直接替代 `projcos4` 主线。原因是 d=1 的随机投影可能存在方向抵消，理论上 adversary 如果知道投影方向，可以构造近似落在投影核空间的扰动。因此更稳妥的论文定位是：`projscalar1_abs` 是一个非常强的低预算 norm-sensitive bridge / hybrid candidate，可与 `projcos4` 组成 cosine + norm/projection-gap 的混合 verifier。

## 产物

- Selected operating points: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_multiseed_stability_selected_operating_points.csv
- Hard-pair detail: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_multiseed_stability_hard_pair_detail.csv
- Material focus detail: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_multiseed_stability_material_focus_detail.csv
- Pair summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_multiseed_stability_pair_summary.csv
- Overall summary: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_projscalar1_abs_multiseed_stability_overall_summary.csv
- Figure: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_projscalar1_abs_multiseed_stability_stability.png
