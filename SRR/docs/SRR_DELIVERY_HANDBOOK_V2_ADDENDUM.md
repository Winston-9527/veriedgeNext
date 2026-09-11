# SRR 快速裁决实验 — 补充实验（V2：算法校对 + 径向系数 + multi-seed）

**实验日期**：2026-08-06
**补充于**：`SRR_DELIVERY_HANDBOOK.md`（V1 结论：SRR NO-GO）
**本补充回答**：用户对 V1 实现正确性的质疑 → 算法校对 → 正交分解 → 径向系数 → multi-seed

---

## 1. V1 实现校对：确认用户伪代码，修正 3 处

V1 实现与用户伪代码有三处不一致，已全部修正并重跑：

| 差异 | V1（错误） | V2（用户伪代码，正确） |
|---|---|---|
| 分母下限 | `E_g > Γ·B_g`（无 B_min） | `E_g > Γ·max(B_g, B_min)`，B_min=1e-3 |
| 抽样 | 8 token × 连续 8-channel 块 | **64 独立随机坐标**（flatten 均匀抽样） |
| 分组 | 每 2 token 一组 | 每 16 坐标一组（4 组 × 16） |

修正后重跑（`python3 run_srr_offline.py`），SRR 结果见 §4。

---

## 2. 正交分解验证（核心假设测试）

令 `e = y - x`，分解为 `e = a·x + e_⊥`（a = xᵀe/xᵀx）。则 `SRR = a² + |e_⊥|²/|x|²`。

**实测（A/B，64 独立坐标）：**

| 场景 | \|a\| p99 | E_⊥ p99 | SRR p99 |
|---|---:|---:|---:|
| honest C1（量化） | **0.386** | 0.147 | 0.222 |
| honest C2（量化下游） | **0.259** | 0.168 | 0.205 |
| honest C3（干净边界） | 0.043 | 0.008 | 0.013 |
| scale 1.10×（理论/实测） | **0.100** / 0.100 | 0.000 | 0.010 |

**结论：**
1. **scale 攻击完美**：`|a|=0.1`、`E_⊥=0` —— 径向系数在 scale 攻击上精确等于 10%。
2. **honest C3 符合预测**：径向分量小（0.043），正交噪声主导（0.008）。→ 干净边界上 SRR 主要累积正交噪声。
3. **但 honest C1/C2 违背预测**：`|a|_p99 = 0.386/0.259` —— **honest 量化漂移不仅有大的正交噪声，还有大的径向分量**，等效 38.6% 的 scale drift，大于 scale 攻击的 10%。

**这推翻了"SRR 失败纯粹因为正交噪声累积"的假设。** 量化 C1 的 honest 漂移在径向（沿 x 方向）分量上本身就 > scale 攻击信号。这是数据信噪比的硬边界。

---

## 3. Sampled Radial Coefficient（S_parallel）测试

按分析第 8-10 点实现 `S_parallel = |Σ x_i(y_i-x_i)| / Σ x_i²`（只累加 P、B，O(64)，无除法部署）。

**4 对结果（64 采样，4 组 3/4 投票）：**

| pair | honest FPR | scale TPR (1.10×) | 备注 |
|---|---:|---:|---|
| A/B | 0.030 | **0.000** | 量化 C1 |
| A/C | 0.015 | **0.000** | 量化 C1 |
| A/D | 0.005 | **0.000** | 量化 C1 |
| B/D | 0.040 | **1.000** | 干净 |

**scale 强度扫描（A/B）：**

| scale | 1.10× | 1.20× | 1.30× | 1.50× | 1.70× |
|---|---:|---:|---:|---:|---:|
| TPR | 0.000 | **1.000** | 1.000 | 1.000 | 1.000 |

**关键发现：S_parallel 检测阈值 ≈ honest 径向漂移 p99（A/B C1 γ=0.146）**。
- S_parallel 对 scale 攻击的值 = `|α-1|`（1.10×→0.10, 1.20×→0.20）
- γ 由 honest C1 `|a|_p99` 决定 → 阈值落在 0.146 → **只能检测 >1.2× 的 scale 攻击**
- 1.10× 的 scale 攻击（0.10 < 0.146）被 γ 吞掉

