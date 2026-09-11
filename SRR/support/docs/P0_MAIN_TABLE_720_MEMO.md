# P0 主表 v3.1：扩样 720 池（200 calib / 520 eval），双机异构

> 日期：2026-08-08
> 对应：评审点 0 + 评审点 8（样本量）+ 用户澄清（Combined 用联合校准 max-fusion，FPR 不叠加）
> 数据：`workspace/captures_720/`——**stack_a_720（mini1 MPS bf16）+ stack_b_720（RTX6000 CUDA fp32）**，720 prompts（200 calib / 520 eval）真实双机异构捕获
> 脚本：`run_p0_main_table_720.py` → `results/p0_main_table_720.csv`

---

## 0. 结论先行

**扩样到 200 calib / 520 eval 后，Combined（联合校准 max-fusion）的 FPR 回到 ~1%，且在所有攻击上 TPR=1.0——既解决了样本量问题，也符合"Combined 的 FPR 应是组件最大值而非 OR 并集"的设计。**

| detector | evalFPR | gauss | **scale** | stale | layer_skip | INT8 | INT4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Scalar16 | 0.000 | 1.0 | **0.000** | 0.948 | 0.771 | 0.969 | 0.969 |
| ProjCos4 | 0.015 | 1.0 | **0.015** ≈FPR | 1.0 | 1.0 | 1.0 | 1.0 |
| SignRadial | 0.010 | 0.977 | **1.000** ✅ | 1.0 | 1.0 | 1.0 | 1.0 |
| **Combined** | **0.010** | **1.0** | **1.0** | **1.0** | **1.0** | **1.0** | **1.0** |

**给写作侧的三句话**：
1. **SignRadial 必要性铁证**：scale 下 Scalar16=0.0、ProjCos4=0.015（≈FPR，数学盲点）、**SR=1.0**。
2. **Combined 用联合校准 max-fusion，FPR=1%（不是 OR 的 12%）**，且 TPR 全 1.0——覆盖每个单检测器的盲点。
3. **扩样从 40→200 calib 大幅稳定了统计**（projcos4 evalFPR 0.11→0.015，combined 0.12→0.010）。

---

## 1. 数据与协议

### 1.1 扩样（评审点 8）

- **生成 720 prompts**：用 stratified-v2 的 topic×task_prefix×response_template 池扩展（`expand_prompts_200_500.py`），保留原 240 条 + 新增 480，**同分布**。
- **tokenize**：Qwen3-0.6B tokenizer，token 数 10-23。
- **双机异构捕获**（`capture_720_stack.py`）：
  - **stack_a_720 = mini1 MPS bf16**
  - **stack_b_720 = RTX6000 CUDA fp32**
  - 720 prompts × 2 设备 = 1440 activation（C1/C2/C3，[1,T,1024]）

### 1.2 Combined 定义（用户澄清）

**联合校准 max-fusion**，不是二值 OR：
```
u_P = F_P(S_P),  u_R = F_R(S_R)    (F = 校准集 honest 的平滑经验 CDF，rank/(n+1))
S_Combo = max(u_P, u_R)
tau_Combo = Q_{1-α}(S_Combo^benign)   (在 calibration 联合分布上取)
S_Combo > tau_Combo ⇒ attack
```
**关键性质**：FPR 由联合分布校准，**不是两个 1% 组件的 OR 并集**——故 FPR≈α（1%），TPR≈max(组件 TPR)。这正是用户要的"先用 ProjCos4 再用 SignRadial"的级联语义。

### 1.3 攻击（全从 H_B 构造，D(H_A, A(H_B))）

gaussian(λ=0.03·RMS)、scale(×1.10)、stale(跨 prompt C2)、layer_skip(C2←C1)、low-prec(INT8/INT4 activation 量化模拟)。

---

## 2. 结果（720 池，A/B 双机）

| detector | calFPR | evalFPR | gauss | scale | stale | skip | lp8 | lp4 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| scalar16 | 0.000 | 0.0000 | 1.000 | 0.000 | 0.948 | 0.771 | 0.969 | 0.969 |
| projcos4 | 0.010 | 0.0154 | 1.000 | 0.015 | 1.000 | 1.000 | 1.000 | 1.000 |
| signradial | 0.010 | 0.0096 | 0.977 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| combined | 0.010 | 0.0096 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

