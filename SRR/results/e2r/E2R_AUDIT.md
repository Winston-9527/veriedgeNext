# E2-R 实验审计报告

- **审计对象**：`results/e2r/` 五件套（`E2R_RESULT_MEMO.md` / `e2r_main_matrix.csv` / `e2r_blindspot_table.md` / `e2r_strength_sweep.png` / `e2r_manifest.json`）及构造脚本
- **对照**：`docs/08.08继续推进手册.md` §2（E2-R 主实验卡）
- **日期**：2026-08-09
- **方法**：全量逐 cell 核对 CSV（648 行）与 memo/盲点表/图的一致性；读攻击构造（`e2r_attacks.py`）、共享协议（`e2r_common.py`）、主流程（`run_e2r_main.py`）、组装（`run_e2r_assemble.py`）；验算盲点三态、harm 门控、rho_eff、Wilson CI。

---

## 0. 结论摘要

交付合规、数字可复算、机制自洽——是一次高质量的主实验。六族攻击全部真实构造且数学精确，所有 memo 数字与 CSV 逐位吻合，盲点三态与判据严格一致。但有 **1 个威胁模型问题（已拍板：P 公开）+ 2 处 memo 事实性错误/过度概括 + 3 个统计与口径注意项**，不阻塞结论但必须在论文前修正。

---

## 1. 符合性核查（对照手册 §2）

| 手册要求 | 状态 | 核验依据 |
|---|---|---|
| 6 攻击族构造写死 manifest | ✅ | 构造数学已验算；manifest 含 code 位置 |
| 强度扫描全 6 ρ（非单点） | ✅ | CSV 六档齐全；joint_null/tol_hug_combined 六档全部 TPR=0.0096/0.0154/0.0096 |
| joint_null 构造失败须报维数 | ✅（构造成功） | rank=49 全独立，dim=12×1024−49=12239，与 memo 一致 |
| 双威胁模型 TM1/TM2 都跑 | ✅ | 216 条件 = 6×6×3×2，全齐 |
| 每 cell 六项指标 | ✅ | CSV 13 列全非空 + 额外 `tpr_ci_lo/hi`、`rho_eff`（超规格） |
| eval_fpr 必报 | ✅ | 实测 0.0096/0.0154/0.0096，与 §6.4 完全一致 |
| harmful_evasion_rate 定义清楚 | ✅ | = P(未检出 ∧ harm>h0)/n，h0=诚实 A/B logit 偏移 Q0.95，按边界分档 |
| 盲点三态判据写死 | ✅ | `blind ≤ 2×evalFPR < partial ≤ 0.5 < detected`，与手册逐字一致 |
| 5 交付物路径/列名 | ✅ | 五件全齐，列名逐项匹配 |
| Q1/Q2/Q3 必答 | ✅ | §6 三节，均有定量答案 |
| 被检出攻击须 harm 交叉验证 | ✅ | harm 全 cell 计算；§3.2 给逃避侧 harm |
| 强度谱图 | ✅ | 2×3 面板、对数横轴、6 ρ、每面板 6 条曲线（3 检测器×2 TM，比规格更丰富） |
| memo 六节 + "异常与坑/没做的"非空 | ✅ | 两节均非空且诚实 |
| 复现性 | ✅ | manifest 含数据指纹(sha256)、全部 seed、Γ/τ 数值、脚本 hash；replay sanity 逐位复现 capture |

**§2.5 轻微口径提醒**：CSV 的 `threshold_gamma` 列填的是 `tau_trace`（trace-max 检测阈值 Q0.99），而非逐边界 Γ_k。对检测 TPR 口径这正确，但列名 "gamma" 与逐边界 Γ 易混淆，建议改列名 `threshold_tau_trace` 或在 manifest 注明。

---

## 2. 严谨性审计（按严重度排序）

### A. 【已拍板·威胁模型修正】"投影 R 共同已知"与实现的 seed 派生冲突

手册 §2.2 写"共同已知：…投影 R…"，但实现中 ProjCos 的投影矩阵 P 由 `seed+911` 派生（`e2r_common.py:119`），行置换也由 seed 派生。当前实现下 TM-1 攻击者实际**不知道 P**——null_space 在 TM-1 的 partial(0.050) 是"猜错 P"导致的，不是坐标保密本身。

**✅ 拍板结论（2026-08-09）：TM-1 攻击者应知道 P，P 公开是正确威胁模型。** 理由：

1. **公开可验证**：TSTC 的核心卖点是 commit 后可被第三方复算。若统计量本身要保密才有检测力，承诺记录就不是公开可核验的，违背 §3.3（sketch 固定且公开）。
2. **现实对手看得见 P**：V0-2(a)=`node_sees_before_exec`，执行节点跑前见 seed，P 是 seed 的确定性函数 → 藏不住。
3. **检测力来源**：必须来自"篡改几何 vs 诚实漂移"，不能来自"对手不知道一张矩阵"——对全知对手（节点共谋）的威胁模型下，知识性保密不自洽。
4. **时间性秘密 vs 知识性秘密**：坐标保密成立是因为秘密是时间性的（先承诺后揭示，每轮刷新）；P 保密是知识性的（固定矩阵，揭示一次永久泄露）。
5. **数值上不值**：藏 P 只把 PC 从 blind(0.015) 抬到 partial(0.05)，不闭合结构性盲点（joint_null/tol_hug_combined 在 TM-1 下也只是 partial）。

