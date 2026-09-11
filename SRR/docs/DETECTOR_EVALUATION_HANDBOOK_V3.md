# TSTC 检测器公平评估实验手册（v3，按评审 20 条严格化重写）

> 版本：v3.0（2026-08-08）
> 状态：**新手册。旧实验结果全部作废**（v1 grid-search 阈值、v2 统一协议版本均不再引用为结论，仅作方法缺陷记录）
> 依据：评审对 fixed-FPR 比较的 20 条意见（检测对象冻结、组件冻结、三份数据、TPR@FPR+CI、攻击族 sweep、自适应攻击、seed 控制、prefill/decode 分离、per-layer、downstream damage 等）
> 数据来源：`reproduction/VeriEdge/workspace/sanity_20260728_m4_m4_rtx3090/captures/`（A/B）+ `sanity_20260727/captures/`（B/D）
> 目标 venue：AccountEdge（NDSS 2027），P0-E2 TSTC 对手评估

---

## 0. 执行摘要

本手册按评审 20 条意见重写 TSTC 检测器评估。核心变更：

1. **冻结检测对象**：`D(H_A, H_attack)`，所有攻击从 `H_B` 构造（评审 1）。
2. **冻结两个 component**：ProjCos4 和 SignRadial 的参数在 pilot 上定死，主实验不再调（评审 2）。
3. **OR-style fusion**：benign percentile 归一化 + `max(u_P, u_R)` + 在独立 calibration 上校准联合阈值（评审 3）。
4. **三份数据**：Pilot / Calibration(C1,C2) / Test，按 prompt 划分（评审 4）。
5. **主指标 TPR@1% FPR** + 0.1%/5% + AUROC + partial AUROC，全部带 Wilson/Clopper-Pearson 95% CI（评审 5/6/7）。
6. **攻击族 strength sweep**：Gaussian RMS 归一化、scale 连续、replay 分级、structural、sparse、precision downgrade（评审 9-14）。
7. **两级攻击者**：oblivious + white-box（含 null-space / cancellation / joint evasion），验证 fresh secret challenge 的价值（评审 15）。
8. **K=20 detector seeds + 三套独立 seed**（评审 16/17）。
9. **prefill/decode 分开报 + per-layer**（评审 18/19）。
10. **每个攻击记录 downstream damage**（评审 20）。

**诚实标注的约束**：现有数据仅 40 calib + 200 eval/stack，**远低于**评审建议的 N≥10,000；且只有 prefill（T=16）无 decode。本手册把这两项作为"样本量升级"和"decode 数据补采"列入前置任务，同时说明在小样本下哪些结论可信、哪些不可信。

---

## 1. 检测对象定义（评审 1）

**冻结**：verifier 持有参考 `H_A`；诚实候选设备实际输出 `H_B`。由于 GPU/kernel/精度实现差异，天然存在 `H_B = H_A + η_benign`（异构漂移）。

**所有攻击必须从 `H_B` 构造**：
```
H_attack = A(H_B)
detector 始终比较 D(H_A, H_attack)
```
例如：`scale: H_attack = 1.1·H_B`。**禁止** `H_attack = 1.1·H_A`（那会删除正常的 A/B heterogeneity，产生 ProjCos(scale) AUROC=0 的人为现象）。

**为什么**：v2 已证实——attack 若从 `H_A` 构造或 ref 取自身，会让 attack 样本缺失 honest A/B nuisance，使 AUROC 虚高/虚低。统一 `D(H_A, A(H_B))` 是唯一公平基准。

---

## 2. Component 冻结（评审 2）

主实验开始前，在 **pilot set** 上定死以下参数，**主实验期间不再修改**：

### 2.1 ProjCos4（记 `S_P(H_A, H_B)`）

| 参数 | 冻结值 | 说明 |
|---|---|---|
| sampled token 数量 | 16 | 固定 T=16 |
| projection dimension | k=4 | 主实验用 4（评审指定）；ProjCos8/16 另作灵敏度报告，不作为主指标 |
| projection matrix | `R_ij ~ N(0, 1/k)` | fresh random R，每 request 独立 |
| aggregation | mean over tokens | `S_P = mean_t(1 - cos(proj_t(H_A), proj_t(H_B)))` |
| anomaly score 公式 | 见上 | 主实验用此 |

### 2.2 SignRadial（记 `S_R(H_A, H_B)`）

| 参数 | 冻结值 | 说明 |
|---|---|---|
| sampled coordinates | q=64 | 平坦坐标，无放回 |
| sampling strategy | 固定 seed 派生（对齐 frozen 基线） | 非秘密抽样变体单独报告 |
| score | `S_R = |Σ_{i∈Ω} sign(x_i)(y_i-x_i)| / (Σ_{i∈Ω}|x_i| + ε)` | ε=1e-12 |
| 阈值方式 | 见 §4 | calibration 分布分位数 |

