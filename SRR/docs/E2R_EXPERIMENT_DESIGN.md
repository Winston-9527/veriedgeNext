# E2-R 实验设计：统一协议下的自适应对手 × 三检测器

> **状态**：设计稿（§3.2 坐标 seed 政策已按 mentor V0-2(a)/A1.3 框架解决；§10 剩 4 个决策点待拍板后冻结）
> **对应手册**：`docs/08.08继续推进手册.md` §2（唯一主实验，8/12 交付）
> **设计日期**：2026-08-09
> **基础设施**：已逐一核实（见 §2），无假设项

---

## 1. 目标与三问

在**统一 nominal 1% FPR 协议**、**720 真实异构池**上，量化 6 个自适应攻击族对 `SignRadial` / `ProjCos4` / `Combined` 的逃避能力，最终必须明确回答：

- **Q1**：tolerance-hugging 在 SignRadial 下还成立吗？（8/3 交付里它让原检测链整条归零 TPR 0/276）
- **Q2**：`joint_null` 能否同时躲过 SignRadial 与 ProjCos？（或：为什么构造不出来——给出约束交的维数）
- **Q3**：Combined 相对单检测器的净增益 ΔTPR（逐攻击族定量）。

成功判据遵循手册 §2.6：**三种结果都算有效，唯一失败是跑不出可复现数字**。所有构造方式写死在 manifest，`ρ` 全扫 6 档，两个威胁模型都跑。

---

## 2. 已核实的基础设施（全部实测/读码确认，非假设）

| 项 | 事实 | 来源 |
|---|---|---|
| 数据 | `workspace/captures_720/{stack_a,stack_b}_720/captures/*.npz`，各 720 个，键 `prefill__C1/C2/C3`，形状 `[1,T,1024]` fp32 | `ls` + npz keys 实测 |
| split | 200 calibration / 520 evaluation，`qwen_prompt_splits_stratified_v2_200_500.jsonl`（sha256 前缀 `5f1be1eed14bf297`） | 实测 |
| token 长 | min 10 / max 23 / median 14 | 实测 |
| 边界映射 | `_BOUNDARY_END_INDEX = {C1:7, C2:15, C3:27}`；C3=层27=**末层输出**，pre-final-norm | `qwen.py:25` |
| 层划分 | C1=层0–7、C2=层8–15、C3=层16–27 | `qwen.py:212-216` |
| 注入 harness | `QwenFull28Adapter._replay_torch(boundary, activation)` 从边界激活跑 `_BOUNDARY_END_INDEX[b]+1..27` → 捕获下游 C2/C3 + final_norm + lm_head logits | `qwen.py:1071-1132` |
| 危害方向 | `_output_gradient_torch(boundary, source)` 给 `∂(logit_competitor − logit_clean)/∂H` | `qwen.py:1134` |
| 检测协议 | §6.4：trace-max 单阈值 `τ_D = Q_{0.99}(calib honest)`；SR q=64、ProjCos k=4；Combined = ECDF-max 联合校准 | `run_p0_main_table_720.py` |
| 固定 seed | run_p0 对**所有 prompt 用同一 seed=2026** → 坐标/投影对全池相同 | `run_p0_main_table_720.py:37-38` |
| seed 保密现状 | **`node_sees_before_exec`**：seed 是公共常量（0/2026/9527），无 PRF 无密钥；A1.2 实证 72/72 复现 verifier 精确坐标。**当前系统 TM-2 才是现实模型** | `results/VERIFIER_SEED_SECRECY_MEMO.md` |
| mentor 已有对齐实验 | A1.3：KNOWN(seed 同)=0.0096≈FPR vs SECRET(seed≠)=0.2942，protective_gain≈+0.28（q=64/256 一致）；tol_hug q=64 增益≈0 | `VERIFIER_SEED_SECRECY_MEMO.md` §3 |

---

## 3. 检测协议（决策点 D1/D2）

### 3.1 数据与 split

- ref 束 `x` = `stack_a_720`（mini1 MPS bf16），cand 束 `y` = `stack_b_720`（RTX6000 CUDA fp32）或攻击束。
- calib 200 / eval 520 互斥，与 §6.4 完全一致，不另起一套。

### 3.2 坐标 seed 政策（已按 mentor 框架解决，非决策点）