**影响**：按拍板模型，TM-1 的 null_space 应像 TM-2 一样对 PC 盲（TPR≈FPR）。当前 0.050 partial 是实现产物。

**处置行动**：
- [ ] 补跑 "TM-1-with-known-P" 臂（P 用 verifier seed 2026、抽查坐标用猜测 seed），把"坐标保密"与"P 保密"两块的贡献拆开
- [ ] memo/manifest 措辞修正：明确 **P 公开**；TM-1/TM-2 差异仅在 SignRadial 抽查坐标
- [ ] 保密值归因修正：PC 通道检查全部行（无坐标抽样），**坐标保密对 PC 无效**；"TM-1 下所有盲点抬到 partial"只对 SR 通道成立
- [ ] ProjCos 若要受益于坐标保密 → 改为行采样设计（future work）

### B. 【高·memo 事实性错误】"C1/C2 几乎全部 detected (TPR 0.87–1.0)" 对 2/6 族不成立

memo §3.1 注释这句对 **tol_hug_combined**（TM2 C2 Combo=0.381 partial、C1=0.567）和 **tol_hug_projcos**（C2=0.579）明显不符。0.87–1.0 只覆盖 sign_balanced/null_space/joint_null/tol_hug_sr 四个族。机制也不同：零空间/平衡族是"注入边界被藏、下游捕获"；tolerance-hug 族是"注入边界被钳制、下游虽脱离钳制但仍被部分压低于阈值"。须改为两族分述。

### C. 【中·语义失真】tol_hug 强度扫描的横轴 ρ 不是真实强度

tol_hug 族 `rho_eff` 中位只有标称的 4–36%（tol_hug_combined 在 ρ=0.10 时 rho_eff=0.0094）。即攻击被钳制到阈值后，名义 ρ 是装饰性的。因此强度谱图上 tol_hug 曲线平坦是"**钳制到阈值**"，不是"强度无关盲"；joint_null 的强度无关是**真实的**（rho_eff=标称，精确 0% 偏差）。memo 把两者并成"盲点是结构性的、与强度无关"是错的。处置：图注 rho_eff 或按族分开解读。

### D. 【中·统计】盲点标签在 n=520 下不稳健

TPR=0.0096 对应 5 个检出，Wilson CI=[0.004,0.022]，**跨过** blind/partial 分界 0.0192。CSV 已存 CI，但盲点表/memo 用硬标签。joint_null 的结构性结论不依赖此（TPR=5/520 与 honest FPR=5/520 精确相等），但 sign_balanced/tol_hug 的 blind 标签有不确定性。建议盲点表单元格加 CI 或脚注。

### E. 【中·口径】harm 与 h0 用了两套基线

h0 用 replay(B)−replay(A) 同边界 logit 差；harm 用 replay(篡改)−full-forward honest logits（`run_e2r_main.py:280`）。差 10× 余量（0.23 vs 0.023）不影响结论，但论文应统一基线或论证 replay 与 full-forward 的一致性（sanity 只验了 activation，未验 logits）。另外"实质输出偏离"目前是连续 logit 偏移 + h0 阈值，detail 里有 `argmax_change` 列但 memo 未报数字——建议论文补 argmax 翻转率。

### F. 【中·表述】"坐标保密值 +0.47"是 ρ 单点 + 单猜测

保密值从 ρ=0.01 的 +0.027 到 ρ=0.10 的 +0.70，ρ 依赖极强；headline 用了最有利的 ρ=0.05。且 TM-1 攻击者是单猜测 seed=2027——更聪明的 TM-1 会 hedge 得更好，故 +0.47 是保密值**上界**。memo §6 承认"单猜测方向性"，但 headline 数字不带 caveat。建议给 ρ 扫描或至少注明。（注意：该保密值基于 sign_balanced/SR 通道，不受 A 项拍板影响。）

### G. 【低】q=64 与 P1 的张力

P1 已证 q=64 在 angular 方向退化（修复用 q=1024）。E2-R 用 q=64 与 §6.4 协议自洽（阈值同源），且结构性盲点（分子精确清零）与 q 无关，可辩护；但论文应说明协议为何定 q=64。

### H. 【低】localization_acc 在盲点 cell 分母极小

盲点行只对个别检出样本算定位，无统计意义。memo 已声明不用，CSV 对 nan 有处理。建议论文只引用 C1/C2 注入（分母大、locAcc=0.015 有统计意义）的定位结果——"检出但定位错到下游边界"是重要的独立发现。

---

## 3. 对三问的回答质量评价

- **Q1（tolerance-hugging 在 SR 下成立吗）→ 成立且升级。** tol_hug_sr 六档 ρ 下 SR TPR=0.008–0.010（全盲），复现 8/3 结论；tol_hug_combined 更严重——三检测器六档全盲，harm 0.18–0.23（ρ=0.10 时 0.228）零报警，rho_eff 只有 0.0094。**注意**：这句"连 Combined 都能躲"只在 TM-2 下成立（TM-1 下 tol_hug_combined 是 partial 0.03–0.05）——结论句应显式限定威胁模型。