> **q、token 数、aggregation、阈值方式一旦主实验开始不再改。** pilot 数据之后永不进入 main test（评审 4）。

---

## 3. Fusion：Benign percentile + OR-style（评审 3）

**不采用**：
- ❌ `S = S_P + λ·S_R`（尺度不同，λ 易人工调）
- ❌ learned fusion（用攻击数据训练，易 overfit 已知攻击，违背未知攻击检测目标）

**采用**：benign percentile normalization + OR-style fusion。

1. 在 benign calibration set C1 上得到两个经验分布 `F_P, F_R`。
2. 对测试样本：`u_P = F_P(S_P)`, `u_R = F_R(S_R)`，都映射到 [0,1]（越接近 1 越异常）。
3. 组合：`S_Combo = max(u_P, u_R)`——ProjCos 发现 angular、SignRadial 发现 radial，任一异常即触发。
4. **不直接设 0.99**：在**另一份 benign calibration set C2** 上测 `S_Combo` 的联合分布，取 `τ_Combo = Q_{1-α}(S_Combo^benign)`。
5. 最终：`S_Combo > τ_Combo ⇒ attack`。

**优势**：不需要 ProjCos 与 SignRadial 独立假设；组合 detector 的 FPR 是实际校准出来的（不是假设）。

---

## 4. 数据划分（评审 4/8）—— 三份，按 prompt 划分

| 份 | 用途 | 大小（当前可得 / 目标） |
|---|---|---|
| **Pilot** | 选 q、aggregation、攻击强度扫描范围、检查代码 | 10-15%（约 30-45 prompts）|
| **Calibration** | 只含 honest 执行，再分两份：<br>C1：估计 F_P, F_R（per-layer，见 §11）<br>C2：确定 Combo threshold τ_Combo | **目标 ≥10,000**（当前 40）|
| **Test** | 完全 untouched：honest test + 所有攻击 test | **目标 ≥10,000 honest**（当前 200）|

**铁律**：
- **同一 prompt 的 honest/gaussian/scale/replay/layer_skip 必须全部属于同一个 split**——按 prompt/request 划分，**不按 token 随机划分**（否则信息泄漏）。
- test 结果出来后，**不得再修改任何 detector 参数**。
- pilot 数据**永不进入** main test。

**样本量诚实标注**（评审 8）：当前 40/200 远低于建议的 10,000。40 条 calib 的 Q_{0.999} 阈值估计极不稳。**本手册将样本量升级列为前置任务**（见 §14），当前小样本结果仅作方向性证据，论文正式表需补采。

---

## 5. 指标与统计（评审 5/6/7）

### 5.1 主指标

| 指标 | 定义 |
|---|---|
| **TPR@1% FPR** | 主指标（真实系统无法接受高 FPR）|
| TPR@0.1% FPR, TPR@5% FPR | 同时报告 |
| AUROC | secondary |
| partial AUROC (FPR≤1% 区域) | secondary |
| attack score distribution | secondary（可视化）|

### 5.2 FPR 必须从独立 honest test 重测（评审 6）

calibration 冻结阈值后，在**独立 honest test** 上测：
```
FPR_observed = #{honest detected as attack} / N_honest_test
```
报告：`nominal FPR = 1%`、`observed test FPR = X%`、`95% CI = [...]`。**不写 "FPR=1%"**。

### 5.3 禁止无 CI 的 0.000 / 1.000（评审 7）

- 经验 rule of three：`p_upper ≈ 3/N`。`0/1000 ⇒ FPR < 0.3% (95%)`；`0/10000 ⇒ < 0.03%`。
- **所有 TPR/FPR 报告 Wilson 或 Clopper-Pearson 95% CI**。

---

## 6. 攻击族定义（评审 9-14）—— 全部从 H_B 构造，全部 strength sweep

> 每类攻击都做 strength sweep（评审 9 的"避免偶然性"）。Gaussian 永不只用一个大 σ。

### 6.1 Precision downgrade（核心攻击，评审 9）—— 主实验用真实执行

诚实声明精度（如 BF16）→ 降级到 {FP8, INT8, INT4}：
- **真实低精度执行 = 主实验**：用 RTX3090 `torch._int_mm`（W8A8 真实 int8 kernel，已有 `p4b_native_w8a8.py` 验证）。
- partial downgrade：25%/50%/75%/100% 的 block/layer 用低精度。
- 若硬件不支持真实 INT4：**simulated quantization = supplementary stress test**，明确标注非主证据。

### 6.2 Gaussian（RMS 归一化强度，评审 11）

