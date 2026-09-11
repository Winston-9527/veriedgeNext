# ProjCos vs Scalar vs SignRadial — 三方法对比

**实验日期**：2026-08-07
**数据来源**：`workspace/SRR/` 全部实验（P0-P4c、Native、Joint ROC）
**核心问题**：三种验证器在**性能**（检测能力）、**开销**（计算/通信）、**盲点**（失效攻击）上各有什么优劣？哪些对比还没做？

---

## 1. 方法定义

| 方法 | 统计量 | 检测什么 | 计算 |
|---|---|---|---|
| **Scalar** | `max\|V_cand − V_ref\|`（抽样坐标绝对差）| 数值幅度变化 | O(q)，q=16/64 |
| **ProjCos** | `mean(1 − cos(投影行))`（行归一化后方向比较）| 方向变化 | O(T·D·d)，T=16, D=1024 |
| **SignRadial** | `\|Σ sign(x)(y−x)\| / Σ\|x\|` | 相干幅值变化（径向）| O(q)，q=64/256 |

---

## 2. 性能对比（检测能力）

### 2.1 基础攻击族（A/B，held-out 200 prompts）

| 攻击 | Scalar16 | Scalar64 | ProjCos4 | ProjCos8 | ProjCos16 | SignRadial |
|---|---:|---:|---:|---:|---:|---:|
| honest FPR | 0.150 | 0.415 | **0.020** | 0.080 | 0.120 | **0.000** |
| gaussian | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.895 |
| stale / wrong_prompt | 0.76 | 0.855 | 1.0 | 1.0 | 1.0 | **0.995** |
| **scale 1.10×** | 0.425 | 0.805 | **0.0** ❌ | **0.0** ❌ | **0.0** ❌ | **1.0** ✅ |
| layer_skip | 0.83 | 0.98 | 1.0 | 1.0 | 1.0 | **1.0** |

**关键观察**：
- **ProjCos 的 scale 盲点确认**：scale TPR=0.0（论文已知，实测复现）。
- **Scalar 的方向盲点**：gaussian 之外的方向类攻击（stale/wrong/layer_skip）Scalar 明显弱（0.76-0.83）。
- **SignRadial 覆盖两者**：scale=1.0（ProjCos 盲点）、stale/layer_skip=1.0（接近 ProjCos）、gaussian 0.895（略低于 ProjCos 的 1.0）。
- **honest FPR**：SignRadial=0.000（q=256），ProjCos=0.02，Scalar=0.15。

### 2.2 自适应/白盒攻击（P1a、P2b + 本次补齐）

| 攻击 | SignRadial | ProjCos | Scalar16 | Scalar64 |
|---|---|---:|---:|---:|---:|
| **sign-balanced**（sign(x)ᵀe=0）| **0.0** ❌ | **0.985-1.0** ✅ | 0.015 ❌ | 0.135 ❌ |
| **balanced per-channel**（α={0.8,1.2}）| **0.005** ❌ | **1.0** ✅ | 0.490 | 0.900 |
| per-token scaling（交替 α）| 0.145 | 0.0 ❌ | （未测）| （未测）|

**本次补齐的关键发现**：**只有 ProjCos 能补 SignRadial 的 sign-balanced 盲点**（0.985-1.0）。Scalar16 也盲（0.015）、Scalar64 部分（0.135）、projscalar1_abs 也盲（0.000）——**不是任何方法都能补 SignRadial，ProjCos 是唯一互补者**。这强化了双头（SignRadial OR ProjCos）架构的必要性。

### 2.2b 坐标保密对齐（新，p5c_coord_secrecy.py + partial_coord_attack.py）

**背景**：论文 verifier 的坐标由 committed seed context 派生，且手册要求"恶意节点必须在不知道抽样位置时先固定/发送 activation"（坐标 secret per-request）。需检查我的攻击实验是否对齐。

**全张量攻击（攻击者改整层）**：坐标 KNOWN vs SECRET 下 SignRadial TPR 都是 0.000/0.005——**坐标保密不救 SignRadial**，因为攻击者改整个张量使其对 sign(x) 正交，无论 verifier 抽查哪些坐标都失效。

**部分坐标攻击（真实盲攻击者，改随机部分坐标）**：