- **Q2（joint_null 能否同时躲）→ 能，且是结构性盲点。** 构造精确（e0−λv 组合，rank=49 全独立，dim=12239），六档 ρ 三检测器全部 TPR=精确 FPR，99% 有害。落入手册 §2.6 第二种结局——"盲点是结构性的"在安全会议比"补上洞"更有分量。附带发现（注入 C1/C2 会被下游捕获但定位错到下游 locAcc=0.015）是真实的独立结果。

- **Q3（Combined 净增益）→ 真实但有限，负增益如实报。** ΔTPR 从 −0.133（sign_balanced）到 −0.006（joint_null），全部 ≤0。Combined 的价值在"非自适应覆盖 + 坐标保密下稳健"，不在"抵抗自适应联合盲点"。论文写法：主表（§6.4）上 Combined 纯增益 TPR=1.0，自适应上为负——把两表并置才是贡献点 3 的完整图景。

---

## 4. 对论文路线的含义

在 V0-2(a)=`node_sees_before_exec` 下，TM-2 是现实模型 → joint_null/tol_hug_combined 结构性破坏 bounded arbitration → **贡献点 3 强度必须下调**，按手册 §2.6 第三种结局在 Discussion 正面处理。§0.3 搁置的 commit-then-challenge 得到量化实证：保密值 +0.03~+0.70（ρ 依赖，SR 通道），但**不足以闭合结构性盲点**——TM-1 下 joint_null 只是从 blind 抬到 partial（0.04–0.06），不是 detected。

**P 公开拍板后的修正**：坐标保密仅保护 SR 通道（+0.03~+0.47，ρ 依赖）；PC 通道无坐标抽样，坐标保密对其无效。若要 ProjCos 受益，需行采样设计（future work）。

---

## 5. 待办清单（拍板后，第一轮）——更新见 §6

**实验**
- [x] 补跑 "TM-1-with-known-P" 臂 → 已完成：TM1b_knownP（P=2026/Ω=2027），见 §6.2
- [ ] 被检出 C1/C2 攻击的 harm 交叉验证数字补进 memo（§3.2 已有逃避侧，检出侧缺）
- [x] argmax 翻转率汇总进 memo → 已做（§3.2 新增列，口径待确认，见 §6.3-8）

**文档修正（E2R_RESULT_MEMO.md）**
- [x] B 项 → 已修（§3.1 两族分述）
- [x] C 项 → 已修（§3.4 拆开真·强度无关 vs 阈值封顶）
- [x] F 项 → 已修（§6 全 ρ-scan 表）
- [x] 结论句限定 TM-2 → 已修（§5"知道 P、知道/猜测 SR 坐标"）
- [x] manifest column_note（threshold_gamma=τ_trace）→ 已加
- [x] 盲点表加 Wilson CI → 已加（D 项）
- [ ] 主盲点表 TM-1 null_space 对 PC 更新为 blind → 未做（主表仍是旧 TM-1 0.050；TM1b 在独立 e2r_knownP）

**论文**
- [ ] 贡献点 3 措辞按"结构性盲点 + Combined 负增益"下调，Discussion 正面处理
- [ ] 坐标保密价值限定为"SR 通道 + 上界 + ρ 依赖"
- [ ] ProjCos 行采样列为 future work

---

## 6. 第二轮审计（新结果，2026-08-09 晚）

**范围**：memo 更新（新增 §3.3 解码验证、§6 审计臂 TM1b_knownP、多猜测稳健臂、保密值全 ρ-scan）、新脚本 `run_e2r_harm_decode.py`、新目录 `results/e2r_knownP` / `e2r_gs12345` / `e2r_gs777` / `e2r_harm_decode`。

### 6.1 上轮审计项复查

| 项 | 状态 |
|---|---|
| A（P 公开拍板）| ✅ 已执行：TM1b_knownP 臂实现正确（`run_e2r_main.py --p-seed` + `e2r_attacks.py p_seed` 分支），CSV 数字与 memo §6 审计臂表逐位一致 |
| B（C1/C2 过度概括）| ✅ 已修：§3.1 拆为零空间/平衡族（0.87–1.0 detected）vs tolerance-hug 族（部分逃逸 0.38–0.58）|
| C（tol_hug 强度语义）| ✅ 已修：§3.4 拆开 joint_null（真·强度无关，rho_eff=标称）vs tol_hug_combined（阈值封顶，rho_eff≈0.0094）|
| D（盲点 CI）| ✅ 已修：盲点表加 Wilson 95% CI + 脚注 |
| F（保密值单点）| ✅ 已修：§6 全 ρ-scan 表（+0.004→+0.700）|
| threshold_gamma 列名 | ✅ 已修：manifest `column_note` |
| E（harm 双基线）| ⚠️ 未处理（replay vs full-forward）；decode 实验的 honest 对照是 full-forward，方向一致，建议 memo 说明 |
| G（q=64）/ H（localization）| 维持原状 |

### 6.2 新交付物核查

**TM1b_knownP（results/e2r_knownP/）**：实现正确（P=verifier seed 2026、Ω=guess seed 2027），CSV 数字与 memo §6 审计臂表一致（null_space PC 0.015→盲、sign_balanced SR 0.037 不变、joint_null SR 0.038）。**审计 A 的结论被实证**：P 公开后 PC 族攻击全部回落到 TM-2 水平（0.015），坐标保密只作用于 SR 通道。