**verifier 抽查坐标 seed 固定 = 2026**（与 §6.4 完全一致，诚实阈值口径可复用）。TM-1/TM-2 的差异**不是 verifier 的 seed 政策，而是攻击是否对齐到 verifier 的坐标**——这正是 mentor V0-2(a)/A1.3 已经用并验收的"坐标对齐"框架：

- **TM-2（seed 已知）**：攻击者知道 verifier 抽查坐标（当前实现 `node_sees_before_exec`，seed 是公共常量——**这是现实模型**）。攻击构造**精确对齐**到 2026 坐标/投影。
- **TM-1（seed 保密）**：攻击者不知道 2026，用**猜测 seed** 构造（对齐到错误坐标）。verifier 查 2026 坐标 → 错位。这是 commit-then-challenge 假设情形（修好实现后 TM-1 才成为现实）。
- **两者差值 = 坐标保密值**（mentor 原话：commit-then-challenge 的坐标保密到底值多少），A1.3 已给出 sign_balanced 方向性结果（+0.28），E2-R 把它推广到全 6 族 × 6 ρ。

**审计 A 拍板（2026-08-09）——P 公开，坐标保密只作用于 SR 通道**：投影矩阵 P 是**公共知识**（TSTC 需承诺后可公开复算，违背则承诺记录不可第三方核验；V0-2(a) 节点执行前见 seed→P 是 seed 确定性函数、藏不住；检测力必须来自"篡改几何 vs 诚实漂移"而非"对手不知一张矩阵"）。ProjCos 无坐标抽样（全 T 行投影），故坐标保密对 ProjCos 通道结构性无效。**TM-1/TM-2 的差异仅在 SignRadial 的抽查坐标 Ω**。由 `TM1b_knownP` 审计臂实证（P 公开 + Ω 猜测）：null_space 对 PC 精确盲（回到 TM-2 水平），坐标保密确实只作用 SR。

**TM-1 的多猜测稳健臂**：A1.3 的 caveat 是 SECRET TPR 依赖具体猜测 seed（seed=1→0.55、seed=2026→0.29）。E2-R 对 TM-1 用 **≥3 个猜测 seed**（如 2027、12345、777），报 mean/min/max TPR，主表用某个固定猜测（manifest 记录），稳健性在 memo 报告。**结论取方向与量级，不取单猜测精度**。

**阈值口径**：`τ_D`（trace-max）与 `Γ_{D,k}`（逐边界）都在 seed=2026 的 honest 分布上校准——与 §6.4 完全同口径，可直接核对。

### 3.3 D2 — 逐边界阈值 vs trace-max（**必须拍板**）

CSV 有 `boundary` 列 + `localization_acc`，必须逐边界打分；但 §6.4 检测用 trace-max 单阈值（evalFPR≈1%）。

**推荐（双层）**：
- **检测（决定 TPR/evasion/FPR）** = §6.4 trace-max：`detected_D ⟺ max_k score_{D,k} > τ_D`，`τ_D = Q_{0.99}(calib trace-max)`，evalFPR≈1%，与 §6.4 同口径。
- **定位（localization_acc）与 tol_hug 目标** = 逐边界阈值 `Γ_{D,k} = Q_{0.99}(calib 逐边界 score)`。
- 两条口径都写进 manifest；逐边界阈值 union FPR≈3% 的差异在 memo 明说。
- 理由：trace-max 保住"与 §6.4 同协议"字面成立；逐边界是定位与攻击校准的天然载体。

### 3.4 攻击注入后的 cand 束构造（忠实传播）

攻击在边界 k* 注入 `e`，则 cand 束 = **{上游边界: 诚实 b；k*: b+e；下游边界: 真实传播结果}**。下游 = 在 CUDA fp32 上 `_replay(k*, b+e)` 的捕获（`_replay_torch` 已捕获 C2/C3 下游）。这忠实模拟"下一个 shard 节点从被篡改激活继续算"的协议语义，且与诚实 stack_b 同设备同精度（确定性可复现）。

> 方法学要点：**null-space 类攻击只在注入边界成立，向下游传播后被非线性层破坏**（C1/C2 注入会在下游边界被 trace-max 捕获；C3=末层注入无下游边界可查）。因此 **C3 注入是逃避关键情形**，三个边界都要跑，解释按此分层。

### 3.5 强制 sanity check

