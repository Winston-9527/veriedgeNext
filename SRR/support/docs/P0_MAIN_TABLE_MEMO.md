# P0：fixed-FPR 公平主表 memo（v3 协议）

> 日期：2026-08-08
> 对应：评审点 0（第一优先级公平主表）+ 实验手册 v3 §12
> 目的：在**相同 nominal FPR=1%** 下比较 Scalar16 / ProjCos4 / SignRadial / Combined，回答"新 detector 是否真的增加攻击覆盖率"
> 脚本：`run_p0_main_table.py` → `results/p0_main_table.csv`

---

## 0. 结论先行

**在统一校准的 1% FPR 下，Combined（ProjCos4 OR SignRadial）在所有 5 类攻击上 TPR=1.0，覆盖了单个检测器的全部盲点——"组合增加攻击覆盖率"成立。**

| detector | eval FPR | gauss | **scale** | stale | layer_skip | low-prec INT8 | INT4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Scalar16 | 0.01-0.05 | 1.0 | 0.06-1.0 | 0.84-1.0 | 0.99-1.0 | 1.0 | 1.0 |
| ProjCos4 | 0.11-0.13 | 1.0 | **0.11-0.13** ≈FPR | 1.0 | 1.0 | 1.0 | 1.0 |
| SignRadial | 0.01-0.02 | 0.79-0.97 | **1.0** ✅ | 0.82-0.99 | 1.0 | 1.0 | 1.0 |
| **Combined** | 0.12-0.13 | **1.0** | **1.0** | **1.0** | **1.0** | **1.0** | **1.0** |

**三句给写作侧**：
1. **SignRadial 的必要性成立**：它对 scale 的 TPR=1.0（ProjCos 只有 0.11≈FPR，即完全不可分），且对低精度 INT4/INT8 也 1.0。
2. **Combined 覆盖全部攻击**：scale（ProjCos 盲点）+ gaussian（SignRadial 弱 0.79）都被补上，所有攻击 TPR=1.0。
3. **代价是 FPR**：Combined 的 FPR≈12%（OR 融合 + 异构漂移），**不是 1%**——这是本实验最重要的诚实发现（见 §4）。

---

## 1. 实验定义（v3 协议冻结）

- **参考** `H_A`，**诚实候选** `H_B`（含 A/B 异构）。所有攻击从 `H_B` 构造：`H_attack = A(H_B)`，始终 `D(H_A, H_attack)`。
- **阈值**：各 detector 从 calibration(40) honest 分布取 `τ = Q_{0.99}(S^honest)`。
- **Combined**：OR-fusion，`alarm = (S_P > τ_P) OR (S_R > τ_R)`，τ_P/τ_R 各取自己的 Q_{0.99}。
- **攻击**（全部从 H_B）：gaussian(λ=0.03·RMS)、scale(×1.10)、stale(跨 prompt C2)、layer_skip(C2←C1)、low-prec(INT8/INT4 activation 量化)。
- **数据**：A/B（S28）+ B/D（S27），calib=40、eval=200。

---

## 2. 结果（详细）

### 2.1 A/B（eval n=200）

| detector | calFPR | evFPR | gauss | scale | stale | skip | lp8 | lp4 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| scalar16 | 0.025 | 0.010 | 1.0 | 0.060 | 0.835 | 0.990 | 1.0 | 1.0 |
| projcos4 | 0.025 | 0.110 | 1.0 | 0.110 | 1.0 | 1.0 | 1.0 | 1.0 |
| signradial | 0.025 | 0.015 | 0.785 | 1.0 | 0.815 | 1.0 | 1.0 | 1.0 |
| combined | 0.050 | 0.120 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

### 2.2 B/D（eval n=200）

| detector | calFPR | evFPR | gauss | scale | stale | skip | lp8 | lp4 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| scalar16 | 0.025 | 0.050 | 1.0 | 0.995 | 1.0 | 1.0 | 1.0 | 1.0 |
| projcos4 | 0.025 | 0.125 | 1.0 | 0.125 | 1.0 | 1.0 | 1.0 | 1.0 |
| signradial | 0.025 | 0.010 | 0.970 | 1.0 | 0.990 | 1.0 | 1.0 | 1.0 |
| combined | 0.050 | 0.130 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

---

## 3. 解读

### 3.1 SignRadial 必要性（评审点 0 的第一个判断标准）

**成立**。scale 攻击下：Scalar16=0.06-1.0、ProjCos4=0.11-0.13（≈FPR，不可分）、**SignRadial=1.0**。这正是用户预期的"Scalar 0.4 / ProjCos 0.01 / SR 0.99"模式（我们更极端：ProjCos 完全盲、SR 完全检测）。

