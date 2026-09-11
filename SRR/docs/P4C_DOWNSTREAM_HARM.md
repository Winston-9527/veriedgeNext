# P4c: Downstream-Harm Coupling（W8A16 vs W8A8）

**实验日期**：2026-08-07
**执行环境**：RTX3090（172.31.100.17），CUDA，Qwen3-0.6B
**目的**：把精度作弊的 activation 漂移（SignRadial）与**输出退化**（token 分歧率、KL）关联起来，回答：SignRadial 检测到的作弊是否真的伤害输出？检测不到的作弊是否无害？

---

## 1. 方法

对同一 prompt 贪心生成 32 tokens，honest BF16 vs 各作弊配置，同时测：
- **边界 SignRadial**（prefill, layer 16）
- **token 分歧率**：生成 token 与 honest 不同的比例
- **KL 散度**：生成 token 分布 vs honest 的 KL

**聚焦 W8A16 vs W8A8**（CUDA 上稳定；INT8/FP8 decode 数值不稳定，已诊断——INT8 layer16 爆炸 max=6517、FP8 产生 NaN，已排除）。

---

## 2. 结果（8 prompts）

| prompt | W8A16 srr/dis/KL | W8A8 srr/dis/KL |
|---|---|---|
| France | 0.002 / 0.00 / 0.0 | 0.046 / 0.97 / 9.8 |
| relativity | 0.006 / 0.00 / 0.0 | 0.131 / 1.00 / 9.5 |
| Python fib | 0.009 / 0.31 / 2.4 | 0.068 / 0.34 / 3.0 |
| TCP/UDP | 0.001 / 0.94 / 9.4 | 0.081 / 0.81 / 7.9 |
| sky | 0.002 / 0.88 / 7.8 | 0.074 / 0.88 / 7.7 |
| sqrt144 | 0.001 / 0.00 / 0.0 | 0.085 / 1.00 / 15.0 |
| water cycle | 0.009 / 0.88 / 8.8 | 0.102 / 0.84 / 7.6 |
| cookies | 0.007 / 1.00 / 13.4 | 0.080 / 1.00 / 8.6 |

**汇总：**

| 配置 | SignRadial | token 分歧率 | KL |
|---|---:|---:|---:|
| **W8A16**（weight-only）| **0.0048**（不可见）| **0.500** | **5.23** |
| **W8A8**（weight+act）| **0.0833**（可检测）| **0.855** | **8.62** |

---

## 3. 核心发现

1. **W8A16 不可见却伤害输出**：SignRadial=0.0048（远低于 honest p99），但 token 分歧率 **50%**、KL=**5.23**。**weight-only 量化不是"无害的"——它显著伤害输出，但 activation-based 检测器完全看不见。** 这是真实盲区，不是"正确拒绝无害行为"。

2. **W8A8 可检测且伤害更大**：SignRadial=0.083（可检测），token 分歧率 **86%**、KL=**8.62**。SignRadial 检测到的漂移对应**真实、更大的输出伤害**。

3. **检测能力与输出伤害不完全对齐**：
   - 可检测的（W8A8）确实伤害大 → 检测有意义
   - 不可检测的（W8A16）也伤害中等 → 存在漏检，且漏检的是**有实际危害**的行为

---

## 4. 对论文（NDSS）的意义

- **诚实披露**：SignRadial（activation-based）能捕获"activation 也低精度"的作弊（W8A8），但**漏掉"仅权重低精度"的作弊（W8A16），即使它确实伤害 50% 输出**。
- **分层检测架构**：
  - **Activation 级**（SignRadial + ProjCos）：检测 W8A8、scale、replay、方向变化等
  - **输出级**（judge 模型 / KL 筛查）：检测 W8A16 这种 activation 不可见的作弊
  - 两者互补，覆盖"偷算力且伤害输出"的全部形式
- **downstream-harm coupling 是审稿人关心的核心问题**：这个结果证明检测能力与输出伤害的关联是有信息量的（W8A8 的漂移→伤害，W8A16 的漏检→伤害被错过），需要分层检测而非单一 activation 检测器。

---

## 5. 产物

```
workspace/SRR/
├── p4c_downstream_harm_v2.py    # RTX3090 脚本
├── p4c_downstream_harm.py       # 初版（含不稳定的 INT8/FP8/INT4，已弃用）
└── docs/P4C_DOWNSTREAM_HARM.md  # 本文件
```

**复现**：`scp p4c_downstream_harm_v2.py 3090:~/VeriEdge-repro/ && ssh 3090 'cd ~/VeriEdge-repro && ./.venv/bin/python3 p4c_downstream_harm_v2.py'`
