# VERIFIER_SEED_SECRECY_MEMO — sketch seed 对执行节点的保密性核实

> 对应：`08.08继续推进手册.md` §1 V0-2(a)（8/9 到期）
> 版本：2026-08-08｜代码版本：主仓库 `059a7fc`，`verifiable-exo@baf15385`
> **结论一句话：`node_sees_before_exec`** —— 当前实现中 sketch seed 是共享源码里的公共常量，执行节点可在执行前算出精确抽查坐标，seed 不保密。

---

## 1. 时序表（对齐真实 E3-T 端到端——锚定"执行节点在各真实阶段看到什么"）

> 真实管线（P0E3_TRACE_DELIVERY_HANDBOOK，2026-08-09 三节点一次运行）：Requester 加密请求 → rank0(mini1) 解密+首分片 → activation_exchange → rank1(RTX3090)/rank2(RTX6000) 下游捕获/注入 → scripted post-run 离线验证对账。
> **实测分片（本次运行，动态）**：mini1=rank0 层**0-1**、RTX3090=rank1 层**1-4**、RTX6000=rank2 层**4-28**——EXO 按节点 `ram_available` 动态分配，**重跑会变**（历史 memo 的 0-22/22-28 等均不同），不许照抄。

| # | 真实相位（E3-T walkthrough 14 phase）| 实测（E3-T 一次运行）| 谁生成 seed | 谁持有 | 执行节点此刻可见什么 | 代码位置 |
|---|---|---|---|---|---|---|
| 1 | **publish_ciphertext → placement/commit**：Requester 发 verifiable 加密请求，放置绑定 provider | — | **无 seed 生成**（放置只绑定 provider 与加密 payload）| — | placement 元数据 + 密文 payload（下游不读明文）| `verifiable/placement.py:10`；`client.py:19-69`（`build_verifiable_chat_request`）；`crypto.py:40-65`（X25519）；`shared/types/events.py:150`、`shared/apply.py:508` |
| 2 | **release_access_package → fetch → decrypt（rank0 ingress, mini1）**：下游只 fetch access 包；rank0 解密输入 | rank0 `decrypted_envelope`、`ciphertext_bytes_fetched=176`、`private_input_accessed=True`；下游 `shape_only_dummy`、`0` bytes、`False` | 无 | — | rank0 明文；下游只拿 upstream activation，**不读明文**（`payload_access_table.csv` 实锤）| `verifiable/runtime.py:136-200`（下游 shape-only、不触密钥）；`E2Edocs/scripts/p0e3_trace_request.py` |
| 3 | **执行前（任务已放置，分片待跑）** | — | seed 是**源码常量**：线上 TSTC 默认 `0`、P0-E2 verifier 默认 `selection_seed=0`、SR 主表写死 `2026`、E3 脚本写死 `9527` | **共享源码（所有节点运行同一份）** | **可见 seed 常量 + 派生函数**（`SHA256("accountedge-e2:{seed}:{purpose}")→PCG64` 或 SR 主表 `default_rng(seed)`）——节点从此刻起即可算出将检查的坐标 | `tstc/sketch.py:18-21`；`accountedge_e2/verifier.py:27,72-75`；`<SRR>/run_p0_main_table_720.py:37-38`；`E2Edocs/scripts/p0e3_3node_localize.py:110` |
| 4 | **shard_exec_C1/C2/C3 + activation_exchange**（三节点跑分片 + 边界交换；B1/B2 hook 捕获/注入）| 总推理 **1.28s**；shard_exec C1=887.9ms / C2=890.9ms / C3=886.5ms（trace span 按 rank+时窗过滤）；B1(rank1) 恒等 ×1.0 捕获 ratio 全 1.0000；B2(rank2) 注入 ×2.0 捕获 ratio 全 2.0000（21 对）| 无 | — | **收到 honest 边界张量 H**（接收本就是执行的一部分）；capture 存 H、inject 生成 H̃、after-inject 存 H̃；**全程无 seed** | `worker/engines/mlx/boundary_hook.py:43-66`（capture/inject/after-inject 纯张量）；`attack_injector.py` |
| 5 | **challenge_issue** | scripted post-run（离线验证器）| 脚本常量 `9527` | 离线脚本 | **无在线 challenge**——E3-T 手册 §4.4/§7.7 明说 challenge/reveal/verify/localize/settle 全部是 scripted post-run，非在线实时 | `p0e3_3node_localize.py:110` |
| 6 | **sketch_reveal** | 离线 | — | — | **无在线 reveal 实现** | （无运行时 reveal 代码）|
| 7 | **verify → localize → settle → log_append**：离线 `VerifierChain.evaluate` 对比 H vs H̃，first-mismatch 定位归因 | **first_mismatch = B2**（21/21 ratio=2.0000，逐对相等）；B1 恒等 0 误报；归因到 rank2/RTX6000/node `2720786b…` | 脚本常量 | 离线脚本 | seed 硬编码；坐标由公开派生函数确定 | `tstc/verifier.py:55-113`；`accountedge_e2/verifier.py:297+`；`p0e3_3node_localize.py`、`p0e3_trace_collect.py` |