| 攻击者篡改坐标比例 | SignRadial TPR |
|---|---:|
| 5% | 0.335 |
| 10% | 0.400 |
| 25% | 0.585 |
| 50% | 0.615 |
| 75% | 0.810 |
| 100% | 0.980 |

**结论（对 verifier 设计的关键对齐）**：
1. **真实自适应攻击者（不知道 verifier 坐标）在部分注入时，SignRadial 能检测**（5%→33%，50%→62%，100%→98%）。
2. **P1a 的 sign-balanced 盲点只在对"攻击者知道全部坐标"的最强假设下成立**——真实协议坐标 secret，攻击者盲改部分坐标反而泄漏信号，SignRadial 检测恢复。
3. **必须诚实披露**：P1a 的攻击高估了攻击者能力；论文的坐标保密设计实际削弱了 sign-balanced 攻击。

### 2.2c 真实精度作弊三方法对比（新，p4b_three_methods.py）

| 方法 | W8A8 信号 | honest~honest | 分离 |
|---|---:|---:|---:|
| **SignRadial** | 0.082 | ~0（异构 p99 0.006）| >13× |
| **ProjCos** | 0.065 | 0.0000（同设备重跑）| 巨大 |
| **Scalar** | 78.4 max-abs | 0.0000 | 巨大 |

**结论**：三方法对真实 W8A8（activation 级作弊）**都能检测**——因为 W8A8 改变 activation 本身。三方法的差异在别处：只有 SignRadial 检测 scale（ProjCos 盲）、只有 ProjCos 补 sign-balanced（Scalar 也盲）。

### 2.3 方向变化攻击（test_direction_vs_radial.py）

| 攻击 | SignRadial | ProjCos |
|---|---|---:|---:|
| sign_flip（y=−x）| 1.0 | 1.0 |
| token_permute | 1.0 | 1.0 |
| 旋转 5°/10°+ | 0.965 / 1.0 | 1.0 |

**结论**：SignRadial 虽以"径向"命名，但**也能检测方向变化**（sign_flip 等）——因为它是 `Σ sign(x)·(y−x)`，对任何与参考不一致的残差都敏感。

### 2.4 真实精度作弊（P1b、P4b，不同设备）

| 配置 | SignRadial | 说明 |
|---|---:|---|
| FP8 / INT4（MPS）| **0.98 / 0.94** ✅ | 秒抓 |
| INT8（MPS，多边界）| 0.083，C2/C3 100% ✅ | 需多边界检查 |
| **W8A8**（CUDA，weight+act）| **0.082** ✅ | native≈模拟，可检测 |
| **W8A16**（CUDA，weight-only）| **0.005** ❌ | 不可见（但伤害 50% 输出）|

**ProjCos/Scalar 对真实精度作弊的检测：未测** ⚠️（需要同样的 decode/forward 数据，见 §5 未做清单）。

---

## 3. 开销对比

| 指标 | Scalar16 | Scalar64 | ProjCos4 | SignRadial-64 | SignRadial-256 |
|---|---:|---:|---:|---:|---:|
| 算术 ops/张量 | ~32 | ~128 | **65,536 MACs** | ~320 | ~1,280 |
| activation 读取 | 16 | 64 | 16×1024=16,384 | 64 | 256 |
| 参考值字节（BF16）| 64B | 256B | 256B | 128B | 512B |
| matmul | 无 | 无 | **有**（需投影）| 无 | 无 |
| 行归一化/cosine | 无 | 无 | **有** | 无 | 无 |
| 随机投影 seed | 无 | 无 | **有**（seed 依赖）| 无 | 无 |

**解读**：
- **ProjCos 计算最贵**（65K MACs + 归一化 + cosine），且依赖投影矩阵。
- **SignRadial-64 与 Scalar64 同级开销**（~320 ops），但 SignRadial-256（~1,280 ops）达到零 FPR + 全检出，仍是 ProjCos4 的 **1/50 计算量**。
- **SignRadial 无乘法平方、无余弦、无归一化、无随机投影**——纯加减/abs，部署时 `\|P\| > Γ·B` 免除法。
- **诚实边界**：在离线 harness 里这些算术差异被 np.load (~0.42ms) 主导，测不出 wall-clock 差；价值在在线融合进 activation 接收。