1. `_replay(C1, b_C1)` 逐位复现捕获的 b_C2/b_C3（同设备 fp32 确定性）。
2. `run_from_input_ids(prompt)` 的 logits 与 `_replay` 一致。
3. 诚实束 trace-max evalFPR ≈ 1%（验证阈值口径没漂）。

---

## 4. 攻击族构造（数学定义，写死进 manifest）

记边界 k 上 ref `x=H_A^(k)`、诚实 cand `b=H_B^(k)`，形状 `[T,D]=[T,1024]`；残差 `r = cand − x`；诚实残差 `r0 = b − x`。
扰动量纲统一：**`‖e‖_F = ρ·‖b‖_F`，ρ ∈ {0.002, 0.005, 0.01, 0.02, 0.05, 0.10}**，攻击束 `cand = b + e`。

**共同白盒知识**：Φ、P、Γ_k、SR 公式+q=64、模型、tokenizer、诚实 ref x 与诚实 cand b（攻击者是执行节点，有 oracle 访问诚实执行）。

**危害方向 g**（§5 定义）：输出梯度方向，每个 (prompt, boundary) 预先计算一次。

### 4.1 构造采用"齐次零化"（Philosophy 2）

攻击只把**注入边界上的残差**投影进被躲避检测器的零空间（`r` 在该检测器下 ≈ 诚实水平，TPR→FPR 级），不补偿诚实漂移。理由：
- 诚实漂移本身就在阈值之下（阈值就是它的 Q_{0.99}），泄漏的诚实级信号不足以报警 → 统计盲。
- **ρ 作为自由旋钮**：齐次约束下 e 的量纲自由，可全扫 6 档（若补偿漂移，量纲被 honest-drift 钉死，ρ 扫不动）。
- 更强变体（精确零化 residual）在 memo 记作变体，不占主表。

### 4.2 符号

- `s_Ω`：`sign(x)` 在 verifier 抽查坐标 Ω 上的向量（Ω 外为 0），q=64。**Ω 由 seed=2026 派生（TM-2 已知）**。
- `P ∈ R^{D×4}`：ProjCos 投影（seed+911 派生，TM-2 已知）。
- `N = I − P(PᵀP)^{-1}Pᵀ`：每行投影到 `null(P)` 的算子。
- `Π_S(g) = g − Sᵀ(SSᵀ)^{-1}S g`：把 g 投影进约束子空间 S 的正交补投影（S 为约束行构成的矩阵）。

**TM-1 统一语义（对齐/错位框架，与 mentor A1.3 一致；审计 A 拍板后 P 公开）**：攻击者**知道 P**（投影矩阵公开），不知 2026 的 **SR 抽查坐标 Ω**，用**猜测 seed gs** 派生 `Ω̂` 并据此构造 sign 平衡；null-space 攻击直接用真实 P（无需猜测）。verifier 查真实 Ω（seed=2026）。`e` 落在错误 sign 零空间 → 真实坐标上留下 overlap residue → 被检出（残留随机游走）。符号：`Ω̂` = 猜测坐标集；P = 公开投影。审计臂 `TM1b_knownP` = P 用 verifier seed、Ω 用猜测 seed，用于实证"坐标保密只作用于 SR 通道"。