```
H_attack = H_B + λ · RMS(H_B) · ε,  ε ~ N(0,1)
λ ∈ {0.001, 0.003, 0.01, 0.03, 0.1}
```
画 **TPR vs λ**，不报单个 "Gaussian=0.99"。

### 6.3 Scale（连续 sweep，评审 12）

```
H_attack = α · H_B
α ∈ {0.90, 0.95, 0.98, 0.99, 1.01, 1.02, 1.05, 1.10}
```
理论预期：ProjCos4 `S_P(αH_B) ≈ S_P(H_B)`（TPR≈FPR）；SignRadial 产生 `|α-1|` 级 coherent radial signal（TPR 随 |α-1| 单调上升）。**画 TPR vs |α-1|**。

### 6.4 Replay 分级（评审 10）

| 级别 | 定义 |
|---|---|
| Wrong-prompt replay | `H_B^(j) → H_B^(i)`，shape 一致、长度尽量匹配 |
| Previous-request replay | 重放上一请求 |
| Previous-step replay | decode 阶段 `H_t ← H_{t-1}`（需 decode 数据）|
| Same-prefix replay | 共享长前缀的两个请求 |
| **Partial replay** | 25%/50%/75%/100% token 被 stale activation 替换 |

画 detection boundary（TPR vs replay coverage）。

### 6.5 Structural corruption（评审 13）

- **Layer skip**：真正跳过 transformer block（`H_{ℓ+1}^attack = H_ℓ`），不人工随机 tensor。
- **Wrong layer**：`H_ℓ ← H_{ℓ-1}` 或 `H_{ℓ+1}`（shape 兼容时）。
- **Activation clipping**：`H_attack = clip(H_B, -c, c)`，扫描 clipping percentile。

### 6.6 Sparse corruption（评审 14）

- **Token sparse**：只攻击 `ρ_token ∈ {1%, 5%, 10%, 25%}` token。
- **Coordinate sparse**：随机/高敏感 coordinate 中攻击 `ρ_coord ∈ {0.1%, 1%, 5%, 10%}`。
- **直接展示 TPR(ρ)**——不隐藏失败，这回答"只抽 16 token，攻击 1% token 怎么办"。

---

## 7. 自适应攻击（评审 15）—— 安全论文与异常检测论文的区别

### 7.1 Threat A：oblivious attacker（主要 security setting）

知道算法形式，但**不知道当前 sampled token、不知道 fresh R**；在 verifier 生成随机 challenge **前**必须固定 `H_attack`。

### 7.2 Threat B：white-box attacker

知道 ProjCos 的 R、SR 抽样、reference/detector 细节。测试：
- **ProjCos null-space attack**：找 `Δ` 使 `R·Δ = 0`（projection 盲点）。
- **SR cancellation attack**：找 `sign(x)ᵀΔ = 0`（SignRadial 盲点）。
- **Joint evasion**：找 `Δ` 同时满足 `S_P(H_A, H_B+Δ) ≤ τ_P` 和 `S_R(H_A, H_B+Δ) ≤ τ_R`，且 `||Δ||_F / ||H_B||_F ≥ δ`。

**关键演示**：fixed/public challenge 可被 detector-aware attacker 绕过 → 攻击者先固定 Δ，verifier 再重新随机采样 R 与 coordinate → 若 TPR 显著恢复，即 **fresh secret challenge 设计的真正安全价值**。

---

## 8. 随机性控制（评审 16/17）

- **K=20 套独立 detector master seeds**。每套 seed 完整跑：calibration → 固定阈值 → honest test → 所有攻击 → TPR/FPR。
- 报告 mean/median TPR + 95% CI 或 mean±std。
- **20 seed ≠ 20 倍独立攻击样本**。CI 以 **request/prompt 为 cluster 做 bootstrap**，不把同一 activation 上 20 个投影当 20 个独立点。
- **三套独立 seed**（评审 17）：
  - `seed_data`（prompt 划分）
  - `seed_attack`（攻击噪声）
  - `seed_detector`（token sampling + projection R）
  - **禁止** `seed=42` 复用同一 seed。

---

## 9. Prefill 与 Decode 分开（评审 18）

- **Prefill**：`H ∈ R^{T×d}`，T=16，天然可抽 16 token。
- **Decode**：单步 `H_t ∈ R^{1×d}`，不存在"当前 step 选 16 token"。定义检测窗口 `W=16` 个连续 decode steps `{H_{t-15}, ..., H_t}`，在 window 上做 ProjCos4/SR。
- **分开报告 Prefill TPR/FPR 与 Decode TPR/FPR**，不混算一个 ROC。

**诚实标注**：当前数据**只有 prefill（T=16）**，无 decode 捕获。decode 部分列为前置任务（§14），在补采前不可报告 decode 结论。

---

## 10. Per-stage / per-layer calibration（评审 19）

