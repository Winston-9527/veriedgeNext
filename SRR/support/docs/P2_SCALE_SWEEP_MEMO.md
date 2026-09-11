# P2：Scale strength sweep — TPR@1%FPR vs |α-1|（720 池，双机）

> 日期：2026-08-08
> 对应：评审点 P2（scale sweep killer experiment）
> 数据：720 池（200 calib / 520 eval），A=MPS bf16 / B=CUDA fp32
> 脚本：`run_p2_scale_sweep.py` → `results/p2_scale_sweep.csv` + `p2_scale_sweep.png`

---

## 0. 结论先行

**Scale sweep 完美复现理论预测：ProjCos4 在全部 α 上 TPR≈FPR（平台），SignRadial 随 |α-1| 单调上升（2% 处跳到 1.0），Combined 跟随上升且全区间覆盖。**

| \|α-1\| | Scalar16 | ProjCos4 | SignRadial | Combined |
|---|---:|---:|---:|---:|
| 0.010 (α=0.99) | 0.000 | 0.015 | 0.629 | 0.410 |
| 0.010 (α=1.01) | 0.000 | 0.015 | 0.698 | 0.554 |
| 0.020 (α=0.98/1.02) | 0.000 | 0.015 | **1.000** | **1.000** |
| 0.050 (α=0.95/1.05) | 0.000 | 0.015 | 1.000 | 1.000 |
| 0.100 (α=0.90/1.10) | 0.000 | 0.015 | 1.000 | 1.000 |

honest eval FPR：scalar16=0.0、projcos4=0.015、signradial=0.010、combined=0.010。

---

## 1. 方法

- 攻击：`H_attack = α·H_B`（从真实候选 H_B 构造），α∈{0.90,0.95,0.98,0.99,1.01,1.02,1.05,1.10}。
- detector 阈值：P0 主表同一协议（calibration 200 honest 的 Q_{0.99}，联合校准 max-fusion for combined）。
- 评估：eval 520 条，TPR@1%FPR + Wilson 95% CI。
- 统一 `D(H_A, A(H_B))`。

---

## 2. 结果与解读

### 2.1 ProjCos4 平台 = 数学盲点（理论验证）

ProjCos4 在全部 α 上 TPR=0.015（≈FPR 0.015）。**不是"表现不好"，而是根本没有 scale 信息**：
```
cos(H_A R, αH_B R) = cos(H_A R, H_B R)
```
投影余弦对 scale 不变。这张图直接证明了评审点 P2 的理论。

### 2.2 SignRadial 单调上升 = coherent radial signal

- |α-1|=1%：TPR=0.63-0.70（弱 scale 部分检测）
- |α-1|=2%：TPR 跳到 **1.0**
- 更大幅度保持 1.0

因为 `H_attack - H_B = (α-1)H_B` 产生**相干径向信号**（所有采样坐标同号），SignRadial 的 `|Σ sign(x)(y-x)|` 不 cancel，随 |α-1| 线性增强。检测 transition 出现在 ~2%。

### 2.3 Combined = max(SR, ProjCos)

Combined 跟随 SignRadial 上升（|α-1|≥2% 全 1.0），且 1% 处 0.41-0.55（比 SR 单独略低是因为联合阈值更保守）。**全区间无盲点**。

### 2.4 Scalar16 = 双机异构下对 scale 完全盲

Scalar16 全程 TPR=0.0。MPS/CUDA 双机异构下，scalar 的 max|diff| 阈值在 honest 上已很高（FPR=0），scale 的额外幅度不足以越过。Scalar 对 scale 无检测能力。

---

## 3. 给 mentor 的一页图

`results/p2_scale_sweep.png`：
- 横轴 |α-1|（1%→10%）
- 纵轴 TPR@1%FPR
- ProjCos4 平线 ≈1%（灰虚线），SignRadial 在 2% 处跳升到 1.0，Combined 覆盖

**一句话解释**：ProjCos 看 angular drift（对 scale 数学上不可见），SignRadial 看 coherent radial drift（对 scale 敏感），二者互补。Combined = max 覆盖两者。

---

## 4. 局限

| 局限 | 说明 |
|---|---|
| 单 pair | A/B（MPS/CUDA）|
| α 粒度 | 1%→2%→5%→10%，2% 处 transition 陡峭，可加 1.5% 细化 |
| combined 1% 处略低 | 联合阈值保守，|α-1|≥2% 后即 1.0 |

---

## 5. 下一步

- **P1 radial-angular**：Δ(θ)=ρ‖H_B‖(cosθ·r + sinθ·a)，θ∈{0..90°}——用几何分量解释为什么 ProjCos/SR 互补。
- **P3 真实精度**：RTX3090 `_int_mm` W8A8 + radial/orthogonal 分解。

---

## 6. 复现

```bash
cd /Users/siyuan/Developer/ndss2027/.claude/worktrees/recursing-austin-d31ca0/workspace/SRR
python3 run_p2_scale_sweep.py   # → results/p2_scale_sweep.csv + .png
```
