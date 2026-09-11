# SRR-64 快速裁决实验手册

**目的**：在写任何新代码、跑任何新实验之前，先快速判断 **SRR（Sampled Relative Residual Energy）** 是否真的比现有方法（scalar16 / projcos4 / projscalar1_abs）更有效。本手册只做**一件事**：在完全复用现有真实 capture 的前提下，产出一张可以裁决"SRR 是否值得投入"的表。

> **本手册不是最终论文实验**。它是一次**快速可行性验证（go/no-go）**。若 SRR 通过，再决定是否做正式实验并进入论文。

---

## 1. 背景与动机

### 1.1 现有方法的两个盲点（你的观察）

- **Scalar16** 只比较**数值幅度**（`max |V_cand - V_ref|`），对**方向变化**（sign flip、旋转、subspace shift）不敏感。
- **ProjCos4** 只比较**方向**（token-wise cosine gap，行归一化后比较），对**尺度变化**（如 `1.05x` 整体缩放、scale perturbation）几乎完全盲——实测 scale TPR 仅 **0.0107**（A/B 对，见论文 §5.6 / Table 6）。

这两者各守一个维度，但都丢掉了另一个。SRR 想用一个轻量指标**同时捕获方向和尺度**。

### 1.2 SRR 的数学定义

对 checkpoint 激活张量 `H ∈ R^{T×D}`（你们的 prefill 激活是 `[1, 16, 1024]`），秘密抽取 `q` 个坐标构成集合 `S`。对每个坐标 `i ∈ S`，记：

- `x_i = V_ref,i`（参考/诚实侧）
- `y_i = V_cand,i`（候选/被挑战侧）

定义：

```
E = Σ_{i∈S} (y_i - x_i)²          # residual energy
B = Σ_{i∈S} x_i²                   # reference energy

D_SRR = E / B
```

**判定**：`D_SRR > Γ` 即报警（Γ 为校准的容差）。在线实现不需要算除法，直接比较 `E > Γ·B`，只需要减法、乘法、累加。

**为什么它同时包含方向和尺度**：

令 `ρ = |y|/|x|`（相对尺度）、`c = cos(x,y)`（方向）。则：

```
D_SRR = 1 + ρ² - 2ρc
```

- **纯缩放** `y = αx` → `D_SRR = (α-1)²`。例如 `1.05x → 0.0025`、`1.20x → 0.04`。与坐标原始大小无关，只取决于缩放比例。
- **纯方向变化** `|y| = |x|` → `D_SRR = 2(1-c)`，等价于一个保留尺度信息的 cosine 检测器。
- **低精度替换** `y = x + δ` → `D_SRR = Σδ²/Σx²`，即抽样坐标上的**相对量化噪声能量**。低精度模型产生的稠密小误差会被累加（不像 max-scalar 那样被忽略）。

### 1.3 SRR 的成本优势

| | Scalar16 | **SRR-64** | ProjCos4 |
|---|---:|---:|---:|
| 算术/张量 | ~16 差值+比较 | **~320 标量操作**（64 减 + 128 乘 + 128 加） | 16×1024×4 = **65,536 MACs** + 行归一化 |
| activation 读取/张量 | 16 | **64** | 16×1024 = 16,384 |
| 参考值存储 | 64B (BF16) | **128B (BF16)** | 256B (BF16) |
| kernel 结构 | 纯 gather | 融合 reduce | matmul + 逐行归一 + cosine 归约 |

> **重要边界（诚实说明）**：在**离线 challenge harness** 里，projcos vs scalar16 的 wall-clock 差几乎全被 `np.load` + 文件 I/O + Python 调用开销吃掉（实测：load 一帧 ~0.42ms，算术仅 ~11µs），**算术优势在 harness 里测不出来**。SRR 的价值在**通信量 + 同时捕获方向/尺度**，不在 harness wall-clock。所以本实验**不**拿 harness wall-clock 当裁决指标，只当旁证。

### 1.4 为什么现在做这个

- NDSS 2027 fall 截稿 **2026-08-19**，今天 **2026-08-06**，只剩 13 天。
- 现有 capture（A/B、A/C、A/D、B/D 的真实异构 paired NPZ）**全部现成**，SRR 只在这些 NPZ 上算 64 个坐标的 E/B，**不需要任何新模型推理**。
- 现有白盒攻击实验慢的**主因是 harness 结构**（每个 attack × variant 都重新 `np.load` + 全量 chain），不是 SRR 本身。本实验用一个**单次 load + 内存缓存**的离线 runner 直接绕开这个瓶颈。

---

## 2. 目标与裁决问题

本实验回答**一个核心问题 + 两个支撑问题**：