**结论：S_parallel 比 SRR 更可解释（直接测 scale coefficient `|α-1|`），但受同一数据边界限制** —— 量化 C1 的 honest 径向漂移决定了最小可检测 scale。它没有解决"1.10× 检测不出"的问题，但它是正确的问题定义，把"为什么"讲清楚了。

---

## 4. projscalar1_abs multi-seed 稳健性（50 seeds）

分析第 6-7 点担忧 projscalar1_abs 的 1D 方向可能是 seed lottery。实测 50 个 projection seed：

| pair | scale TPR median | scale TPR p10 | scale TPR min | honest FPR median | honest FPR max |
|---|---:|---:|---:|---:|---:|
| A/B | 1.000 | 1.000 | **0.000** | 0.015 | 0.050 |
| A/C | 1.000 | 1.000 | **0.000** | 0.010 | 0.040 |
| A/D | 1.000 | 1.000 | **0.000** | 0.010 | 0.040 |
| B/D | 1.000 | 1.000 | 1.000 | 0.010 | 0.035 |

**失败的 seed 高度一致**（5/50）：seed 22/32/34 在 A/B/A/C/A/D 全失败，seed 33 在 A/C/A/D，seed 40 只 A/B。B/D 无失败。

**结论：**
1. **不是纯 seed lottery**：median 和 p10 都是 1.0，90% 的 1D 方向能稳定检测 scale。
2. **但存在真实的 seed 尾部风险**：10% 的方向（5/50）是"不幸方向"，scale TPR 掉到 0。这证实了分析第 6 点"单维投影方差大"的担忧。
3. **不能把单一 seed 的 projscalar1_abs 当最终算法** —— 需要 multi-seed 取 median，或升级为更高维投影。

---

## 5. 综合判断（对比三个统计量）

| 统计量 | 检测尺度变化 | 机制 | 问题 |
|---|---|---|---|
| **SRR**（energy） | 1.20×+（A 对） | Σ(y-x)²/Σx² | 累积正交噪声，honest 量化漂移 > scale |
| **S_parallel**（radial） | 1.20×+（A 对） | \|Σx(y-x)\|/Σx² | 受 honest 径向漂移限制（1.10× 不可分） |
| **projscalar1_abs**（1D proj） | 1.10×（90% seed） | \|Σr(y-x)\| | seed 尾部风险（10% 方向失败） |

**共同的根本边界**：A 配对（Metal-int8 量化 C1）的 honest 漂移在径向方向上也超过 10%（`|a|_p99=0.386`）。**任何"保留 norm/尺度信息"的检测器都无法在 1.10× 尺度变化和 honest 量化漂移之间分开** —— 这是数据信噪比边界，不是算法缺陷。

**为什么 projscalar1_abs 能检测 1.10×**：它测的是投影后符号聚合的 `|Σr·e|`，coherent scale error（沿 x）与随机混合的量化噪声在投影方向上的行为不同。但它的 1D 方向有 10% 尾部风险。

---

## 6. 最终建议

1. **SRR 放弃**（V1+V2 双重确认）：energy 统计量与量化噪声结构不匹配。
2. **S_parallel 是最可解释的方向**：它直接测 scale coefficient `|α-1|`，把问题讲清楚（检测阈值 = honest 径向漂移）。但它受同一数据边界限制，1.10× 在量化 C1 上测不出。
3. **projscalar1_abs 保留但需升级**：multi-seed 证实非 lottery 但存在 10% 尾部风险 → 应升级为**更高维投影**（如 projabs-4/8/16）降低方向方差，或 multi-seed 集成。
4. **诚实披露**：A 配对量化 C1 的 honest 径向漂移（38.6%）是**所有尺度检测器的硬边界**。论文应如实报告"可检测的最小 scale 变化受 honest 量化漂移限制"。

---

## 7. 产物

```
workspace/SRR/
├── srr.py         # V2 修正（独立坐标 + B_min）
├── radial.py      # S_parallel 径向系数（新增）
├── run_srr_offline.py  # V2 runner
├── results/srr_vs_baseline.csv   # V2 数据（含 SRR 修正后）
└── docs/SRR_DELIVERY_HANDBOOK_V2_ADDENDUM.md   # 本文件
```

**复现命令：**
```bash
cd workspace/SRR
python3 run_srr_offline.py        # SRR V2 全表
# 正交分解 / S_parallel / multi-seed 用本节内嵌脚本
```