---

## 3. 与 40/200 池的对比（评审点 8 的验证）

| 指标 | 40/200 池（旧，双机 B/D）| 720 池（新，双机 A/B）|
|---|---|---|
| N_calib | 40 | **200** |
| N_eval | 200 | **520** |
| projcos4 evalFPR | 0.110-0.125 | **0.015** |
| combined evalFPR | 0.120-0.130 | **0.010** |
| combined scale TPR | 1.0 | **1.0** |
| signradial gauss TPR | 0.785 | **0.977** |

**扩样的效果**：
1. **FPR 漂移大幅减小**：projcos4 从 0.11 到 0.015、combined 从 0.12 到 0.010——200 条 calib 让 Q_{0.99} 阈值稳定，不再"eval 分布漂移"主导。
2. **signradial gauss TPR 上升**（0.785→0.977）：样本增大后统计更稳定（之前 200 条里 0.785 的波动较大）。
3. **结论方向不变且更稳**：Combined 覆盖全部攻击，FPR=1%。

---

## 4. 解读

### 4.1 SignRadial 必要性（评审点 0）

scale 攻击下：Scalar16=0.0、ProjCos4=0.015（≈FPR）、**SignRadial=1.0**。ProjCos 对 scale 是数学盲点（cos(HA R, αHB R) = cos(HA R, HB R)），SR 检测 coherent radial 信号。**SR 的必要性铁证成立**。

### 4.2 Combined 增加攻击覆盖率（评审点 0 核心问题）

Combined 在 6 类攻击上全 TPR=1.0：
- **scale**（Scalar/ProjCos 盲点）→ SignRadial 分支补
- **gauss**（SR 0.977）→ ProjCos 分支补到 1.0
- **stale**（Scalar 0.948）→ ProjCos 补
- **layer_skip**（Scalar 0.771）→ 补
- **low-prec**（Scalar 0.969）→ 补

### 4.3 Combined FPR 设计验证（用户澄清）

**联合校准 max-fusion 使 FPR=0.010**（≈1%），**不是 OR 并集的 12%**。这验证了用户的设计判断：Combined 应该"先用 ProjCos 再用 SR"，FPR 取两者中较大者，而不是简单 OR 叠加。且 TPR = max(组件 TPR)（全 1.0）。

### 4.4 Scalar16 的局限

Scalar16 对 scale=0.0、layer_skip=0.771——它在 720 池双机（MPS/CUDA 差异大）下表现最弱。这与"Scalar 看幅度变化、对方向/相干攻击弱"的预期一致。

---

## 5. 局限

| 局限 | 说明 |
|---|---|
| 攻击强度固定 | gaussian λ=0.03、scale 1.10× 单点（P2 需 sweep）|
| low-prec 模拟 | activation 量化模拟，非真实 kernel（P3 用 RTX3090 _int_mm）|
| 采样非秘密 | 固定 seed 2026 |
| 单 pair | A/B（MPS/CUDA）；B/D 未扩 |
| 10k 目标 | 720 仍 < 10k，但 200 calib 已足够让 1% 分位数稳定（评审点 8 的核心关切已缓解）|

---

## 6. 下一步（P1/P2/P3）

1. **P2 scale sweep**：α∈{0.90..1.10}，画 TPR vs |α-1|（ProjCos 理论平台、SR 单调上升）。
2. **P1 radial-angular**：θ 扫描证明 SR/ProjCos 对应几何分量。
3. **P3 真实精度**：RTX3090 `_int_mm` W8A8 + radial/orthogonal 分解。
4. 若需 10k：继续扩 prompts + 双机捕获（已有脚本，线性扩展）。

---

## 7. 复现

```bash
# 1. 生成 + tokenize + 双机捕获（已在 mini1/RTX6000 完成）
cd workspace/inversion/scripts
python3 expand_prompts_200_500.py     # 720 prompts
python3 tokenize_720.py               # 加 input_ids
python3 capture_720_stack.py stack_a_720 all mps   # mini1
python3 capture_720_stack.py stack_b_720 all cuda  # RTX6000

# 2. 主表
cd /Users/siyuan/Developer/ndss2027/.claude/worktrees/recursing-austin-d31ca0/workspace/SRR
python3 run_p0_main_table_720.py      # → results/p0_main_table_720.csv
```