**解码验证（results/e2r_harm_decode/）**：`run_e2r_harm_decode.py` 方法学合理——hook 替换 layer-27 在 prefill 的输出（KV 保持诚实，忠实于"篡改末层输出不改 KV"），32-token 贪婪解码，honest 对照=模型正常 generate。summary 与 memo §3.3 逐位一致（token 一致率 0.033–0.144、ROUGE-L 0.25–0.34、p_output_changed 0.88–1.0）。

**多猜测稳健臂（results/e2r_gs12345/、e2r_gs777/）**：detail 显示 TM1 各族 s_C3 得分与主表（gs2027）不同（null_space/joint_null 520/520 得分全不同）→ **确实用了不同 seed**（非 2027 重复）。但 memo §6 表数字与落盘数据全部不符（见 §6.3-1）。

### 6.3 新发现（按严重度）

**1. 【数据完整性·最高】memo §6 多猜测表数字与落盘数据全部不符**

memo §6 声称（gs2027/gs12345/gs777 三列，ρ=0.01，C3，TM-1 SR TPR）：

| family | memo gs2027 | 实际主表(2027) | memo gs12345 | 实际 gs12345 | memo gs777 | 实际 gs777 |
|---|---|---|---|---|---|---|
| sign_balanced_sr | 0.049 | **0.037** | 0.049 | **0.037** | 0.049 | **0.037** |
| null_space_projcos | 0.050 | **0.040** | 0.048 | **0.038** | 0.050 | **0.038** |
| joint_null | 0.050 | **0.040** | 0.048 | **0.038** | 0.050 | **0.038** |
| tol_hug_sr | 0.046 | **0.033** | 0.047 | **0.033** | 0.047 | **0.035** |
| tol_hug_projcos | 0.049 | **0.037** | 0.031 | **0.023** | 0.048 | **0.037** |
| tol_hug_combined | 0.042 | **0.031** | 0.021 | **0.015** | 0.037 | **0.029** |

**18 个 cell 全部对不上，memo 数字系统性偏高。** memo 的 gs2027 列（0.049/0.050/...）与主表 TM-1（同 seed 2027）也不一致——不是 gs 目录的问题，是 memo 引用了无来源数字。**必须核对 memo 多猜测表的数字来源并替换为实际数据。**

**2. 【数据完整性·高】memo §6 "ρ=0.05 三族 SR TPR 完全一致（0.822）" 无来源**

实测 TM-1 ρ=0.05 SR：主表=0.475/0.477/0.475，gs12345=0.477/0.483/0.485，gs777=0.477/0.475/0.471。**没有任何数据是 0.822。**

**3. 【复现性·高】script_hashes 与实际文件全部不符**

- 主表 manifest 声称 e2r_attacks.py=dba6a035，实际文件（加 p_seed 后）为 e02a17ee
- **e2r_knownP manifest 声称的 hash 与主表相同（dba6a035），但 TM1b 必须用带 p_seed 的代码（e02a17ee）才能跑——TM1b 的 manifest 记录了错误的脚本版本**，当前文件无法复现 TM1b
- 建议：脚本纳入 git，manifest 记录 commit hash；至少把 hash 改为实际值并注明版本差异

**4. 【复现性·中】gs12345/gs777 缺完整 manifest 和主矩阵 CSV**

只有 `manifest_partial` + detail。且 `manifest_partial` 的 `primary_guess_seed` 是**硬编码常量 2027**（`run_e2r_main.py` 写死 `PRIMARY_GUESS_SEED`），不反映实际 `--guess-seed` 参数——**无法从交付物确认 gs 目录实际用了哪个 seed**（只能靠 detail 得分反推）。需补 manifest 记录实际 guess_seed，并生成主矩阵 CSV。

**5. 【交付完整性·中】gs 目录只跑了 TM-1**（108 条件，无 TM-2）。作为"多猜测稳健臂"合理（只测 TM-1 的 seed 敏感性），但 memo 未显式声明，读者可能误以为含 TM-2。

**6. 【交付完整性·中】harm_decode 缺 manifest/hash**：`run_e2r_harm_decode.py` 无对应 manifest，只有 summary + per_prompt。补 manifest（seed、rho、max_new、模型路径、脚本 hash）。

**7. 【交付完整性·低】e2r_knownP 盲点表主体 12 行全为 "-"**：`run_e2r_assemble.py` 的 `write_blindspot` 假设 tm ∈ {TM1_seed_secret, TM2_seed_known}，TM1b 不匹配 → 空。TM1b 的正确对照在 CSV / memo §6 审计臂表。修正 assemble 脚本或接受独立 CSV。

**8. 【口径·低】§3.2 argmax 翻转率与数据微差**：按 Combo-evaded 口径重算：tol_sr=0.991（memo 0.988）、tol_pc=0.988（0.983）、tol_comb=0.892（0.883）。接近但非逐位一致，memo 需注明口径（合并 detector 或 Combo-evaded、全样本或 evaded）。

**9. 【表述·低】§3.3 p_output_changed 是弱指标（tautology 风险）**：定义为"32 token 中任一不同即算改变"，而注入直接改首 token logits → 首 token 变则 32-token 必变（自回归级联），p_output_changed≈1 是构造性必然，无新增信息。**核心论据应是 token 一致率 0.033–0.144**（输出几乎全文重写）——这个扎实，论文应突出它而非 p_output_changed。

