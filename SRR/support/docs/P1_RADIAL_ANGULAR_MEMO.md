# P1：Radial-Angular controlled perturbation — TPR@1%FPR vs θ（720 池，双机）

> 日期：2026-08-08
> 对应：评审点 P1（机制实验——证明 SR/ProjCos 对应 activation error 的两个几何分量）
> 数据：720 池（200 calib / 520 eval），A=MPS bf16 / B=CUDA fp32
> 脚本：`run_p1_radial_angular.py` → `results/p1_radial_angular.csv` + `p1_radial_angular.png`

---

## 0. 结论先行

**θ=0（纯 radial）完美复现 scale 机制：SignRadial=1.0、ProjCos=0.015（=FPR，数学盲）。但 θ≥15° 后所有 detector 都升高——SignRadial 对 angular 也不完全盲，只对 sign-canceling 方向盲。**

| θ | Scalar16 | ProjCos4 | SignRadial | Combined |
|---|---:|---:|---:|---:|
| **0°（纯 radial）** | 0.000 | 0.015 | **1.000** | 1.000 |
| 15° | 0.125-1.0 | 1.000 | 0.915 | 1.000 |
| 30-90° | 0.92-1.0 | 1.000 | 0.96-1.0 | 1.000 |

（ρ=0.05；ρ=0.1/0.2 趋势相同，见 §2）

---

## 1. 方法

对真实 benign pair (H_A, H_B)，从 H_B 构造：
```
r = H_B / ||H_B||_F                       (径向单位向量)
a = (g - <g,r>r) / ||g - <g,r>r||_F       (正交单位向量, g 随机)
Δ(θ) = ρ·||H_B||_F·(cosθ·r + sinθ·a)
H_attack = H_B + Δ(θ)
```
- θ∈{0,15,30,45,60,75,90}°——**所有攻击有相同的 relative-L2 magnitude ρ**，唯一变化是 radial↔angular 混合。
- ρ∈{0.05, 0.10, 0.20} 三档。
- 已验证几何：θ=0 时 cos(Δ,H)=1.0（径向），θ=90° 时 cos(Δ,H)=0.0（正交），‖Δ‖/‖H‖=ρ 恒定。

---

## 2. 结果

### 2.1 θ=0（纯 radial）= scale 机制的复现

| ρ | Scalar16 | ProjCos4 | SignRadial |
|---|---|---|---|
| 0.05 | 0.000 | 0.015 | **1.000** |
| 0.10 | 0.000 | 0.015 | **1.000** |
| 0.20 | 0.002 | 0.015 | **1.000** |

与 P2 的 scale=1.10× 结果一致（radial 扰动 ≡ scale-like）。**ProjCos 平台、SR 满检测**。

### 2.2 θ≥15°（含 angular 分量）

| θ | Scalar16(ρ=0.05) | ProjCos4 | SignRadial | Combined |
|---|---|---|---|---|
| 15° | 0.125 | 1.000 | 0.915 | 1.000 |
| 30° | 0.917 | 1.000 | 0.963 | 1.000 |
| 45° | 1.000 | 1.000 | 0.969 | 1.000 |
| 90°（纯 angular）| 1.000 | 1.000 | 0.967 | 1.000 |

**ProjCos 立即升高**（θ≥15° → 1.0），因为 Δ 含 angular 分量改变了投影方向。**Scalar16 随 θ 上升**（ρ=0.05 时 15°→0.125、30°→0.92）。

---

## 3. 解读

### 3.1 支持的核心机制（评审 P1 的正面证据）

**θ=0 的对比是决定性的**：SignRadial=1.0 vs ProjCos=0.015（=FPR）。这证明了**对纯 coherent radial drift，ProjCos 数学上不可见、SignRadial 完全检测**——与 scale 攻击同构。SR 不是偶然能检测 1.1×scale，而是检测 activation error 的 radial 分量。

### 3.2 与"理想预期"的差异（诚实报告）

理论预测 θ→90° 时 SignRadial 应下降（angular 不产生 coherent radial signal）。**实测 SignRadial 在 θ=90° 仍 0.97**。

原因：**θ=90° 的 Δ 是随机正交方向，sign(x)·Δ 是随机游走（~√q 量级），但当 ρ 足够大（0.05-0.2），这个随机游走的幅度已超过 honest 阈值**。SignRadial 的盲点**不是"所有 angular"，而是 sign(x)·Δ **精确 cancel** 的方向（即 sign-balanced 攻击，P1a 已证明 TPR→0）。

**结论**：P1 证明的是——
1. **ProjCos 对 radial 完全盲**（θ=0 → TPR=FPR）；
2. **SignRadial 对 coherent radial 强**（θ=0 → 1.0），对一般 angular 中等（θ=90° → 0.97），**只对 sign-canceling 方向真正盲**；
3. **Combined 全区间覆盖**（全 θ 全 ρ → 1.0）。

### 3.3 对"是不是只有 scale 体现 SR 优势"的回答

**不是只有 scale**。θ=0（radial）是 ProjCos 的盲区、SR 的强区，而 radial 扰动是更一般的几何族（scale 是其特例）。加上 P0 主表里 stale/layer_skip 的 SR=1.0，SR 的优势覆盖多个攻击族。Combined 通过 max-fusion 覆盖 ProjCos 的 radial 盲区 + SR 的 sign-cancel 盲区。

---

## 4. 局限

| 局限 | 说明 |
|---|---|
| ρ 偏大 | ρ≥0.05 时 angular 端信号已足够触发 SR，掩盖了"SR 对 angular 弱"的细节。要看清 SR 的 angular 衰减需 ρ 更小（如 0.01-0.02）|
| 单 checkpoint | 攻击只作用 C2（与 P0/P2 一致）|
| 单 pair | A/B |

**建议补充**：ρ=0.01/0.02 的细扫，看 SR 在 θ→90° 是否开始下降（更清晰地展示"SR 偏 radial、ProjCos 偏 angular"的几何分工）。

---

## 5. 下一步

- **P3 真实精度**：RTX3090 `_int_mm` W8A8，把低精度误差 Δ 分解为 radial/orthogonal，报告 ρ_∥、ρ_⊥——回答"真实 precision downgrade 是否产生 coherent radial component"。
- P1 细扫 ρ=0.01-0.02（可选，补 SR 的 angular 衰减细节）。

---

## 6. 复现

```bash
cd /Users/siyuan/Developer/ndss2027/.claude/worktrees/recursing-austin-d31ca0/workspace/SRR
python3 run_p1_radial_angular.py   # → results/p1_radial_angular.csv + .png
```