| family | 约束（目标检测器） | TM-2 构造（seed 已知，对齐 2026） | TM-1 构造（seed 保密，对齐猜测 seed） |
|---|---|---|---|
| `sign_balanced_sr` | 躲 SR：`s_Ωᵀ e = 0` | `e = Π_{s_Ω}(g)`，归一化到 ρ‖b‖。SR 分子精确清零，score 只剩诚实泄漏 → **盲** | `e = Π_{s_{Ω̂}}(g)`（对齐猜测坐标）。真实 Ω 上残留 = `s_Ωᵀe` 随机游走 → 小 ρ 盲、大 ρ 检出（**crossover 即坐标保密值**，A1.3 已见 +0.28） |
| `null_space_projcos` | 躲 ProjCos：`e[i]ᵀP = 0 ∀i` | `e[i] = N·g[i]`，归一化到 ρ‖b‖。逐行投影不变 → ProjCos score = 诚实级 → **盲** | **P 公开（审计 A）**：`e[i] = N·g[i]`（真实 P）→ 对 PC 精确盲（同 TM-2）。坐标保密对 PC 无效（无坐标抽样） |
| **`joint_null`** | 同时躲两个：`{e[i]ᵀP=0 ∀i} ∩ {s_Ωᵀe=0}` | 约束矩阵 `C ∈ R^{(T·4+1)×(T·D)}`（每行 4 条 P 约束 + 1 条 sign 约束），`e = g − Cᵀ(CCᵀ)^{-1}Cg`，归一化到 ρ‖b‖。**必须报 `rank(C)` 与 `dim null = T·D − rank`** | **P 公开**：C 用真实 P（PC 约束精确），sign 约束用猜测 Ω̂ → 对 PC 盲、SR 残留随机游走 |
| `tol_hug_sr` | 贴 SR 阈值：`score_SR(b+e) = (1−δ)Γ_{SR,k*}`，δ=0.05 | 方向 u=g；先 `e_raw=ρ‖b‖·u`；若 `score(b+e_raw) ≤ (1−δ)Γ` 则用 e_raw（天然低于阈值）；否则**对分查找 λ**：`score(b+λ·e_raw)=(1−δ)Γ`，交付 `e=λ·e_raw` | 用猜测坐标校准 λ；真实 Ω 下 score 偏离目标 → 可能超 Γ（检出）或低于目标。**回答"tolerance-hugging 能否盲校准"**（A1.3 稀疏版 q=64 增益≈0） |
| `tol_hug_projcos` | 贴 ProjCos 阈值 | 同上，目标 `Γ_{ProjCos,k*}`，score 对 λ 单调 → 对分可解 | 用猜测投影校准；真实 P 下可能超阈值 |
| `tol_hug_combined` | 贴联合阈值 | 目标 `Γ_{Combo,k*} = Q_{0.99}(max(u_P,u_R) 逐边界)`，对分 max(u_P,u_R) | 用猜测坐标/投影近似校准；真实口径下可能超阈值 |

> **TM-1 多猜测稳健臂**：TM-1 的残留依赖具体猜测 seed（A1.3：seed=1→0.55、seed=2026→0.29）。对 TM-1 用 ≥3 个猜测 seed（如 2027、12345、777），主表取固定一个（manifest 记录），mean/min/max 报在 memo——**结论取方向与量级，不取单猜测精度**。

> **joint_null 可构造性预判**：T·D 维（T≥10 → ≥10240），约束秩 = T·4+1 = 65（P 约束逐行独立 + sign 约束几乎必然独立），dim null ≈ 10240−65。**几何上必然可构造**，"构造不出来"的结果概率极低；真正的正面/反面结果在 **harmful_evasion_rate**（联合零空间里的扰动是否还有危害）。秩与维数照报，不许跳过。

### 4.3 归一化与数值

- 投影后 `e ← ρ·‖b‖_F · e/‖e‖_F`（齐次约束对缩放不变，合法）。
- `Π_{s_Ω}` 用 `e = g − (s_Ωᵀg/‖s_Ω‖²)s_Ω`；`N·g[i]` 用 `P(PᵀP)^{-1}`（4×4 可逆，a.s.）；joint 用 `Cᵀ(CCᵀ)^{-1}`（65×65 可逆，需在代码中断言 rank）。
- TM-1 的 score 校准用**猜测坐标/猜测投影**：攻击者在自己的 Ω̂/P̂ 上对分校准 λ，交付后由 verifier 在真实 Ω/P 上打分。

---

## 5. 危害方向 g 与危害代理（决策点 D3）

### 5.1 危害方向 g

**主用 = 输出梯度**：`g = ∂(logit_competitor − logit_clean)/∂H`（`_output_gradient_torch`，在诚实 b 处求值，已现成）。这是"每单位 L2 最伤输出"的方向：`argmax` 迁移的第一阶最优方向。
- 在零空间类攻击里 `e = ρ‖b‖·Π_S(g)/‖Π_S(g)‖` 是**约束下 L2 最优危害方向**（一阶）。
- 在 tol_hug 里 `e = λ·g` 是"探测器能容忍的最大危害方向"——正是 tolerance-hugging 的定义。
- **回退**：`--harm-dir random`（i.i.d. Gaussian）作稳健性对照，memo 报告两版差异。
- 成本：720×3 = 2160 次 backward（0.6B，CUDA）≈ 10–30 分钟，一次性，跨攻击族复用。

### 5.2 危害代理 harm_proxy（全流程一致，定义写死）