**10. 【方法·低】§3.3 解码实验只跑 TM-2/C3/ρ=0.01**：与 §3.2 harm 口径一致，合理；但 memo 的"逃避的攻击改变输出"结论应显式限定为该条件。

### 6.4 第二轮待办

**数据完整性（最高优先）**
- [ ] 核对 memo §6 多猜测表数字来源，替换为实际数据（§6.3-1 表格）
- [ ] 核对/删除 memo "0.822" 无来源 claim（§6.3-2）
- [ ] 补 gs12345/gs777 的 manifest（记录实际 guess_seed）并生成主矩阵 CSV

**复现性**
- [ ] 脚本纳入 git，manifest 记录 commit hash；修正 e2r_knownP manifest 的 script_hashes（§6.3-3）

**交付完整性**
- [ ] harm_decode 补 manifest（§6.3-6）
- [ ] 修正 assemble 的 TM1b 盲点表或接受独立 CSV（§6.3-7）

**口径**
- [ ] memo 注明 argmax 翻转率口径（§6.3-8）
- [ ] memo §3.3 突出 token 一致率，弱化 p_output_changed（§6.3-9）
- [ ] memo §3.3 结论限定 TM-2/C3/ρ=0.01（§6.3-10）

---

## 7. 第三轮审计（修复验证，2026-08-09 深夜）

**方法**：对第二轮 §6.3 全部 10 项 + E 逐项重新验证；主工作区同步抽查。

### 7.1 第二轮修复逐项验证（全部通过）

| # | 修复 | 验证结果 |
|---|---|---|
| 🔴1 | 多猜测表 18 cell 改实际数据 | ✅ **逐位一致**。gs2027=0.037/0.040/0.040/0.033/0.037/0.031、gs12345=0.037/0.038/0.038/0.033/0.023/0.015、gs777=0.037/0.038/0.038/0.035/0.037/0.029，mean/range 正确（tol_hug_combined range=0.031−0.015=0.015 用未舍入值） |
| 🔴2 | 0.822 → 实测 | ✅ 0.475/0.477/0.477（sign_bal）与 0.475/0.485/0.471（joint_null）从 gs 主矩阵逐位核对 |
| 🟡3 | script_hashes 动态计算 | ✅ assemble 用 `hashlib.sha256(...)[:12]`（非 git SHA1），5 文件全部匹配。**注：我第一轮用 git hash-object（SHA1）判"不符"是验证方法错，SHA256 下实际全对** |
| 🟡4 | gs 补 manifest/主矩阵 | ✅ e2r_gs12345/777 有完整 manifest + main_matrix + blindspot + sweep；`primary_guess_seed` 正确（12345/777） |
| 🟡5 | gs scope 声明 | ✅ manifest `scope="TM1_seed_secret only (guess-seed robustness arm); TM2 rows absent"` |
| 🟡6 | harm_decode manifest | ✅ `e2r_harm_decode_manifest.json` 完整（method/scope/metrics/hash），metrics 诚实标注 p_output_changed 的 tautology |
| #7 | knownP 盲点表 | ✅ TM1b 6 族正确（null_space PC=0.015 blind、sign_bal SR=0.037 partial 等）；All-boundaries 部分 C1/C2 为 "-" 属正常（TM1b 只跑 C3 注入，scope 已声明） |
| #8 | argmax 口径 | ✅ §4 注明"detail 逐 prompt 重算 tol_hug_combined=88.27%" |
| #9 | p_output_changed | ✅ §3.3 重新定位：核心证据=token 一致率 3–14%，p_output_changed 降为辅助并说明 tautological 部分 |
| #10 | §3.3 范围限定 | ✅ "仅覆盖 TM-2/C3/ρ=0.01" |
| E | harm 双基线 | ✅ §4 注明 replay vs full-forward、10× 余量、decode 同源 |
| 新增 | 检出侧 harm 交叉验证 | ✅ 检出数（1040/913/719/493）与 mean harm（0.960/0.449/0.181/0.147）从 detail 逐位复算一致 |

**附加验证**：
- 主工作区 `workspace/AdversarialEvaluation/results/e2r/` 与 worktree 同步（memo 逐字节一致；e2r_robust_gs12345/777、e2r_knownP、e2r_harm_decode 齐全）
- gs12345 盲点表三态判定复核正确（tol_hug_combined TM1: SR 0.015/PC 0.027/Combo 0.019 均 ≤2×evalFPR → blind ✓）
- 主表 e2r_main_matrix.csv 与 detail 完全一致（四舍五入 6 位 vs 完整精度）

### 7.2 新发现（第三轮）

**【低级·口径】memo §3.2 检出侧表 tol_hug_combined "检出且有害 98.8%" 用了统一 h0=C3，未注明**

复算：tol_hug_combined C1/C2 Combined 检出 493 个，
- **per-boundary h0**（§3.2 声称的口径，C1=0.0087/C2=0.0118）：489 有害 = **99.2%**
- **统一 h0=C3=0.0233**：487 有害 = **98.8%**（与 memo 精确吻合）