**要点**：
1. **从 publish 到 verify，没有任何协调方持有、且对执行节点保密的 seed。** seed 从第 3 行起就躺在节点运行的共享源码里——真实 E3-T 的执行节点（mini1/RTX3090/RTX6000）跑的就是这份代码。
2. **真实执行节点全程不接触任何"秘密 seed"**：rank0 解密后跑分片、rank1/rank2 接收边界张量后捕获/注入，看到的唯一 seed 是它们自己源码里的常量（`0`/`2026`/`9527`）。
3. **challenge/reveal/verify 在真实管线里不存在**：E3-T 一次运行把它们做成 **scripted post-run 离线验证器**（`p0e3_3node_localize.py`），seed 硬编码 9527；线上 TSTC 模块（`evaluate_chain`/`capture_*`）只被测试调用，未接入运行时。
4. **rank 动态分片不影响 seed 结论**：本次 0-1/1-4/4-28 只是 EXO 按内存动态切的一次实现；无论分片怎么变，节点"知道张量形状（执行时天然知道）+ seed 常量（源码里有）"⇒ 执行前即可精确复现 verifier 将检查的坐标（A1.2：72/72）——这是 `node_sees_before_exec` 的直接时序证据。

---

## 2. A1.2 实证重构测试（把"结论"变"证明"）

**方法**：只凭公共信息（seed 常量 + 张量形状）重构 verifier 的抽查坐标，与真实 `materialize_policy` / `capture_*_sketch` 物化坐标逐比对；同时全量扫描运行时随机 seed 源。

**结果**（`workspace/V0-2/results/a12/seed_reconstruction_audit.csv`，720 池 6 prompts × C1/C2/C3）：

| 证据 | 结果 |
|---|---|
| P1/P2（SHA256-verifier 派生）重构 vs 真值 | **72/72 全匹配**（坐标哈希逐位一致） |
| P3（SR 主表 `default_rng(2026)`）分数等价 | **score_equiv=True**（重构坐标手算分数 == `signradial_score` 输出，如 fn=2.0368e-03==manual） |
| 跨路径一致性（同 seed 同 q） | **18/18 不一致**：SR 主表 `default_rng` 派生 ≠ verifier `SHA256("accountedge-e2:…")` 派生 |
| 运行时随机 seed 源扫描 | **0 个 sketch-seed 相关**（`os.urandom` 是加密 nonce、`secrets` 是身份 token/常数时间比较、`time.time` 是进度计时器） |

**解读**：攻击者只凭源码 + 形状即可复现 verifier 的全部抽查坐标（72/72），SR 主表也分数等价——**seed 非保密已实证坐实**。

**额外发现（跨框架 seed 语义未统一）**：SR 主表用 `np.random.default_rng(2026)` 直接抽样；P0-E2 verifier / 线上 TSTC 用 `SHA256("accountedge-e2:{seed}:{purpose}")` 包装后再抽样。**同 seed 下两者坐标不同**。这是 seed 派生未统一的实现缺陷，论文若写"统一 seed 协议"会与实现不符。

---

## 3. A1.3 后果量化（知道 seed 值多少；最小实证，完整矩阵归 E2-R）

**方法**：720 池（200 calib / 520 eval，ref=stack_a left，cand=attacked stack_b right），SR 链式 max over C1/C2/C3，Γ=Q_0.99(calibration honest)，统一 1% FPR。攻击只扰动 C2：sign-balanced（`sign(x_ref)ᵀe=0`，c=0.5）、tolerance-hug（校准到 verifier 实际分数=(1−δ)Γ，δ=0.05）。KNOWN = 攻击 seed==verifier seed；SECRET = seed≠。主表 seed=2026。

**结果**（`workspace/V0-2/results/a13/seed_secrecy_gain.csv`）：

| q | 攻击族 | KNOWN TPR | SECRET TPR | protective_gain |
|---|---:|---:|---:|---:|
| 64 | sign_balanced | 0.0096 ≈FPR（全逃避） | **0.2942** | **+0.285** |
| 64 | tol_hug | 0.0077 | 0.0077 | 0.000 |
| 256 | sign_balanced | 0.0192 ≈FPR | **0.2942** | **+0.275** |
| 256 | tol_hug | 0.0173 | 0.0731 | +0.056 |