**主定义（连续）**：
```
harm_proxy(p) = ‖logits(replay(k*, b+e)) − logits(honest_B)‖₂ / ‖logits(honest_B)‖₂
```
其中 `honest_B` 由 `run_from_input_ids(prompt)`（CUDA fp32）给出，一次计算全池复用。

**诚实基线（逐边界）**：
```
honest_shift_k(p) = ‖logits(replay(k, H_A^k)) − logits(replay(k, H_B^k))‖₂ / ‖logits(replay(k, H_B^k))‖₂
h0_k = Q_{0.95}( honest_shift_k over calib )
```
**harmful(p) ⟺ harm_proxy(p) > h0_{k\*}** —— 即"扰动造成的输出偏离超过诚实设备异构本身在 95% 分位造成的偏离"。这就是 §2.6"material output divergence"的可操作定义，锚在诚实噪声地板而非任意常数。

**次要（辅助）**：argmax 迁移率 `P(argmax(L_att) ≠ argmax(L_honest))`，memo 里并列报告。

> 危险信号：若 h0 偏大（异构在输出级本身就大），harmful 率会系统性偏低 → 会显示"逃避的扰动大多无害"（bounded-arbitration 的正向解读）。memo 必须如实报告 h0 分布，不许调它凑结论。

---

## 6. 指标定义（每个 cell 全要）

每个 cell = (TM ∈ {TM1_seed_secret, TM2_seed_known} × family × ρ × boundary 注入)：

| 指标 | 定义 |
|---|---|
| `tpr_at_1fpr` | `P(detected_D)`，detected = trace-max > τ_D（§3.3） |
| `eval_fpr` | 诚实束 `P(detected_D)`（实测，用于验证阈值口径 + 盲点判据分母） |
| `evaded_rate` | `1 − tpr_at_1fpr` |
| `harmful_evasion_rate` | `P(未检出 ∧ harmful)`（§5.2） |
| `harm_proxy_mean` | `mean(harm_proxy(p))` |
| `localization_acc` | `P(首个超阈值边界 == k* | detected)`，首超边界按 C1→C2→C3 顺序取第一个 `score_k > Γ_{D,k}` |

**盲点三态（§2.4 写死判据）**：
- `blind` ⟺ `tpr_at_1fpr ≤ 2 × eval_fpr`
- `partial` ⟺ `(2×eval_fpr, 0.5]`
- `detected` ⟺ `> 0.5`

TPR/FPR 附 Wilson 95% CI（复用 harness 的 `wilson95`）。

---

## 7. 实验矩阵与成本预算

**全格**：6 family × 6 ρ × 2 TM × 3 注入边界 × 520 eval = 112,320 攻击实例。

- **构造 + 打分**：纯 numpy（captures），本地即可，分钟级。
- **梯度危害方向**：2160 backward，RTX6000，10–30 分钟，一次性。
- **注入 forward + logits**：`_replay(k*, b+e)` 每实例一次 tail（C3 注入仅 norm+head，C1 注入 20 层）。~112k 次 tail ≈ **20–40 分钟**（可优化：按条件批叠 520 进一个 batch 跑 tail）。
- **诚实基线**：`run_from_input_ids` × 720 + `honest_shift_k`（calib 200×3×2 replay）≈ 5 分钟。

合计 RTX6000 ≈ **1–1.5 小时**。预算内。

**输出矩阵**：`e2r_main_matrix.csv` 每行一个 (TM, family, ρ, boundary, detector)，3 detectors × 112,320/3 = 112,320 行。另有逐 prompt 明细 CSV 供复算审计。

---

## 8. 交付物结构（路径与字段写死，与手册 §2.5 一致）

输出目录 `<SRR>/results/e2r/`：