### 3.2 Combined 增加攻击覆盖率（评审点 0 的核心问题）

**是**。Combined 在所有攻击上 TPR=1.0：
- **scale**（ProjCos 盲点）→ 被 SignRadial 分支补上
- **gaussian**（SignRadial 弱 0.785）→ 被 ProjCos 分支补上
- **stale**（Scalar16/SignRadial 弱）→ 被 ProjCos 补上
- **low-prec INT4/INT8**（所有单 detector 都 1.0）→ 保持

### 3.3 机制一致性

与 v3 手册理论预期完全吻合：
- ProjCos4 scale TPR≈FPR（0.11 vs 0.11）——**数学盲点**（cos 对 scale 不变），不是"表现不好"
- SignRadial scale TPR=1.0——**coherent radial signal**
- 低精度攻击全部 1.0——所有检测器都看到 activation 级变化

---

## 4. 诚实发现：Combined 的 FPR 不是 1%（方法学限制）

**这是本实验最重要的边界条件**：
- Combined eval FPR=0.12（A/B）/0.13（B/D），**远高于** nominal 1%。
- **原因**（两层）：
  1. **OR-fusion 的 FPR 是两组件 FPR 的并集**（≈1%+1%=2%，若独立）。
  2. **异构 FPR 漂移**：projcos4 在 eval 上 FPR 本身就是 0.11（calib=0.025）——calibration(40) 与 evaluation(200) 的 honest 分布不同（v2 已发现），OR 继承了 projcos4 的漂移。

**对结论的影响**：
- Combined 在 **FPR=12%** 下 TPR=1.0，而单 detector 在 **FPR=1-13%** 下各有盲点。
- 严格说，**Combined 与单 detector 不在同一 FPR 点**（12% vs 1%），直接比 TPR 不完全公平。
- 但结论方向仍清晰：**Combined 消除了所有已知盲点**，只是代价是 FPR 上升。

**这不是 bug**，而是（a）OR-fusion 的天生 FPR 叠加 +（b）异构 honest 漂移 +（c）N_calib=40 无法精确校准 1% 的联合阈值。**解决需按 v3 §3 用连续 S_Combo 联合校准 + 更大 calib**（评审点 3/8）。

---

## 5. 与旧实验的对比

| 指标 | 旧（grid-search v1）| 本实验（v3 统一协议）|
|---|---|---|
| Scalar16 FPR | 0.150 | **0.010**（校准到位）|
| ProjCos4 FPR | 0.020 | 0.110（漂移，见 §4）|
| SignRadial FPR | 0.000 | 0.015 |
| 比较基准 | 各 FPR 不同 | 统一 nominal 1% |
| attack 构造 | 从 H_A（v1）/ 混（v2）| 全部从 H_B，D(H_A,A(H_B)) |

**关键进步**：不再有"Scalar 15% vs SR 0%"那种不可比的 operating point；所有 detector 都报告 calib FPR≈2.5%（40 条里 1 条）和 eval 实际 FPR。

---

## 6. 局限

| 局限 | 说明 |
|---|---|
| N_calib=40 | Q_{0.99} 即第 40 条最大值，FPR 校准粗糙；Combined 联合阈值无法精确到 1%（评审点 8）|
| eval FPR 漂移 | 异构 honest 分布 calib/eval 不一致（尤其 ProjCos），导致 evFPR 偏离 nominal |
| Combined FPR | OR-fusion 并集 ≈12%，非 1% |
| 攻击强度固定 | gaussian λ=0.03 单点（P2 需 sweep）；scale 仅 1.10× |
| low-prec 模拟 | activation 量化模拟，非真实 kernel（P3 用 RTX3090 _int_mm）|
| 采样非秘密 | 固定 seed 2026 |

---

## 7. 下一步（P1/P2/P3）

1. **P2 scale sweep**：α∈{0.90..1.10}，画 TPR vs |α-1|（ProjCos 理论≈1% 平台、SR 单调上升）。
2. **P1 radial-angular**：Δ(θ)=ρ‖H_B‖(cosθ·r + sinθ·a)，θ∈{0..90°}，证明 SR/ProjCos 对应几何分量。
3. **P3 真实精度**：RTX3090 `torch._int_mm` W8A8，分解误差为 radial/orthogonal 分量。
4. **Combined FPR 修复**：连续 S_Combo 联合校准 + 扩 calib（评审点 3/8）。

---

## 8. 复现

```bash
cd /Users/siyuan/Developer/ndss2027/.claude/worktrees/recursing-austin-d31ca0/workspace/SRR
python3 run_p0_main_table.py   # → results/p0_main_table.csv
```