**Q0（裁决）**：SRR 是否在真实异构 capture 上，同时满足——honest-hetero FPR 可比 projcos 低或接近、且 scale-perturbation TPR 显著高于 projcos（从 0.0107 → 目标 ≥0.9）？

- **GO**：SRR 在 ≥3/4 对上 FPR ≤ 0.10 且 scale TPR ≥ 0.9 → SRR 升级为 headline sketch，值得正式实验。
- **NO-GO**：SRR 只在部分对上成立 → 退为"盲点修复组件"，与 projcos 组成 hybrid（呼应论文"no single low-cost statistic"）。

**Q1（方向性攻击不倒退）**：SRR 在方向性攻击（stale-replay / wrong-prompt / layer-skip）上 TPR 是否保持 ≥ 0.9（projcos 在这些上是 1.0）？

**Q2（成本可核验）**：SRR 的算术操作数、activation 读取数、参考值字节，是否如 §1.3 所述（结构证据，不需 wall-clock）？

---

## 3. 数据源

**只用真实 paired capture，不用合成扰动**（红线2）。模型统一为 Qwen3-0.6B（SHA-256 `f47f71177f...974b`）。

### 3.1 可用 capture 清单（实测核对过）

| 对 | 来源目录 | calib | eval | 硬件构成 |
|---|---|---|---|---|
| **A/B** | `reproduction/VeriEdge/workspace/sanity_20260728_m4_m4_rtx3090/captures/stack_{a,b}_{calib,eval}` | 40 | 200 | **真实 M4**，C1=Apple M4/MPS (FP16+Metal-int8), C2=M4/BF16, C3=RTX3090/FP32；sanity 已复现原表 |
| **A/C** | 同 20260727 目录，`{aprime,cprime}_*` | 40 | 200 | M5 Pro C1 替代 + M4 C2 + RTX C3（projcos16 有 ±0.05 复现偏差，见 §3.2） |
| **A/D** | 同 20260727，`{aprime,dprime}_*` | 40 | 200 | 同上 |
| **B/D** | 同 20260727，`{bprime,dprime}_*` | 40 | 200 | 同上 |

### 3.2 capture 来源与两个注意点（诚实披露）

1. **A/B 用 20260728 真实 M4 capture**（已背书：12 个 projcos cell 逐 cell 复现，差 0.000）。这是最干净、最可信的数据源。
2. **A/C、A/D、B/D 用 20260727 的 M5-Pro-替代-C1 capture**（`prime` 后缀）。注意：M5 Pro 替代不是原 M4，projcos16 两个 cell 有 ±0.05 数值复现偏差。**本手册把它当"候选数据源"，但结果若进正式论文必须重新用真实 M4 采集 C/D，或在论文里明确标注 M5 替代**。
3. **E/F 对无 capture**（论文 projscalar1_abs 的 E/F 结果无法复现）。**本手册不纳入 E/F**，只做 A/B、A/C、A/D、B/D 四对。

### 3.3 capture 结构（实测确认）

每个 `.npz` 含三个 checkpoint：

```
prefill__C1: [1, token_count, 1024]  float32
prefill__C2: [1, token_count, 1024]  float32
prefill__C3: [1, token_count, 1024]  float32
```

token_count 实测为 **16**（所以 `T×D = 16×1024`）。

---

## 4. 方法

### 4.1 SRR 变体与分组 vote

**SRR 坐标抽样**（§4.3 详述）：每个 checkpoint 抽 `8 tokens × 8 channels = 64` 坐标，分 **4 组**（每 2 个 token 一组，每组 16 坐标）。

**4 组 3/4 vote 判定**：

```
对每组 g：E_g = Σ_{i∈S_g}(y_i - x_i)² ;  B_g = Σ_{i∈S_g} x_i²
          组异常 ⟺ E_g > Γ_g · B_g
最终报警 ⟺ 至少 3/4 组异常
```

**测试的变体**（保持轻量，首轮只测 3 个）：

| 变体 | 抽样坐标数 | 分组 | 阈值 |
|---|---|---|---|
| **SRR-32** | 32 | 4 组 × 8 | 3/4 vote |
| **SRR-64（推荐默认）** | 64 | 4 组 × 16 | 3/4 vote |
| **SRR-128** | 128 | 4 组 × 32 | 3/4 vote |

> 首轮不测更大的 q。若 SRR-64 通过裁决，SRR-128 作为增强点留到正式实验。

### 4.2 阈值校准协议（镜像现有，保证可比）

**每对 × 每变体独立校准**，只在 40 条 calibration 上选 Γ，在 200 条 held-out 上数 FPR/TPR。

**网格**（与现有 scalar 一致）：