memo §3.2 声明 h0 是 per-boundary，但检出侧表实际用了统一 C3 的 h0（更严，把 harm∈(0.0118,0.0233] 的 2 个样本判为无害）。概念上 per-boundary 才对（C1 注入的诚实漂移是 0.0087，用 0.0233 判定偏严）。结论不受影响（98.8% vs 99.2% 均为"几乎全部有害"），但**口径未注明**，且与 §3.2 声称的 per-boundary h0 矛盾。**建议**：memo 注明"检出侧统一用 C3 h0（保守口径）"，或改用 per-boundary（99.2%）。

**其余全部无问题**。主实验结论（结构性盲点、坐标保密只作用 SR、输出级危害）均建立在主表 CSV/detail 上，复核正确。

### 7.3 第三轮待办

- [ ] memo §3.2 检出侧注明 h0 口径（统一 C3 vs per-boundary），或改用 per-boundary 99.2%（§7.2）

---

## 8. 第四轮审计（fresh-P 协议验证，2026-08-10）

**范围**：`run_e2r_fresh.py` + `results/e2r_fresh/`（commit-then-challenge 的 fresh per-request P/Ω 验证）。用户重点检查 tol_hug 攻击实现是否符合"先 commit e、后 reveal fresh seed_s"。

### 8.1 用户核心检查点：tol_hug 是否符合 commit-then-challenge？→ **符合**

验证代码执行顺序（`run_e2r_fresh.py`）：
1. **攻击构造（line 108-138）**：`AG = args.guess_seed`（默认 2026），tol_hug 的 `score_fn` 全部用 `AG`（如 `sr_score(c1, x1, SR_Q, AG)`），`construct(..., AG, ...)` 传入 AG。
2. **检测（line 140-148）**：`detect(cand, ref, seed_map[pid])` 用 fresh random seed_s。
3. `_grid_bisect`（`e2r_attacks.py:150`）只查询 `score_fn`（= AG 下 score），**不触碰 fresh seed_s**。

**攻击者 commit e 时不知道 seed_s，无法读取本轮 fresh detector score 来缩放 e——协议顺序正确。** 用户担心的"生成 fresh P/Ω → 计算 score → 调整 e"违规模式**不存在于 run_e2r_fresh.py**。

（对比：主实验 `run_e2r_main.py` 的 TM-2 下 tol_hug 确实用真实 verifier seed 的 score 缩放 e——但那是在**固定 P/Ω 协议**下，TM-2=攻击者知道 seed 是合法的白盒；fresh 实验正确隔离了该假设。）

**fresh 结果定性方向正确**：joint_null 结构性盲点被打破（C3 TM-2，ρ=0.10：fixed SR=0.010→fresh SR=0.739、PC=0.015→1.0、Combo=0.010→0.998；ρ=0.05 时 SR=0.565）。攻击者不知道 seed_s，无法精确构造 ker(P)∩ker(Ω) → 精确 joint-null 不可能。残余逃避仅为 tolerance（ρ≤0.005 时 TPR≈FPR）。

### 8.2 新发现（第四轮）

**🔴 P0：fresh 协议 honest FPR 漂移到 2.7%（标称 1%）——TPR 不可与 fixed 基线直接比**

- `fpr_fresh = {SR: 0.0269, PC: 0.0269, Combo: 0.0135}`。
- **根因（已诊断）**：per-request random seed_s 使 honest score 分布跨 pid 不稳定。eval SR Q0.99=0.0115、max=0.0178，均高于 calib（0.0088/0.0123）→ calib 200 样本的 Q0.99 在 eval 上截出 2.7% 而非 1%。固定 seed 2026 下同法 FPR=0.96% 正常 → **是 fresh 协议固有技术问题，非脚本 bug**。
- **影响**：fresh 的 TPR 是在 2.7% FPR 下测的，与 fixed 基线（0.96% FPR）不公平。joint_null ρ=0.10 SR=0.74 校准回 1% 后可能 ~0.5–0.6，但仍远高于 fixed 的 0.01——定性结论（fresh 打破盲点）大概率成立，**数字需校准后重测**。
- **盲点判据**：fresh 下 eval_FPR=0.027 → blind 阈值=0.054。ρ=0.002 TPR≈0.027–0.033 仍 blind；ρ=0.01 SR=0.088 > 0.054 → partial。用统一 eval_FPR 判据即可，但需注明 FPR 口径。
- **修复方向**：更大 calib（如 500+）；或 honest score 对多个 seed_s 取期望的统计量（更稳）；或报告 TPR@统一 1% FPR（按 fresh honest 分布重校准）。

**🟡 P1：MASTER/seed_map 记录在 manifest——协议保密性提醒**

`e2r_fresh_manifest.json` 记录了 `master=20260810` 和完整 `seed_reveal`（所有 pid 的 seed_s）。实验隔离正确（攻击者代码用 AG，不读 manifest），但**这是协议设计提醒**：若执行节点在 reveal 前能读 manifest/MASTER，则能预计算 seed_s → fresh 保密即破。论文需说明 seed 生成机制的保密前提（MASTER 为 verifier 秘密 / 公共随机信标 drand / reveal 前不可读）。

**🟡 P2：harm 方向 g = 随机高斯（line 119），非输出梯度**