1. **`e2r_main_matrix.csv`** — 列：`threat_model, attack_family, rho, boundary, detector, n_eval, threshold_gamma, tpr_at_1fpr, eval_fpr, evaded_rate, harmful_evasion_rate, harm_proxy_mean, localization_acc`（`boundary`=注入边界；`threshold_gamma`=该检测器 trace-max τ_D；末尾追加 `tpr_ci_lo, tpr_ci_hi, rho_eff_delivered` 供审计）。
2. **`e2r_blindspot_table.md`** — 行=family×TM（12 行），列=3 detector，格=`TPR (状态)`，**ρ=0.01 固定档**（另注：强度谱见 sweep 图）。直接进论文。
3. **`e2r_strength_sweep.png`** — 6 面板（每 family），横轴 ρ 对数，纵轴 TPR；每 detector 一条曲线，TM-1 虚线 / TM-2 实线。
4. **`e2r_manifest.json`** — 必含：数据指纹（两 stack 文件数 + prompt 文件 sha + token 长统计）、split 定义、verifier seed=2026 与 TM-1 猜测 seed 列表（含主猜测）、**全部 Γ_{D,k} 与 τ_D 数值**、ρ 网格、δ=0.05、每 family×TM 构造参数与**代码 file:line**、harm proxy 精确定义 + h0 分布、脚本 git 版本/hash、设备后端精度。
5. **`E2R_RESULT_MEMO.md`** — §5 模板六节 + 三问专项 + 异常/坑 + 本次没做的部分。

另加（设计自担，非手册要求）：
- `e2r_per_prompt_detail.csv.gz`（逐 prompt 复算审计）
- `e2r_tolhug_delivered.csv`（tol_hug 的 ρ_budget vs ρ_eff）
- `e2r_constraint_rank.csv`（joint_null 逐 prompt 的 rank(C)/dim null）

---

## 9. 执行计划（两阶段）

**Phase A（numpy 构造 + 打分，可本地）**：
1. `run_e2r_common.py`：数据加载、seed 派生、逐边界/逐 prompt score、calib 阈值、ECDF 融合。
2. `run_e2r_construct.py`：6 family × 2 TM 构造，输出注入边界激活 + 约束秩 + tol_hug 校准参数。
3. `run_e2r_score.py`：对诚实束与攻击束打分 → TPR/FPR/evaded/localization。

**Phase B（CUDA fp32，RTX6000，路径参数化 /home/siyuan）**：
4. `run_e2r_harm.py`：`run_from_input_ids` 诚实 logits + `_output_gradient_torch` 危害方向 + `_replay` 注入 forward → harm_proxy + 下游边界捕获（回填 Phase A 的 cand 束）。
5. `run_e2r_assemble.py`：合成主表/盲点表/sweep 图/manifest/memo。
6. 强制 sanity（§3.5）在 Phase B 最先跑，不过不出数。

---

## 10. 决策点（需用户/mentor 拍板，其余已定）

> **D1 已解决**：坐标 seed 政策不是决策点——按 mentor V0-2(a)/A1.3 的"坐标对齐"框架执行（verifier seed=2026，TM-2=对齐、TM-1=错位到猜测 seed），已写死在 §3.2/§4.2。这与 mentor 已验收的 A1.3 口径一致，不另起 per-request PRF seed。
>
> **审计 A 已拍板（2026-08-09）**：投影矩阵 **P 公开**（TSTC 需承诺后可公开复算；V0-2(a) 节点执行前见 seed→P 藏不住；检测力来自"篡改几何 vs 诚实漂移"）。**坐标保密只作用于 SignRadial 抽查坐标通道**（ProjCos 无坐标抽样）。由 `TM1b_knownP` 审计臂实证（§3.2）。

| # | 决策点 | 推荐 | 若拍板不同 |
|---|---|---|---|
| D2 | 检测口径 | **trace-max 定检测 + 逐边界定定位/tol_hug 目标**，双层都报 | 纯逐边界 → 检测 evalFPR≈3%，与 §6.4 口径不一致 |
| D3 | 危害代理 | **末 token logit 相对偏移**（手册 §2.3 两个建议之一），h0=诚实 A/B 逐边界 Q_{0.95}；辅助报 argmax 迁移率。手册无强推荐（"选一个"+§9 兜底"先跑一版、歧义列给写作侧"）——本设计按此执行 | 换 token 变化率 → 32-token 解码成本 ×10、需另定解码协议、全池跑不动只能抽子集 |
| D4 | 危害方向 g | **输出梯度**（`_output_gradient_torch`），random 作对照 | 纯 random → tol_hug 的 harm 会被低估，"弱攻击刷 TPR"风险 |
| D5 | joint_null 预判 | **几何上必然可构造**（dim≈T·D−65），正面结果落在 harmful_evasion_rate | 若构造失败 → 照手册交秩与推导，是正面结果 |

> 依据手册 §9："必须上报、不要自己拍板"——D3/D5 直接改变论文结论强度，建议本轮内确认；D2/D4 是实现口径，无结论级影响，默认按推荐执行。