- **tolerance mode**：`checkpoint-specific`（每 checkpoint 独立 Γ，主口径）和 `global-shared`（C1/C2/C3 共享同一 Γ，对照口径）
- **percentile**：99.0、99.5、99.9、99.95、99.99
- **tolerance scale**：0.5、1.0、1.5、2.0

**选择规则**（与现有完全一致）：

1. 优先选 calibration honest-hetero FPR ≤ 0.10 的候选；
2. 在可行候选中最大化 `TPR - FPR`；
3. **绝不**用 held-out 数据选操作点。

### 4.3 坐标抽样（secret 化）

**为什么必须 secret**：恶意节点必须在**不知道抽样位置**时先固定/发送 activation，否则任何抽样检测都可能被绕过。

**抽样方式**（每 checkpoint、每个新请求 seed 独立）：

```
seed = PRF(K, request_id || layer_id)
```

- **必须**包含当前最新 token；
- 另随机选 **7** 个 token；
- 每个 token 随机选 **1 个连续 8-channel 块**（共 8 块，连续块利于 GPU 合并加载）；
- 每 2 个 token 组成一个检测组，共 4 组。

### 4.4 攻击族（需新写 3 个注入函数）

现有代码只有 `gaussian / stale_replay / wrong_prompt`。本实验需要新增：

| 攻击族 | 定义 | 目的 |
|---|---|---|
| `scale_perturb` | 对 C2 checkpoint 做 `H → H * (1 + ε)`，ε ~ 0.05~0.20 | **projcos 盲点，SRR 主目标** |
| `layer_skip` | 用上一层的激活替换当前层（模拟跳过计算） | 方向性攻击，验证 SRR 不倒退 |
| `null_space` | 构造与投影矩阵正交的方向扰动 | **SRR 自己的边界**，诚实披露 |

> `layer_skip` 的实现需要**相邻层激活**。当前 capture 只有 C1/C2/C3 三个边界，没有逐层激活。**可用的替代**：用 `wrong_prompt` 的 donor（同一 checkpoint 换成另一 prompt 的激活）近似 layer-skip 的"内容替换"效应。若无法实现真正的 layer-skip，则只在手册中标注"近似替代"，不硬造。

**null_space 的诚实性**：SRR 的坐标投影本质是低维，必然存在 null space。应主动测出 SRR 对 null-space 攻击的 TPR，**预期会低**，这正是"诚实披露边界"的价值。

### 4.5 基线（必须在同一份 capture 上跑，保证可比）

| 基线 | 来源 |
|---|---|
| `scalar16` | 现有实现（复现）
| `projcos4` | 现有实现（复现）
| `projscalar1_abs` | 现有实现（复现）

> 基线用**现有 frozen 算法文件**（`frozen_snapshot/artifacts/thc/src/hash_chain.py`）跑，保证与论文一致。SRR 是**新增**，不算现有实现。

---

## 5. 裁决标准

**GO（继续投入）**：SRR-64 在 **≥3/4 对**上满足：

1. honest-hetero FPR ≤ 0.10（主口径 checkpoint-specific），**且**
2. `scale_perturb` TPR ≥ 0.9（对比 projcos 的 0.0107），**且**
3. 方向性攻击（stale/wrong_prompt/layer-skip-approx）TPR ≥ 0.9（不倒退），**且**
4. 成本证据（ops/reads/bytes）与 §1.3 一致（结构核验，非 wall-clock）。

**NO-GO（退回 hybrid）**：SRR 只在部分对上成立，或 scale 盲点没修好 → 退为"盲点修复组件"，与 projcos 组成 hybrid。

**NO-GO（数据问题）**：如果 capture 缺失（如 A/C、A/D、B/D 的 M5 替代）导致结果无法解释 → 先补 capture，不强行下结论。

---

## 6. 实现

### 6.1 离线 runner 设计（关键：单次 load + 缓存，绕开白盒慢的根因）

现有白盒攻击慢的根因是**每个 attack × variant 都重新 `np.load` + 全量 chain**。本 runner 必须：

1. **一次性**加载每对的 200 条 held-out NPZ 到内存（每个 prompt 的 3 个 checkpoint 缓存为 `np.ndarray`）；
2. 对每个 (prompt, checkpoint)，**只计算 SRR 需要的 64 坐标**的 E/B，不跑全量 `compute_hash_chain`；
3. 对每个攻击，**在缓存 tensor 上直接注入**，不改原始 capture；
4. 输出一张对照表：`pair × variant × 攻击族 → FPR/TPR/LocAcc`。

**计算量估算**：4 对 × 200 prompt × 3 checkpoint × 64 坐标 × ~320 ops ≈ **约 1.5M 次操作**，现代 CPU 毫秒级完成。**瓶颈只有文件加载**（4 对 × 200 × 122KB ≈ 100MB），一次性读完也只要几秒。**白盒攻击不再是慢点**。