pure numpy 无法算梯度，故用 `rng.normal`。这**改变了 tol_hug 攻击语义**——不再瞄准最大危害方向（主实验用 `_output_gradient_torch`）。只测 TPR/FPR 时合理（脚本已注明 "harm not needed"），但：① 与主实验 tol_hug（梯度方向）不可直接比；② fresh 实验未测"逃避的篡改是否有害"（harm/输出改变），需补或注明局限。

**🟢 P3：攻击者是单猜测固定 seed（AG=2026），非 EOT**

攻击者猜固定 2026，不是对 seed_s 分布取期望（Expectation-over-Transformation）。EOT 攻击者可利用公开的 challenge distribution 构造更优 e → **fresh 协议收益可能被高估**。论文应注明攻击者模型局限，EOT 作为更强后续测试。

**🟢 P4：AG 默认值 = VERIFIER_SEED=2026**（旧协议 verifier seed）。fresh 下猜任何固定 seed 都约等于瞎猜（verifier 用 random），合理但建议说明"攻击者假设 verifier 沿用旧 seed"。

**验证通过**：fresh 结果可复现（manifest 含 MASTER、seed_reveal、tpr_fresh 全量）；主工作区已同步；Combined 检测用 trace-max ECDF 与 §6.4 同口径。

### 8.3 第四轮待办

- [ ] **P0**：fresh 实验校准回 1% FPR 重测（更大 calib 或对 seed 期望的统计量），或报告 TPR@统一 1% FPR；盲点表注明 fresh eval_FPR=0.027 口径
- [ ] **P1**：论文写明 seed 生成保密机制（MASTER 保密 / 公共信标），pre-reveal 可读性
- [ ] **P2**：fresh 结论注明随机 harm 方向；补逃避侧 harm/输出改变验证（用梯度方向需 CUDA）
- [ ] **P3**：注明单猜测非 EOT 攻击者模型；EOT 列为 future work

---

## 9. 第五轮审计（fresh P0 修复验证，2026-08-10）

**范围**：`run_e2r_fresh.py` eval-anchored 修复版 + 更新后的 `results/e2r_fresh/` + memo §7。

### 9.1 P0 修复验证：eval-anchored 统一 1% FPR —— 基本达标

| 项 | 结果 |
|---|---|
| 阈值方法 | ✅ SR/PC 用各政策下 eval honest 的 Q_{0.99}（`run_e2r_fresh.py:101-102,134-135`），Combined 因 ECDF 天花板（n/(n+1)≈0.995）改用 calib-based τ_Combo（:103,138-140） |
| eval FPR 对齐 | ✅ SR/PC：fresh=0.0115 = fixed=0.0115（均 1.15%，nominal 1% 达标）|
| 修复后数字 | ✅ 与用户报告逐位吻合：joint_null Combo fixed 0.027→fresh 0.023→0.998、PC 0.012→1.000、null_space PC→1.000、sign_balanced SR 0.012→0.683、tol_hug_combined Combo 0.027→0.031 |
| 审计预测 | ✅ joint_null SR fresh ρ=0.10=0.681，落在预测区间 0.5–0.6 之上沿——定性结论成立 |
| memo §7 | ✅ 完整记录协议机制、P0 修复、结果、P1/P2/P3 局限；对 tol_hug_combined 解读准确（幅度钳制不依赖 P，利用公开 Γ）|
| 图 | ✅ `e2r_fresh_vs_fixed.png` 存在（run_e2r_figs.py 生成），4 面板 |
| 主工作区同步 | ✅ manifest/csv/memo 已同步 |

### 9.2 新发现（第五轮）

**🟡 问题 A：Combined 通道 fresh 与 fixed 用了不同的融合定义——FPR 未对齐（fresh 1.35% vs fixed 2.69%）**

- **fresh 侧**（`run_e2r_fresh.py:182`）：`combo = max(u_tr_sr(trace_sr), u_tr_pc(trace_pc))` → **trace-ECDF fusion**（与主协议 §6.4 `combo_trace` 同口径），阈值 `tau_fresh[Combined]=Q0.99(cal_tr_combo)` 与之匹配 → FPR=1.35%。
- **fixed 侧**（:127-133）：从主 detail 读 Combined 行的 `s_C1/C2/C3`（**per-boundary ECDF-max fusion** `combo_b[b]`），取 `max` 后与主协议 calib τ_Combo（为 trace-ECDF 校准）比较 → **融合定义与阈值不匹配** → FPR=2.69%（主表正确 trace-ECDF 口径下是 0.96%）。
- **影响**：Combined 列的 fixed TPR（0.027）在 2.69% FPR 下测得，fresh TPR（0.998）在 1.35% FPR 下——Combined 通道 fresh vs fixed **不可严格比**。但方向成立：修正后 fixed 会更低、fresh 相对更高，定性结论（joint_null 盲点被打破）反而被强化。
- **修复**：fixed 侧统一用 trace-ECDF fusion（或直接用主 detail 的 `detected` 列/主表 TM-2 TPR），使 Combined 与 SR/PC 一样在 ~1% FPR 下比较。

**🟢 问题 B：tol_hug_combined 严格判据下是 partial（非 blind）**

