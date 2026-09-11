# TSTC 检测器 fixed-FPR 公平比较 memo（v2，统一协议）

> 日期：2026-08-08
> 背景：针对评审反馈重做检测器比较。v1 用 grid-search 阈值（FPR 不统一，Scalar16=0.150/0.415 等），已改为 fixed-FPR 校准。**v2 进一步修正实验定义：所有攻击从 y0=H_B 出发、始终比较 D(H_A, y)，使 attack 样本与 honest 共享 A/B 异构 nuisance。**
> 数据：`reproduction/VeriEdge/workspace/sanity_20260728_m4_m4_rtx3090/captures/`（A/B）+ `sanity_20260727/captures/`（B/D），40 calib / 200 eval。

---

## 0. 结论先行（v2 修正后）

**统一协议（D(H_A, y)）后，之前的部分极端 AUROC（0.00/0.12/0.19）被证伪为"attack 样本缺 A/B nuisance"的实验假象，而非检测器的真实结构盲点。**

| 攻击 | 检测器 | v1 AUROC（attack 无 nuisance） | v2 AUROC（统一 D(H_A,y)） | 判定 |
|---|---|---|---|---|
| scale | ProjCos4/16 | 0.00 | **0.50** | 假"绝对盲"→ 实为"与 honest 不可分" |
| null_space | Scalar16 | 0.19 | 0.50 | 假"强盲"→ 随机 |
| null_space | SignRadial | 0.12 | 0.56 | 假"强盲"→ 略高于随机 |
| null_space | ProjCos16 | 0.72 | 0.95 | 真实能力，且更强 |
| scale | Scalar16 | 0.63 | 0.81 | 真实能力，略增 |
| scale | SignRadial | 1.00 | 0.9999 | 真实能力，不变 ✅ |

**核心结论（与用户点 11/12 一致）**：
1. **SignRadial 对 scale 的检测（AUROC≈1.0）是真实且稳健的**——统一协议后不变。
2. **ProjCos 对 scale 的"盲"从 AUROC=0.00 修正为 0.50**：不是"反向检测"，而是"完全不可分"（scale 攻击的 cos 变化 < honest 的 A/B 方向变化）。
3. **ProjCos 对 null_space 的检测（0.95）比 SignRadial（0.56）更强**——真实互补关系，且统一协议后更清晰。
4. **统一协议前后差异巨大，证明评审点 12 的批评完全成立**：attack 必须共享 honest 的 A/B nuisance，否则部分 AUROC 是人为的。

---

## 1. 统一实验定义（评审点 12）

```
x  = H_A          （reference，固定）
y0 = H_B          （base，固定）
所有攻击从 y0 出发；始终比较 D(H_A, y)：
  Honest:      y = H_B
  Gaussian:    y = H_B + ε            （ε = 0.15·std(H_B)·N(0,1)）
  Scale:       y = 1.10·H_B
  Stale:       y = H_B^previous        （另一个 prompt 的 B）
  Null:        y = H_B + δ_null        （相对 H_B 采样坐标的正交扰动）
  Layer skip:  y = H_B^skip            （C2 ← 同 prompt 的 C1）
```

**为什么关键**：v1 的 attack 用 `D(attack(H_B), H_B)`——attack 只含攻击信号，不含 honest 的 A/B 异构。而 honest 是 `D(H_B, H_A)`——含 A/B 异构。两个分布基准不同，AUROC 被扭曲。v2 统一后 attack 也含 A/B nuisance，与 honest 同基准。

---

## 2. 方法（与 v1 相同的 fixed-FPR 协议）

- **连续 score**：Scalar=`max\|ref-cand\|`、ProjCos=`mean(1-cos)`、SignRadial=`\|Σsign(x)(y-x)\|/Σ\|x\|`（各 C1/C2/C3 取 max 作 trace score）
- **校准**：calibration honest score 的 `τ_D(α)=Q_{1-α}(S_D^honest)`，α∈{0.1%,1%,5%}
- **评估**：eval 200 条，honest 报 FPR、attack 报 TPR@FPR；另算 AUROC

---

## 3. 结果（v2 统一协议）

### 3.1 TPR@1% FPR（A/B 与 B/D 平均）

| 检测器 | eval FPR | gauss | stale | scale | layer_skip | null_space |
|---|---|---|---:|---:|---:|---:|---:|
| Scalar16 | 0.030 | 1.0 | 0.92 | 0.53 | 0.99 | 0.02 |
| Scalar64 | 0.095 | 1.0 | 0.94 | 0.61 | 1.0 | 0.04 |
| ProjCos4 | 0.118 | 1.0 | 1.0 | ~FPR | 1.0 | 0.54 |
| ProjCos16 | 0.080 | 1.0 | 1.0 | ~FPR | 1.0 | 0.78 |
| **SignRadial** | 0.013 | 0.97 | 0.91 | **1.0** | 1.0 | 0.02 |