- Activation statistics 随 layer 明显变化 → calibration 至少 per-stage/per-layer：`F_{P,ℓ}, F_{R,ℓ}`。
- 报告：early / middle / late layer、macro-average、**worst-layer TPR**。
- 只报混合平均会掩盖某些 boundary 的盲点——**worst-stage 对安全系统更重要**。

---

## 11. 攻击必须证明"真的有害"（评审 20）

每个攻击样本同时记录：
- **Activation distortion**：`D_H = ||H_attack - H_B||_F / ||H_B||_F`
- **Downstream logits difference**：`D_KL = D_KL(p_honest || p_attack)`
- **Next-token flip**：`1[argmax p_honest ≠ argmax p_attack]`
- **任务层面质量下降**（若有 ground truth）

**画 TPR vs downstream damage**——比 TPR vs noise magnitude 更有安全意义。真正要证明：**对足以显著破坏下游推理质量的攻击，组合 detector 有高检测率**；而不是"所有数值非零的 perturbation 都能检测"。

---

## 12. 执行流程（主实验）

```
1. Pilot（约 30-45 prompts）
   - 选 q、aggregation、Gaussian 强度扫描范围、检查代码正确性
   - 输出：冻结的 component 参数（§2），此数据永不进 main test
2. Calibration（C1 + C2）
   - C1：估计 F_{P,ℓ}, F_{R,ℓ}（per-layer）
   - C2：测 S_Combo 联合分布，定 τ_Combo = Q_{1-α}(S_Combo^benign)
   - 冻结：τ_P, τ_R, τ_Combo, 所有参数
3. Test（完全 untouched）
   - honest test → FPR_observed + CI
   - 每类攻击 × 每个 strength → TPR@FPR + CI
   - 记录 downstream damage（§11）
   - 自适应攻击（§7）单独跑
4. 汇总
   - TPR@1%FPR 主表（带 CI）
   - TPR vs λ（gaussian）、TPR vs |α-1|（scale）、TPR vs coverage（replay/sparse）
   - per-layer + prefill/decode 分离表
   - K=20 seeds 的 mean/median + bootstrap CI
```

---

## 13. 与旧实验的断裂声明

- v1（grid-search 阈值，FPR 0.02~0.415 不统一）→ **作废**。
- v2（fixed-FPR，但 attack 与 honest 基准不一致）→ **作废**，其教训（`D(H_A, A(H_B))` 必须统一）已融入 v3 §1。
- v3 的结论将以**本手册的协议 + 三份数据 + 统计 CI** 为准。

---

## 14. 前置任务与诚实约束

| 前置任务 | 当前状态 | 优先级 |
|---|---|---|
| **扩采 honest 数据到 N≥10,000** | 现 40/200 | P0（不满足则论文正式表样本量不足，只能作方向性证据）|
| **补采 decode 数据**（W=16 window） | 无 | P0（评审 18 无法满足）|
| **真实低精度执行路径**（RTX3090 _int_mm W8A8） | 已有 p4b_native_w8a8.py | P0（评审 9 主攻击）|
| **INT4 真实执行可行性** | 待确认；不可则 simulated 标注 | P1 |
| **per-layer capture**（每层 activation） | 现有仅 C1/C2/C3 三层 | P1（评审 19 需 per-layer）|
| **K=20 seeds 完整重跑** | 待建 | P1 |

**小样本下的可信度声明**：当前 40 calib + 200 eval 不足以支撑"TPR@1%FPR"的统计稳健性（40 条里 1% 即 0.4 条，Q_{0.99} 实为第 40 条最大值）。本手册产出为协议与流程；**论文正式数字必须等扩采完成**。

---

## 15. 复现与工具

- 现有脚本（待按本手册改造）：`run_fixed_fpr_comparison.py`（v2，作废但可复用 score 函数）、`radial.py`（sign_radial）、`srr.py`（采样）、`attacks.py`（攻击）、`p4b_native_w8a8.py`（真实精度）。
- 数据：`reproduction/VeriEdge/workspace/sanity_20260728_m4_m4_rtx3090/captures/`（A/B）、`sanity_20260727/captures/`（B/D）。
- GPU：RTX3090（24GB，_int_mm）、RTX6000D（85GB）。

---

## 16. 一句话总结

**v3 冻结 `D(H_A, A(H_B))` 检测协议、冻结 ProjCos4+SignRadial 参数、用 benign percentile OR-fusion + 独立校准阈值、按 prompt 三份划分、TPR@FPR 带 CI 为主指标、攻击族全 sweep + 真实精度 + 自适应两级攻击者、per-layer 与 prefill/decode 分离、攻击记录 downstream damage；旧结果全部作废，样本量与 decode 数据列为 P0 前置任务。**