---

## 11. 风险与诚实边界

- **诚实泄漏**：null-space 攻击在注入边界的 score 是诚实级泄漏，不是精确 0——判盲用 `TPR ≤ 2×evalFPR`（§2.4），不承诺绝对 0。
- **传播打破零空间**：C1/C2 注入会被下游边界捕获，这是**协议的正向结果**（不是攻击失效的借口）；逃避结论只对 C3 注入陈述。
- **h0 敏感性**：harmful 定义锚在诚实异构 Q_{0.95}；若异构输出级漂移大，harmful 率系统性低——如实报告，不调。
- **C3=末层注入**：扰动只过 final_norm+head，危害可能小于 C1/C2 注入（传播少）——这是攻击本身的几何，如实报。
- **模型口径**：0.6B 单模型；不同模型/层深可能改变传播行为，memo 标注"本模型实测"。
- **性能非实验目标**：不扫节点数、不报时延均值。

---

## 12. 系统设计启示：fresh challenge 消除构造性盲点（E2-R 最大反馈）

**E2-R 的核心发现（§7 memo）**：固定-P 下攻击者可构造 e ∈ ker(SR_Ω) ∩ ker(PC_P) = joint-null（结构性盲点，任意强度逃避）。**根本原因**：P/Ω 在攻击构造前已知，攻击者"已知 A → 找 e ∈ ker(A)"。

**新协议（commit-to-seed + reveal）改变数学问题**：先 commit 完整 activation，verifier 事后生成 fresh P/Ω。**为满足公开可验证，fresh 参数用 commit-reveal 而非 verifier 秘密持有**：verifier 先提交 `C=Commit(seed_s)`，节点提交 e 后再 reveal `seed_s`，任何人从公开 seed_s 派生 P_s/Ω_s 复算。攻击者变成"先固定 e → 再随机 A"，且提交 e 时不知 seed_s（时间性秘密）。对固定 e≠0，Pr[e·P=0]=0（连续随机矩阵，a.e.）——**精确构造的 joint-null 不再可能**。

**实证（`run_e2r_fresh.py`，纯 numpy 本地可复现；seed_s 每请求随机，manifest 记录=reveal）**：
- joint_null Combo TPR：fixed-P 0.027（全盲）→ fresh-P 0.998（ρ=0.1）。构造性盲点消除。
- 残余逃避 = tolerance（小 ρ 时 e 低于阈值）——强度问题，任何阈值检测器如此。
- **tol_hug_combined 仍逃避**（fresh-P Combo 0.031）：幅度钳制攻击不依赖 P 知识（只利用公开阈值 Γ）——commit-reveal 无法消除，本质是阈值宽松。
- **P0 口径修复**：fresh 政策下 per-request 随机 seed 使 calib Q_{0.99} 在 eval 上截出 2.7% FPR（分布跨 pid 不稳定）。统一用 **eval-anchored Q_{0.99}**（fresh 与 fixed 都在 ~1.15% FPR 下测 TPR，直接可比）。Combined 因 ECDF-max 天花板饱和，用 calib-based τ_Combo + 报实际 FPR。

**协议设计要点**（纳入新协议正式机制）：
1. P 不在 execution 前公开——verifier 每请求生成随机 seed_s，先提交 `Commit(seed_s)`，节点提交 e 后 reveal。
2. Challenge 流程：verifier reveal seed_s → 任何人派生 P_s/Ω_s → 选 s 个 token → provider 打开对应 committed hidden vectors → 验 Merkle proof → verifier 计算 H_t·P。
3. 代价仅 dispute path：SignRadial q=256 开 256 scalar；ProjCos 开 s×D（s=8, D=1024 → 8192 values ≈ 几十 KB），正常推理零开销。
4. 保密性语义：ProjCos 从"知识性秘密"（泄露一次永久失效）升级为"**时间性秘密**"（每轮 commit-reveal 刷新，且公开可验证）。
5. **残余盲点 = tolerance-hugging（幅度钳制）**：这是阈值本身的宽松性，非构造问题——应对方向是阈值/安全余量设计或对输出级检测，而非坐标保密。

> 注：此为 E2-R 的**系统设计输出**，与 §0.3 搁置的 commit-then-challenge 正式化不冲突——本设计给出的是"如何消除 adaptive 盲点"的实证基础，正式化仍需写作侧完成机密性安全游戏。