### 6.2 新增文件

```
reproduction/VeriEdge/workspace/sanity_20260728_m4_m4_rtx3090/
├── run_srr_offline.py          # 主 runner：单次 load + SRR + 基线 + 攻击
├── srr.py                      # SRR 实现（E/B、分组 vote、secret 抽样）
├── attack_srr.py               # scale_perturb / layer-skip-approx / null_space 注入
├── results/srr_offline/        # 输出对照表
│   └── srr_vs_baseline.csv
└── notes/SRR_OFFLINE_SCOPE.md  # 一页 scope 记录（含"哪些是近似/缺失"）
```

> **不复制现有 harness**。这是一个独立的最小 runner，只依赖 `numpy` + 现有 capture 路径，不依赖 `torch`（避免加载模型）。

### 6.3 输出表结构

```
pair_id, variant, family, tolerance_mode, percentile, tolerance_scale,
calib_fpr, eval_fpr, eval_tpr_gaussian, eval_tpr_stale, eval_tpr_wrong_prompt,
eval_tpr_scale, eval_tpr_null_space, eval_locacc,
ops_per_tensor, reads_per_tensor, ref_bytes_per_ckpt
```

（SRR 的 scale/null-space TPR 用攻击注入测；projcos/scalar 的 scale TPR 用同一个 attack_srr.py 的 scale 注入测，保证公平可比。）

---

## 7. 执行顺序与验收

| 步骤 | 内容 | 验收 |
|---|---|---|
| 1 | 确认 4 对 capture 路径可读，跑一次 `validate_captures` | 每对 calib=40, eval=200 |
| 2 | 写 `srr.py`（E/B、分组、secret 抽样）+ 单测（已知输入） | 单测通过 |
| 3 | 写 `attack_srr.py`（3 个新攻击） | 注入后 tensor 形状不变 |
| 4 | 写 `run_srr_offline.py`（单次 load + 全表） | 4 对 × 5 变体 × 6 攻击族全出 |
| 5 | **先跑基线（scalar16/projcos4/projscalar1_abs）复现** | 基线与论文表 3 对齐（A/B 的 scalar16=0.15、projcos4=0.02） |
| 6 | 跑 SRR 变体 | 出对照表 |
| 7 | 按 §5 裁决 | GO / NO-GO 明确 |
| 8 | 写 scope note（含"哪些是近似/缺失"） | 记录可复现 |

**步骤 5 是最关键的 sanity check**：如果基线和论文表对不上，说明 runner 或数据有问题，SRR 结果不可信，必须先修对。

---

## 8. 风险与已知边界（诚实披露）

1. **A/C、A/D、B/D 用的是 M5-替代 capture**，非原 M4。projcos16 有 ±0.05 偏差。若 SRR 在这些对上表现好，可能部分归因于替代硬件，进正式论文需重采。
2. **E/F 对无 capture**，本实验不覆盖（论文的 multiseed/E-F 稳定性也无法复现）。
3. **`layer_skip` 无逐层激活**，用 `wrong_prompt` donor 近似。结果须标注"近似替代"。
4. **null_space 攻击**需要构造投影正交方向，SRR 预期 TPR 低——这是**诚实的边界**，不是失败。
5. **harness wall-clock 不用于裁决**（被 I/O 吃掉），只报算术/通信结构证据。
6. **小样本 FPR**：200 条 held-out 上 FPR 是离散计数（0.005 步长），低 FPR 波动大，必要时报 Wilson 区间。

---

## 9. 附：与论文/NDSS 的关系

如果 SRR 通过：
- **表 4 叙事升级**：从"scalar 不行、projcos 好、projscalar 是诊断"变成"**同一预算下 relative-residual-energy 同时覆盖方向和尺度，并修复 projcos 的 scale 盲点**"。
- **对 NDSS 特别有价值**：手册红线 4 要求诚实披露盲点，而"披露 + 用 SRR 修掉"比单纯披露更主动，是更漂亮的贡献。
- **只换 Φ 和 μ**：challenge 协议、digest 链、first-mismatch 定位完全不动——正是论文"only the sketch statistic changes"的设计原则。

**优先级**：这是快速验证实验（约 1-2 天），不阻塞 NDSS 主线的其他工作。replay 数字对账仍是更紧迫的地基问题，可与本实验并行。

---

## 10. 交付物

- `results/srr_offline/srr_vs_baseline.csv` —— 裁决用的主表
- `notes/SRR_OFFLINE_SCOPE.md` —— 一页 scope 记录
- 本文档 —— 实验手册

**裁决后**：GO → 正式实验手册 + 进论文；NO-GO → 记录结果，退回 hybrid 或放弃。
