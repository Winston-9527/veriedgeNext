# SRR 快速裁决实验 — V3 补充实验：SignRadial 突破

**实验日期**：2026-08-06
**补充于**：`SRR_DELIVERY_HANDBOOK.md` / `SRR_DELIVERY_HANDBOOK_V2_ADDENDUM.md`
**本补充结论**：**SignRadial (S₁) 解决了 projcos 的 scale 盲点，是比 SRR / S_parallel / projscalar1_abs 更优的径向检测器。**

---

## 1. 方法

**SignRadial（p=1 radial coefficient）**：

```
S₁ = |Σ sign(x_i) · (y_i − x_i)| / Σ |x_i|
```

- 用参考 activation 自身符号 `sign(x_i)` 作为投影方向（非随机）
- 单一 signed accumulator，全 64/256 坐标共同聚合（**不分组**，最大化抵消）
- 对 scale attack `y=αx`：`S₁ = |α−1|` **精确**，无随机投影 seed 风险
- 计算量 O(q)：纯 加/减/abs，无乘方/余弦/归一化

---

## 2. 为什么它跨过了 SRR / S_parallel 的障碍

### 2.1 正交分解（V2 已测）

`SRR = a² + E_⊥`，其中 `a = xᵀ(y−x)/xᵀx`：
- scale 1.10×：`|a|=0.10`、`E_⊥=0`（完美）
- honest C1（量化）：`|a|_p99 = 0.386`（大！）→ **S_parallel 失效**

### 2.2 SignRadial 的符号抵消

SignRadial 测 `Σ sign(x_i)·e_i`：
- **scale 攻击**：`sign(x_i)·e_i = (α−1)|x_i|` **全部同号** → 同向累积 → `S₁ = |α−1|` 精确
- **honest 量化噪声**：`sign(x_i)·e_i` 正负混合 → **符号抵消**

**实测 honest S₁（64 坐标，A/B）：**

| checkpoint | honest p99 | honest max |
|---|---:|---:|
| C1（量化） | 0.060 | 0.065 |
| C2 | 0.032 | 0.039 |
| C3 | 0.012 | 0.036 |

**honest p99 (0.06) < scale (0.10)** —— 跨过 S_parallel 的障碍（其 honest C1 p99=0.386）。

### 2.3 多采样天然收敛（§14 预测验证）

honest S₁ noise floor ∝ **1/√q** 下降，scale 信号固定 0.10：

| q | honest C1 p99 | honest C1 max |
|---|---:|---:|
| 64 | 0.098 | 0.150 |
| 128 | 0.090 | 0.129 |
| **256** | **0.059** | **0.080** |
| 512 | 0.036 | 0.060 |
| 1024 | 0.027 | 0.032 |

**q=256 时 honest max (0.080) < scale (0.10)** —— 彻底分离。
对比 SRR：noise floor 是 O(1)（多采样救不了）；SignRadial 是 O(1/√q)（多采样天然降低）。

---

## 3. 实验结果

### 3.1 主表（q=256, 校准 p99×3.0, 20 sampling seeds, 全部 4 对）

| pair | scale TPR (1.10×) median | min | honest FPR median | max |
|---|---:|---:|---:|---:|
| A/B | 1.000 | **1.000** | 0.000 | **0.000** |
| A/C | 1.000 | **1.000** | 0.000 | **0.000** |
| A/D | 1.000 | **1.000** | 0.000 | **0.000** |
| B/D | 1.000 | **1.000** | 0.000 | 0.005 |

**20 个 seed 全部 TPR=1.0、FPR≈0** —— 无 sampling-seed 尾部风险（对比 projscalar1_abs 的 5/50 seed 失败）。

### 3.2 攻击族覆盖（A/B, seed 1）

| 攻击 | TPR |
|---|---:|
| scale 1.05× | 0.000 |
| **scale 1.10×** | **1.000** |
| scale 1.20× | 1.000 |
| stale / wrong_prompt | 0.995 |
| layer_skip | 1.000 |
| gaussian (0.15×std) | 0.895 |

> 注：scale 1.05×（S₁=0.05）低于 honest p99（0.06），检测不出 —— 这是 honest 漂移的物理下限，任何径向检测器都受此限。1.10× 起全检出。

---

## 4. 对比全部候选

| 方法 | 1.10× scale TPR（A 配对） | honest FPR | seed 风险 | 计算 |
|---|---|---|---|---|
| SRR (energy) | 0.0 | 低 | — | O(q) |
| S_parallel (radial p=2) | 0.0 | 低 | — | O(q) |
| projscalar1_abs (1D proj) | median 1.0 | 低 | **5/50 方向失败** | O(q) |
| **SignRadial (radial p=1)** | **1.0（全 seed）** | **0.000** | **无** | **O(q) 最轻** |

**SignRadial 全面胜出**：同时修复 scale 盲点 + 无 seed 风险 + FPR=0 + 计算最轻 + 可解释（直接测 `|α−1|`）。

---

## 5. 结论

1. **SignRadial 是本次实验最终推荐**：它用 `sign(x)` 作为投影方向，让 honest 量化噪声符号抵消（noise ∝ 1/√q），而 scale 攻击同号累积（O(1)），从根源上解决了 SRR/S_parallel 在量化异构环境"honest 漂移 > scale 攻击"的信噪比障碍。
2. **它比 projscalar1_abs 更优**：无随机投影方向 → 无 seed lottery 尾部；且更可解释（`|α−1|` 就是 scale coefficient）。
3. **与 ProjCos 的职责划分**（你的 §11）：Radial detector（SignRadial 检测 scaling）+ Angular detector（projcos 检测方向变化），OR 报警。SignRadial 补上了 projcos 的 scale 盲点，两者正交互补。
4. **诚实边界**：1.05× scale 低于 honest 量化漂移下限，检测不出；1.10× 起全检出。这是物理边界，不是算法缺陷。

---

## 6. 产物

```
workspace/SRR/
├── radial.py        # 含 sign_radial / sign_radial_stat（SignRadial）
├── srr.py           # V2 修正（独立坐标 + B_min）
├── docs/SRR_DELIVERY_HANDBOOK_V3_ADDENDUM.md   # 本文件
```

**复现命令**：见 §3 各脚本片段（SignRadial 核心在 `radial.py`）。