**解读**：
1. **坐标保密对 sign-balanced 盲点价值显著**：KNOWN 把抽查坐标上 `sign(x)ᵀe=0` 精确清零→SR 分数≈honest drift→完全逃避（TPR≈FPR）；SECRET 只能在错误坐标上清零→checked coords 留下 overlap residue→~29% 检出。**protective_gain≈+0.28（q=64 与 256 一致）** → commit-then-challenge 的坐标保密对 SR 的 sign-null 盲点有实质增益。
2. **坐标保密对稀疏 tolerance-hug 价值≈0**：KNOWN 精确贴 (1−δ)Γ 逃避；SECRET 扰动落在 verifier 不查的坐标→隐身→同样逃避。**注意：SECRET 的"逃避"可能是扰动过弱/无实质危害**——是否真危害需 harm proxy 判定，这正是 E2-R 的职责，本实验不越界。
3. **异常/口径**：evalHonestFPR 在 q=64/seed=2026 为 0.96%（与主表一致），q=256 升到 1.92%——**sketch 分辨率 q 越高，跨设备 honest 分布尾部越宽、1% 校准越不稳定**。主表 q=64 的 0.96% 是 tighter 的。此点已在 §4 记录。
4. **SECRET TPR 的绝对量依赖具体 seed 实现**（seed=1 时 sign_balanced SECRET=0.55，seed=2026 时=0.29）——overlap residue 是随机实现；稳健结论是**方向与量级**（gain 显著 > 0 且两 q 一致），不是某个 seed 的精确值。

### 3.5 保密边界：seed 可见已覆盖、P 可见未做、commit-then-reveal 可两者皆隐

**seed 不可见是**可做到**的**：commit-then-reveal（先绑定输出、后揭示抽查坐标）即可让 seed 不可见——这正是新协议的核心主张（08.08 手册 §0.3 归档为 future work）。**E2-R 已有 seed 可见/不可见的定量对比**：TM-1（seed 保密）/ TM-2（seed 已知）两威胁模型，坐标保密值 +0.03~+0.70（ρ 依赖，SR 通道，E2R_AUDIT 已审计）。

**P（投影矩阵）的可见性还没做**：
- E2-R 两个威胁模型都假设 **P 公开**（手册 §2.2"共同已知：…投影 R…"；E2R_AUDIT 已拍板 P 公开，理由含"P 是固定矩阵、揭示一次永久泄露、知识性保密不自洽"）。
- **P 可见 vs 不可见没有实验对比**；E2R_AUDIT 留了 future work："ProjCos 若要受益于坐标保密 → 改为行采样设计"。

**commit-then-reveal 可让 seed 与 P 都不可见**：若 P 也按每任务派生（`P = PRF(K, request_id‖layer)`，非固定矩阵），则 reveal 阶段才揭示 P——攻击者在 commit 前**两者皆不可见**，无法针对抽查坐标或投影矩阵任一项构造。此时 P 的保密从"知识性秘密"（固定矩阵、揭示一次永久泄露）转为"时间性秘密"（每轮刷新），与 seed 同类；公开可验证性由"reveal 后任何人可复算"保持。**代价**：需在"藏 P 的检测力 vs 公开可验证"之间权衡（E2R_AUDIT 拍板时评估过藏 P 只把 PC 从 blind 抬到 partial、不闭合结构性盲点）——是否值得是 E2-R/设计侧的待评估项。

---

## 4. 异常与坑

1. **A1.3 tolerance-hug 初版构造缺陷**：只校准攻击项 `c·num_nonzero`，忽略 honest drift `Σsign(left)(right−left)`，导致 KNOWN 分数超阈值（TPR=0.65）。修复为校准 verifier **实际分数**（含 drift）到 (1−δ)Γ——这要求攻击者知道 left 参考（白盒最强假设），已在脚本注释与本文 §3 标注该假设。
2. **eval FPR 对 q 敏感**：q=64→0.96%，q=256→1.92%。写主稿时若换 q 需同步重校准阈值。
3. **SR 主表与 verifier 的 seed 派生不一致**（`default_rng` vs SHA256 包装）——跨框架坐标不同，seed 语义未统一（§2 额外发现）。
4. **线上 TSTC 未接入运行时**：challenge/reveal/verify 全部是离线脚本 + 测试，无在线实现。这本身是论文必须诚实陈述的空白（§4 verifier 规格输入）。

---

## 5. 一句话结论

**`node_sees_before_exec`**：当前实现中 seed 是公共常量（0/2026/9527），无 PRF、无协调方持有的密钥、无承诺机制；A1.2 实证 72/72 复现 verifier 精确坐标、随机 seed 源为 0。现有协议下执行节点可在执行前算出全部抽查坐标——这是现有设计的**真实弱点**，必须写进论文已知局限；同时它定量支撑 commit-then-challenge 坐标保密对 SR 盲点的增益（A1.3：sign-balanced protective_gain≈+0.28）。

## 6. 本次没做的部分

- 全 TM1/TM2 × 6 攻击族矩阵（E2-R，8/12）
- tolerance-hug 的 harm proxy 交叉验证（E2-R 职责）
- 对多 seed 平均的稳健 protective_gain（本实验给单 seed 方向性结论）
- **P（投影矩阵）可见 vs 不可见的对比实验**（未做；E2-R 两个威胁模型都假设 P 公开，P 保密仅存在于 commit-then-reveal 的 per-task P 设想，见 §3.5）
- 主稿 §3.3 的形式化重写（写作侧）
