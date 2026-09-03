# projscalar1_abs 补充实验审计报告

日期：2026-05-12

## 审计结论

`projscalar1_abs` 补充实验总体可信，当前没有发现阻断性交付问题。结果支持把 `projscalar1_abs` 写成一个强低预算 norm-sensitive bridge / hybrid candidate。

但它不应直接替代 `projcos4` 作为论文主线方法。更稳妥的写法是：`projscalar1_abs` 证明“随机投影 + 幅值敏感 gap”可以用更小 payload 取得很强效果，并且能补 `projcos4` 的 scale-only blind spot；后续可以发展为 `cosine + projection/norm gap` hybrid verifier。

新增实验 C extension 后，科学结论更完整：`projscalar1_abs` 对普通 material tamper 和 weak-to-strong gaussian/scale sweep 表现强，但 projection-aware null-space attack 全部 0 检出，明确给出了 d=1 投影在 white-box/adaptive setting 下的边界。

## 已核对的正确点

| 检查项 | 结论 |
|---|---|
| calibration/evaluation split | 未发现 eval 反向选参；operating point 由 calibration split 选择 |
| projection seed | 多 seed 实验没有挑最好 seed，而是汇总 5 个固定 seed |
| pair 覆盖 | multiseed 覆盖 6 个 strict pair，validation 覆盖 A/B 与 B/D |
| payload 口径 | `16 tokens x 1 scalar = 16 fp32 = 64B/checkpoint`，3 checkpoint reveal 为 192B/trace |
| 结果计数 | multiseed hard detail 为 30 行，即 6 pairs x 5 seeds |
| material detail 计数 | multiseed material detail 为 150 行，即 6 pairs x 5 seeds x 5 attacks |
| selection feasibility | 30/30 selected_from_feasible，calib FPR 均满足目标 |
| held-out FPR | overall mean FPR = 0.007333，max FPR = 0.025 |
| held-out TPR | min eval TPR = 1.0，min eval LocAcc = 1.0 |
| material tamper | primary material TPR 与 scale TPR 均为 1.0 |
| weak-to-strong scale sweep | strength=0.01 时 mean TPR=0.239167，0.02 时 mean TPR=0.941667，0.05 及以上为 1.0 |
| projection-aware null-space | 所有 sweep strength 下 mean/min TPR 均为 0.0，边界结果清晰 |
| null-space seed 对齐 | 攻击构造使用的 projection matrix 与 verifier 的 `projection_seed + seed_base + checkpoint_index` 一致 |

## 主要结果

| 指标 | 数值 |
|---|---:|
| pair_count | 6 |
| seed_count | 5 |
| run_count | 30 |
| selected_feasible_rate | 1.000 |
| mean_eval_fpr | 0.007333 |
| max_eval_fpr | 0.025 |
| min_eval_tpr | 1.000 |
| min_primary_material_tpr | 1.000 |
| min_scale_tpr | 1.000 |

## 新增 Experiment C Extension

| Attack family | Mean TPR | Min TPR | 解释 |
|---|---:|---:|---|
| gaussian | 1.000 | 1.000 | 普通随机扰动稳定检出 |
| cross_prompt_stale_substitution | 1.000 | 1.000 | 语义替换类 replay 稳定检出 |
| wrong_shard_output | 1.000 | 1.000 | 错 shard/错 prompt 替换稳定检出 |
| layer_skip | 1.000 | 1.000 | 跳层类 material tamper 稳定检出 |
| scale_perturbation | 1.000 | 1.000 | 幅值敏感 gap 能覆盖 `projcos4` 的 scale-only 盲点 |
| projection_aware_nullspace | 0.000 | 0.000 | white-box/adaptive 攻击可规避 d=1 投影 |

Strength sweep 的关键读法是：gaussian 在 `0.01` 已满检出；scale perturbation 在 `0.01` 仍有灰区，mean TPR=`0.239167`，到 `0.02` 提升到 `0.941667`，`0.05` 及以上为 `1.0`。Projection-aware null-space attack 在 `0.01-0.20` 全部为 `0.0`。

## 科学解释

`projscalar1_abs` 不是旧 sparse scalar coordinate check。旧方法看的是少量原始坐标，容易漏掉分散在高维 hidden vector 中的变化。`projscalar1_abs` 对每个 token 做 1 维随机投影，因此每个标量都混合了完整 hidden vector 的信息。

它也不同于 `projcos4`。`projcos4` 比较方向，因此对 scale-only / direction-preserving attack 弱；`projscalar1_abs` 比较 absolute projected gap，保留幅值信息，所以能检测 `scale_perturbation`。

新增 null-space attack 也符合数学预期。若 verifier 只保留 `z=<r,h>`，攻击者知道 `r` 后可以构造扰动 `u` 使 `<r,u>=0`，则 `z` 不变，`projscalar1_abs` 无法报警。这是 d=1 随机投影的自然边界，不是实现 bug。

## 需要保留的边界

| 边界 | 说明 |
|---|---|
| adaptive white-box 边界已补 | projection-aware null-space attack 全 0 检出，说明 `projscalar1_abs` 不能单独承担 adaptive adversarial robustness claim |
| 不是完整 E5 replay | 当前只有 E5-style addendum，没有把 `projscalar1_abs` 完整放入 policy replay candidate set |
| d=1 理论上仍可能抵消 | 单维随机投影可能存在方向抵消；多 seed 实验降低偶然性风险，但不能证明 adversarial robustness |
| null-space 是否 output-affecting 未单独证明 | 当前 null-space attack 是 verifier-evasion boundary test，不是 output-affecting subset 证据 |
| material focus 是 offline replay | 不是 live online adversarial deployment |

## 建议写法

可以写：

> As a norm-sensitive bridge, `projscalar1_abs` achieves low FPR and high TPR across six heterogeneous pairs and five projection seeds with only 64B/checkpoint, while a projection-aware null-space attack exposes its white-box boundary. This suggests that random-projection gap sketches are best used as a norm-sensitive complement to cosine-based projected-token verification.

不要写：

> `projscalar1_abs` fully replaces `projcos4` or solves adaptive tamper detection.