- memo §7 标 "仍盲"，但按 §2.4 判据：fresh Combo FPR=1.35% → blind 阈值=2×1.35%=2.7%；tol_hug_combined ρ≥0.02 的 Combo TPR=3.1% > 2.7% → **partial**。
- 科学意义不变（memo 结论 3 准确）：fresh 无法消除幅度钳制攻击（只利用公开 Γ），tol_hug_combined 在 fresh 下仅从 2.7% 微升到 3.1%。但**状态标注应改 partial**，且这个"仍逃避"的结果恰恰是重要发现——fresh 协议打破构造盲点但暴露"阈值宽松"这一剩余盲点，与 memo 结论 3/4 一致。

**🟢 问题 C：eval-anchored 使 fixed TPR 相对主协议虚高**

- fixed joint_null Combo：eval-anchored 0.027 vs 主表 TM-2 0.010。eval-anchored 阈值（SR 0.008817）< calib-based（0.008965），检测更松。
- 测试集校准的固有副作用（阈值过拟合 eval、真实 FPR 被低估）。memo 已注明"test-set calibration acceptable for protocol comparison"作为局限 ✓，但论文引用时应明确这是**协议对比口径**，非主协议口径。

### 9.3 第五轮待办

- [ ] **A**：fixed 侧 Combined 统一 trace-ECDF fusion（或直接用主 detail `detected`/主表 TM-2 TPR），使 Combined 也在 ~1% FPR 下比较（§9.2-A）
- [ ] **B**：memo §7 的 tol_hug_combined 状态从"仍盲"改为"partial（幅度钳制残留）"，附 fresh Combo FPR 口径（§9.2-B）
- [ ] **C**：论文注明 eval-anchored 为协议对比口径（§9.2-C）

---

## 10. 第六轮审计（fresh harm 补充实验，2026-08-10）

**范围**：`run_e2r_fresh_harm_decode.py` + `results/e2r_fresh_harm/` —— 回答"fresh 协议下仍逃避的攻击（尤其 tol_hug_combined）是否影响最终输出"。

### 10.1 方法验证（代码级）

- 协议与 `run_e2r_fresh.py` 完全一致（MASTER=20260810、seed_map、eval-anchored 阈值：SR/PC=Q99(eval)，Combined=Q99(cal_tr_combo)；FPR 复核 SR/PC=0.0115、Combo=0.0135 与 run_e2r_fresh.py 逐位一致）
- **攻击用真实输出梯度 g**（`_output_gradient_torch`，"3C"）——现实攻击者（执行节点有模型访问权），修正了第 4 轮 P2 的"随机 g"局限
- 攻击构造用 AG=2026（猜 seed），检测用 fresh seed_s——**commit 前不可知 seed，协议顺序正确**（与 §8.1 一致）
- **第 4 轮 bug 已在早期修复**：decode inject 初版用 [1,T,D]，原始脚本用 [T,D] → 修复后 `np.stack` 形状正确（sanity 6 样本 + 全量 520 均通过）
- harm=replay(C3, b+e) 末 token logit vs honest full-forward，rel-L2；h0_C3=0.0233

### 10.2 结果（520 eval，C3/ρ=0.01，Combo-evaded）

| family | n_ev | harm_mean | argmax_flip | tok_agree | out_chg | harm>h0 |
|---|---:|---:|---:|---:|---:|---:|
| joint_null | 506 | 0.240 | 1.000 | 0.033 | 1.000 | 1.000 |
| sign_balanced | 506 | 0.240 | 1.000 | 0.033 | 1.000 | 1.000 |
| null_space | 506 | 0.240 | 1.000 | 0.033 | 1.000 | 1.000 |
| tol_hug_sr | 506 | 0.233 | 0.986 | 0.047 | 0.986 | 0.984 |
| tol_hug_projcos | 507 | 0.213 | 0.951 | 0.078 | 0.951 | 0.951 |
| **tol_hug_combined** | **507** | **0.176** | **0.893** | **0.133** | **0.893** | **0.888** |

**验证数字**：与 summary.json 逐位一致；与 fixed 协议 §3.2/3.3 对比——tol_hug_combined fresh harm=0.176 vs fixed 0.184、out_chg 0.893 vs 0.883；joint_null fresh=0.240 vs fixed 0.240。**fresh 与 fixed 危害几乎相同**（构造盲点消除，但幅度钳制残留危害不变）。

### 10.3 结论

1. **直接回答用户问题**：不知道 P/Ω 的节点**不能**做任意强度的精确构造攻击（fresh 挡住 joint_null），但**能**做钳制到阈值容忍幅度的篡改（tol_hug_combined，只用公开 Γ+梯度 g），且该受限篡改 **89% 改变最终输出**——残留威胁真实。
2. **fresh 协议 is 部分解**：消除"构造盲点"（需要 P/Ω 的那类），留下"阈值宽容"（只需公开 Γ 的那类）——任何固定阈值检测器的固有极限。
3. **memo 已更新**：§7 加入 fresh harm 表，tol_hug_combined 明确"规避且 89% 有害"，P2 局限标记为已补测。
4. **主工作区已同步**：summary/per_prompt/脚本均落地 `e2r_fresh_harm/`。

### 10.4 第六轮待办

- [ ] 补 fresh harm 图（TOKEN/LCS 对比 fresh vs fixed，`run_e2r_figs.py` 扩展）——论文 fig
- [ ] 保留第五节待办 A/B/C（Combined fusion 口径、tol_hug 状态 partial、eval-anchor 注）——独立技术债，不影响本实验结论