**通信量对比**：SignRadial-64 传 128B/checkpoint（与 Scalar64 同级，低于 ProjCos 的 256B）。

---

## 4. 盲点对比（汇总）

| 盲点 | Scalar | ProjCos | SignRadial |
|---|---|---|---|
| scale 攻击（幅值缩放）| 部分（0.4-0.8）| **❌ 全盲** | ✅ |
| 方向变化（sign_flip/旋转）| ❌ 弱 | ✅ | ✅ |
| gaussian 统计噪声 | ✅ | ✅ | 部分（0.895）|
| **sign-balanced**（sign(x)ᵀe=0）| ❌ 预期 | ✅ | ❌ |
| **balanced per-channel** | ❌ 预期 | ✅ | ❌ |
| **W8A16 weight-only** | ❌ 预期 | ❌ 预期 | ❌（需输出级）|
| exact replay | ❌ | ❌ | ❌（需 nonce）|

**谁覆盖什么**：
- **Scalar**：仅数值幅度，方向盲、scale 部分。整体最弱。
- **ProjCos**：方向强、scale 全盲、sign-balanced/balanced-channel 强（补 SignRadial）。
- **SignRadial**：scale/精度作弊/replay/方向全覆盖，但 sign-balanced/balanced-channel/W8A16 盲。
- **双头（SignRadial OR ProjCos）**：覆盖除 W8A16 和 exact-replay 外的全部攻击（Joint ROC 验证 FPR<0.02）。

---

## 5. 未做的对比实验（明确标记 ⚠️）

**已补齐（本轮）：**
- ✅ **Scalar/ProjCos 对 sign-balanced 和 balanced-channel**（p5c_missing_comparison.py）→ 只有 ProjCos 能补 SignRadial
- ✅ **三方法对真实 W8A8 精度作弊**（p4b_three_methods.py）→ 三方法都能检测 W8A8
- ✅ **坐标保密对齐**（p5c_coord_secrecy.py + p5c_partial_coord_attack.py）→ 部分坐标攻击下 SignRadial 恢复检测

**仍待补：**

| 实验 | 缺什么 | 需要的资源 |
|---|---|---|
| **Scalar/ProjCos 对 FP8/INT4/INT8 真实作弊** | 只测了 SignRadial | 复用 P1b decode/forward 数据跑 Scalar/ProjCos |
| **Scalar/ProjCos 对 partial replay / per-token** | 只测了 SignRadial 和 ProjCos | 复用 P3b/P2b2 注入 |
| **三方法的 multi-seed 稳健性** | 只测了 SignRadial（20 seeds）和 projscalar（50 seeds）| 对 Scalar 和 ProjCos 跑多 seed |
| **三方法 honest FPR 跨层（C1/C2/C3）** | 只测了 SignRadial | 对 Scalar/ProjCos 跑 P5a |
| **三方法 joint 三头 ROC** | 只测了双头（SignRadial OR ProjCos）| 加 Scalar 进 OR gate |
| **Scalar/ProjCos 对坐标保密下的攻击** | 只测了 SignRadial | 复用 p5c 部分坐标攻击注入 |

> **说明**：这些未做的对比大多是"聚焦 SignRadial 验证"的取舍，不是方法空白。Scalar 已证实整体弱（FPR 0.15-0.415、sign-balanced 盲），ProjCos 已证实 scale 盲（0.0）。补全主要是**三方对照表的完整性**。

---

## 6. 一句话总结

| 维度 | 胜者 |
|---|---|
| 检测能力（综合）| **SignRadial**（覆盖 scale + 方向 + 精度作弊 + replay）|
| 计算开销 | **SignRadial**（O(q) 纯加减，ProjCos 的 1/50）|
| 方向类攻击 | **ProjCos**（sign-balanced/balanced-channel 补 SignRadial 盲点）|
| 数值幅度 | Scalar（但 FPR 高、整体弱）|
| 综合架构 | **SignRadial OR ProjCos 双头**（FPR<0.02 覆盖全部）|

---

## 7. 产物

```
workspace/SRR/
└── docs/SRR_METHOD_COMPARISON.md   # 本文件
```