> ProjCos 的 scale TPR≈eval FPR（0.11/0.05）：scale 对 ProjCos 完全不可见，与 AUROC=0.5 一致。

### 3.2 AUROC（v2 统一协议，A/B 与 B/D 平均）

| 攻击 | Scalar16 | Scalar64 | ProjCos4 | ProjCos16 | **SignRadial** |
|---|---:|---:|---:|---:|---:|
| gaussian | 1.00 | 1.00 | 1.00 | 1.00 | **0.99** |
| scale | 0.81 | 0.90 | **0.50** | **0.50** | **1.00** ✅ |
| stale | 0.99 | 0.99 | 1.00 | 1.00 | **0.97** |
| wrong_prompt | 0.99 | 0.99 | 1.00 | 1.00 | **0.97** |
| layer_skip | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| null_space | **0.50** | 0.56 | 0.84 | **0.95** ✅ | **0.56** |

### 3.3 u-histogram（统一协议，A/B，40 prompts）

| 情况 | mean | frac>0 | 结构 |
|---|---|---|---|
| honest | -0.010 | 0.456 | zero-centered、正负平衡 |
| gaussian | 0.008 | 0.500 | zero-centered、sign-balanced |
| **scale 1.10×** | 0.140 | **0.869** | 右偏（含 A/B nuisance 后不再是全 0.999，但仍明显右偏） |

图：`results/u_histogram_sanity.png`

---

## 4. 关键解读（对应评审各点）

### 4.1 评审点 12（attack-on-B）→ 已修正，且证伪了部分假盲点

统一协议后，`scale→ProjCos AUROC=0.00→0.50`、`null_space→Scalar16=0.19→0.50`、`null_space→SignRadial=0.12→0.56`。**这些"绝对盲"大多是实验定义缺陷**（attack 缺 A/B nuisance），不是检测器真实结构性质。

### 4.2 评审点 11（正交互补）→ 统一协议后更清晰

| | SignRadial | ProjCos |
|---|---|---|
| Scale 1.10× | **1.0** ✅ | 0.50（不可分） |
| null_space | 0.56 | **0.95** ✅ |

SignRadial 补 ProjCos 的 scale 盲点；ProjCos 补 SignRadial 的 null_space 弱点。双头架构仍有依据，但**"ProjCos 对 scale 绝对盲（0.00）"要改写为"不可分（0.50）"**。

### 4.3 评审点 7/8（threshold 校准）→ 已由 fixed-FPR 解决

Scalar64 的 0.415 是 max-statistic 未随 q 校准（`1-(1-p)^q`，p=1%、q=64 → 47.4%）。fixed-FPR 后消除。

### 4.4 评审点 9/10（u-histogram / Gaussian 加性）→ 已确认

Gaussian 是加性（`y=x+0.15·std·ε`）。u-histogram 证实 scale 右偏、gaussian 平衡。

---

## 5. 独立发现：eval FPR 漂移（honest 分布 calib/eval 不稳定）

统一协议下，eval FPR 仍偏离 nominal α（如 ProjCos4 α=1% → eval FPR=11%）。数据证实：calib(n=40) honest score 中位 1.63e-4、p99=3.56e-4；eval(n=200) 中位 1.98e-4、p99=9.50e-4（2.7×）、max 1.49e-3（4×）。**不是阈值选错，而是 eval 有少数 prompt 的 honest A/B 差异在投影方向被放大（长尾）**。

**影响**：所有检测器受同样漂移影响，横向比较仍公平；但 40 条 calib 的 Q_{0.99} 无法精确预测 eval FPR。建议后续用 conformal 留余量或增大 calib。

---

## 6. 局限与下一步

| 局限 | 说明 |
|---|---|
| 采样非秘密 | 固定 seed 2026（对齐 frozen 基线）；秘密 per-request 抽样是另一变体（p5c 研究），TPR 会不同 |
| 40 条 calib | Q_{0.999} 估计粗糙（α=0.1% 即 40 条里 0 条）；eval FPR 漂移（§5） |
| 攻击强度固定 | gaussian σ=0.15 是强攻击（96× honest），需 sweep σ 区分方法敏感度 |
| 范围 | A/B、B/D 两 pair |

**下一步**（评审点 11 第三件事）：**sweep Gaussian 强度 σ/RMS(H)，画 TPR vs attack strength**；并做二维图（如 scale vs gaussian 的检测空间）前，先按本 v2 统一协议重跑。已满足前置条件。

---

## 7. 复现

```bash
cd /Users/siyuan/Developer/ndss2027/.claude/worktrees/recursing-austin-d31ca0/workspace/SRR
python3 run_fixed_fpr_comparison.py     # v2 统一协议 → fixed_fpr_comparison.csv, fixed_fpr_auroc.csv
python3 plot_u_histogram.py             # 统一协议 → u_histogram_sanity.png
```
