# VeriEdge 路线 B 学生研究与实验手册

**文档日期：** 2026-09-03  
**适用对象：** 负责系统实现、实验设计、数据采集和结果整理的研究生  
**目标论文：** *VeriEdge: Risk-Adaptive Verification for Cross-Provider LLM Inference at the Edge*  
**系统名称：** VeriEdge  
**核心协议：** PACT（Post-commit Activation Consistency Test）  
**当前实现候选：** PACT-G16  
**当前阶段：** 核心几何和本地协议原型已完成；参考执行、真实校准、语义攻击和三节点集成尚未完成

---

## 0. 先读这一页

这不是一份“看看方向”的备忘录，而是一份可以直接照着执行的研究手册。你的工作不是继续为现有结果补一些图，而是依次回答四个生死问题：

1. VeriEdge 是否存在明显低于 always-on duplicate execution 的成本区间？
2. PACT 能否在足够多的独立 prompt 上控制诚实任务误报，而不是依靠小样本或大量 `INCONCLUSIVE`？
3. PACT 能否检测真正改变生成结果的未知 seed、承诺后语义攻击？
4. 上述机制接入三节点异构运行时后，是否仍有可用的延迟、吞吐和资源开销？

必须按 `G0 -> G1 -> G2 -> G3 -> G4` 的门控顺序推进。没有通过前一阶段，不要提前做昂贵的系统集成或大规模 baseline。

本手册中的第一张工单是 `RB-G0-01`，位于第 9 节。新同学完成第 7 节的入门复现后，应立即开始该工单。

### 0.1 文档优先级

出现冲突时按以下顺序处理：

1. `docs/VERIEDGE_ROUTE_B_RESEARCH_HANDBOOK_2026-08-24.md`：科学结论、主张边界和总路线的权威账本。
2. 本手册：学生执行、文件组织、交付物和验收规则的权威入口。
3. `docs/ROUTE_B_REDESIGN_PACT_2026-08-24.md`：PACT 协议和统计设计规范。
4. `experiments/pact_offline/*_RESULTS_2026-08-24.md`：已完成实验的证据记录。
5. `legacy_veriedge_eurosys/` 和 `docs/ROUTE_B_STRONG_CHECK_DESIGN_2026-08-24.md`：历史材料，只读，不作为当前设计规范。

如果发现新数据与 8 月 24 日总账冲突，不要静默改口径。先提交冲突说明、原始结果和复现命令，再由负责人更新科学账本。

### 0.2 你的权限边界

你可以：

- 在路线 B 的 `experiments/` 下新建实验目录、脚本、配置和结果；
- 在 `docs/` 下新增带日期的实验设计、结果备忘和工单；
- 复用 `shared/` 中的数据、prototype 和采集模板；
- 从路线 A 复用攻击作为 baseline，但必须标明来源，不能把路线 A 的发现重复写成路线 B 的新贡献。

你不可以：

- 修改路线 A 的论文主张或把路线 A 的资产搬成路线 B 独占贡献；
- 在 `legacy_veriedge_eurosys/` 上继续开发新主线；
- 把 `pcra_offline_retired/` 恢复成当前方案；
- 把假设数字写成实测数字；
- 把 timeout、缺失回执或统计支持不足记成 `PASS`；
- 未经批准改变威胁模型、目标 FPR、harm floor 或 Go/No-Go 标准。

---

## 1. 项目背景：路线 A 发现了什么，路线 B 要解决什么

### 1.1 应用场景

VeriEdge 面向跨提供方的边缘 LLM 推理。一个模型被切成多个 shard，依次部署在硬件、后端和精度不同的提供方上。上游 provider 产生边界激活，下游 provider 消费该激活并继续执行。

系统希望验证每个 provider 是否按承诺执行，但有两个根本困难：

- 诚实的异构执行存在浮点漂移，因此不能直接比较张量哈希或要求逐 bit 一致；
- 低成本 verifier 只观察高维激活的低维摘要。若攻击者在提交输出前知道该摘要映射，它可以把扰动放入 verifier 的零空间。

### 1.2 路线 A 的结论

路线 A 当前论文是：

> *AccountEdge: A Detection Ceiling for Low-Rank Checkpoint Sketches in Sharded Edge LLM Inference*

路线 A 研究固定、低秩 checkpoint sketch 的检测上限。其核心不是“某一个统计量不好”，而是一个结构性事实：若 verifier 只观察残差 `e in R^N` 的固定低秩像 `A e`，那么 `ker(A)` 中的扰动对 verifier 完全不可见。

在论文实测实例中，`T=12`、`D=1024`、ProjCos reveal dimension `d=4`，SignRadial 与 ProjCos 的联合观测 rank 为 49，blind subspace dimension 为：

`12 * 1024 - 49 = 12,239`。

盲空间占比超过 99.5%。路线 A 的 `joint_null` 攻击在全部测试强度下保持在误报率附近，同时显著改变生成结果：32-token continuation 仅保留约 3%--14% 的位置一致性。需要注意：路线 A 只对 `joint_null` 支持“任意测试强度仍结构性盲”的强解释；`tol_hug_combined` 是被阈值限制在约 `rho_eff=0.009`，两者不能合并表述。

路线 A 的后续 harm-aware 理论进一步给出：对危害梯度 `g` 和预算 `R`，精确盲空间内的最大一阶危害为：

`R * ||P_ker(A) g||_2`。

这说明“大 kernel”只是容量结论，真正的 harm 取决于危害梯度与 verifier row space 的对齐。路线 B 可以把这一结论作为设计动机和攻击 baseline，但不能把它作为自己的首要贡献。

### 1.3 路线 A 留给路线 B 的设计规则

路线 A 的关键正面发现是：决定低维检查是否有用的属性不是模糊的“经常刷新”，而是：

> **unpredictability at attack commitment**：攻击者固定并绑定本次输出时，不能知道本任务最终使用的检查随机量。

固定投影即使暂时保密，也会在泄露后永久失效；每任务重新产生、且只在输出承诺后产生的随机量，才迫使攻击者每次都面对未知挑战。

### 1.4 路线 B 的任务

路线 B 不是再证明一次检测上限，而是给出正向系统答案：

> 如何把承诺后随机挑战、独立参考执行、异构漂移校准、三态裁决和风险自适应审计组合成一个可部署的跨提供方验证系统？

路线 B 的目标主张是：

> VeriEdge 将跨任务的不可预测承诺后审计，与任务内支撑不变、边界自适应的 PACT 检查结合，使异构边缘 LLM 流水线能够以风险可计价的平均成本完成跨提供方验证。

### 1.5 旧路线 B 论文与新路线 B 的区别

`legacy_veriedge_eurosys/main_eurosys.tex` 是被拒的旧 EuroSys 论文。它的主线是 verifiability-constrained placement、selective delivery 和 TSTC。旧稿提供了大量可复用资产：异构 verifier profile、placement replay、delivery sweep、TSTC 实现经验和系统图。

它不是当前 PACT 论文。当前路线 B 尚没有一份完整的新论文 TeX，只有研究总账中的论文骨架。新论文不能写成旧稿的小修重投：

| 旧 EuroSys 主线 | 当前路线 B 主线 |
|---|---|
| placement 决定可验证性 | 风险自适应审计决定何时产生参考证据 |
| 固定 TSTC sketch | 输出承诺后派生一次性 PACT challenge |
| bounded challenge evidence | `PASS/FAIL/INCONCLUSIVE` 与升级 |
| selective delivery | reference path 的隐私和状态约束 |
| 普通 material tamper | 未知 seed、EOT、语义危害攻击 |

旧数据进入新论文前必须重新核对协议、硬件、模型、边界和 workload，不能直接复制数字。

---

## 2. 研究问题、威胁模型和非目标

### 2.1 研究问题

路线 B 要回答六个研究问题：

- `RQ1 Reference economics`：V1/V2/V3 的参考执行成本和风险分别是多少？
- `RQ2 Honest calibration`：在独立 prompt 和真实异构运行上，任务级 FPR 是否受控？
- `RQ3 Semantic attacks`：PACT 能否检测或升级真正有害的未知 seed 攻击？
- `RQ4 Runtime`：三节点运行时的延迟、吞吐、内存、网络和证据成本是多少？
- `RQ5 Adaptivity`：风险自适应策略是否优于固定 `p_a`、固定 `K` 和 always-on duplicate？
- `RQ6 Baselines and scale`：相对 TSTC、PCRA、TOPLOC、DiFR、TensorCommitments/TAO 类方案，VeriEdge 的不可替代点是什么？

### 2.2 攻击者能力

恶意 shard provider 可以：

- 知道模型、协议、投影族、阈值、审计策略形式和升级规则；
- 离线优化任意攻击，并对未来 challenge 分布做 EOT；
- 修改模型、精度、算子、边界张量或运行状态；
- 试图预测审计、磨 root、复用回执、替换上下文、延迟或拒绝 reveal；
- 在张量承诺后看到 seed。

恶意 provider 不可以在看到 seed 后替换已经承诺的张量。若协议或实现允许替换，则实验必须判为协议失败，而不是攻击太强。

### 2.3 最低信任条件

每个受检边界至少需要：

- 生产方与实际接收方不完全串谋，或另有独立 receipt witness；
- reference/replay path 不与恶意生产方串谋；
- challenge 随机源在攻击输出承诺时不可预测；
- 任务记录能阻止 root、身份、策略和终态被事后替换。

如果 producer、receiver 和 reference 全部串谋，基础 PACT 不提供保证。该情况只能通过第二 witness、TEE、完整重放或更强证明系统处理。

### 2.4 明确非目标

VeriEdge 不声称：

- 证明生成文本的语义正确性；
- 发明随机投影、JL/AMS sketch、哈希承诺或 conformal calibration；
- 消灭任意线性检查的零空间；
- 在 seed 于输出承诺前已知时仍然安全；
- 检测低于声明 materiality/harm floor 的攻击；
- 在没有独立 reference 或可信 replay 时证明执行正确；
- 防御 producer、receiver 和 reference 的完全串谋；
- 用当前 6 个 calibration prompt 支撑 1% 部署级 FPR。

---

## 3. VeriEdge 方法

### 3.1 两层风险控制

VeriEdge 把验证拆成两个不同问题。

第一层是跨任务审计调度：任务完成并承诺输出后，系统根据任务价值、provider 历史、边界风险、参考资源和成本预算，决定是否触发独立 reference。

第二层是任务内 PACT：对已经触发审计的边界，从较小 `K` 开始比较 actual/reference 投影；证据不足时扩展 `K`，仍不足则升级。

不能把二者混在一个 detection rate 中。报告结果时必须同时给：

- `conditional detection`：已审计任务上的 PACT 检测率；
- `overall detection`：任意恶意任务最终被发现的概率。

若审计概率为 `p_a`，PACT 条件漏检率为 `gamma_p`，则：

`p_detect_single = p_a * (1 - gamma_p)`。

同一 provider 连续作弊 `m` 次，且审计抽样独立时，至少一次被发现的概率为：

`p_detect_m = 1 - (1 - p_detect_single)^m`。

这是一种乐观审计保证，不是逐任务正确性保证。

### 3.2 四种保护模式

| 模式 | reference 行为 | 适用任务 | 必须如何解释 |
|---|---|---|---|
| V0 Record | 不主动生成 reference，只记录承诺 | 诊断、极低风险 | 不主动检测静默作恶 |
| V1 Sampled audit | 输出承诺后以不可预测概率 `p_a` 触发 reference | 常规任务 | 提供总体检测/威慑，不提供单任务保证 |
| V2 Per-task protection | 每个任务都生成独立 reference 或冗余边界 | 高价值任务 | 无跨任务抽样损失，成本可能接近复制执行 |
| V3 Strong upgrade | per-operator、full replay、TEE 或强证明 | PACT 不确定或极高风险 | 保证由具体升级机制定义 |

### 3.3 reference 的四种实现候选

| 候选 | 优点 | 主要代价/风险 | 当前角色 |
|---|---|---|---|
| full-model replay | 语义最清楚 | 成本最高，可能抹掉系统优势 | upper-cost baseline |
| shard-local replay | 只重放目标 shard，可能便宜 | 必须绑定输入激活、token position、mask、KV/cache 和版本状态 | 第一优先候选 |
| redundant shard | 调度第二 provider 执行同一 shard | 资源占用和串谋问题，可能接近复制 | 可实现 baseline |
| trusted/TEE referee | reference 身份清晰 | TEE 可用性、模型隐私和数据搬运成本 | 高保证候选 |

局部重放验证的是“该 shard 是否对它实际收到且已绑定的输入正确执行”，不是自动证明上游输入正确。逐边界检查应通过第一个失败边界完成定位。

### 3.4 PACT 协议时序

对任务 `task_id` 和边界 `boundary_id`：

1. 控制面预提交模型、shard map、受检边界、reference 身份、审计规则、PACT 版本、`K0/Kmax`、阈值、deadline 和升级规则。
2. producer 完成边界张量 `h`，按规范序列化并提交 `actual_root`。
3. receiver 对实际消费的字节计算 `receive_root`；不一致立即 `FAIL/FROZEN_CONFLICT`。
4. reference path 产生 `h_ref` 并提交 `reference_root`。
5. 只有在 roots 不可替换后，系统才生成 audit decision 和 task/boundary-specific seed。
6. seed 定义全覆盖矩阵 `A_s`；receiver 和 reference 分别计算 `y=A_s h`、`y_ref=A_s h_ref`。
7. 双方回执绑定 task、boundary、model、shape、dtype、roots、seed、K、coefficient digest、sketch bytes 和时间。
8. adjudicator 先验证上下文、身份、时序和签名，再计算统计量。
9. 结果为 `PASS`、`FAIL` 或 `INCONCLUSIVE`；不确定时扩展 K 或进入 V3。

安全单位是完整时序，不是“用了 Gaussian projection”。

### 3.5 PACT-G 的统计核心

设：

`v = h - h_ref in R^N`，

且 `v` 在 seed 生成前已经固定。理想 PACT-G 生成：

`A_s in R^(K x N), A[j,i] ~ N(0, 1/K)`。

令：

`F_2 = ||v||_2^2 / N`，

`T_K = ||A_s v||_2^2 / N`。

则有精确条件分布：

`K * T_K / F_2 ~ chi-square_K`。

因此，理想 Gaussian 下的检测分布取决于总 residual energy 和 `K`，不取决于攻击修改 1、16 还是 256 个坐标。这消除了 coordinate-opening 的 support-hit ceiling。

这条结论不解决 prompt-level honest drift，也不解决 known-seed 零空间攻击。

### 3.6 PACT-G16

PACT-G16 使用固定 65,536 项 inverse-CDF LUT，由 SHAKE256/XOF 产生 16-bit 索引。当前 LUT little-endian float32 字节的 SHA-256 为：

`8babbcaf96568f10165a1eab530c0e5c92d04de96761b6dbb3dadfa94baba37f`

理想 PACT-G 是定理模型，PACT-G16 是实现候选。G16 不能自动继承精确 chi-square 定理；必须使用有限表 concentration 论证或预注册的保守经验区间。

### 3.7 三态裁决

- `PASS`：在已提交风险预算下，residual 上界位于 honest envelope 内。
- `FAIL`：residual 下界超过 material discrepancy boundary，或出现 root、身份、签名、上下文、时序冲突。
- `INCONCLUSIVE`：区间重叠、校准不足或 execution signature 无有效 profile。

`INCONCLUSIVE` 必须扩展证据、升级或拒绝该 placement。绝不能静默转为 `PASS`。

### 3.8 状态机

当前本地原型的合法路径为：

`ROOTS_COMMITTED -> BEACON_COMMITTING -> BEACON_COMMITTED -> BEACON_REVEALING -> SEED_READY -> RECEIPTS_PENDING -> ADJUDICATED`

终态还包括：

- `ABORTED`：commit/reveal/receipt 超时或缺失；
- `FROZEN_CONFLICT`：同一角色提交冲突回执、root 或上下文。

SQLite 原型只证明本地事务和重放控制，不是 Byzantine 或 tamper-evident 公共账本。

---

## 4. 已建立的事实和仍未建立的事实

### 4.1 已建立

| 结论 | 当前证据 |
|---|---|
| coordinate opening 对稀疏攻击受 support-hit ceiling 限制 | PCRA 结果：`q=64,rho=.05` 检测 9.70%；`q=512` 检测 36.26%，FPR 已到 13.80% |
| Rademacher 全覆盖但小 K 有 shape effect | `K=1,rho=.02` support spread 26.0pp；`K>=32` 小于 0.9pp |
| 理想 Gaussian 近似支撑不变 | 21 个 `(K,rho)` 设置最大 support spread 0.70pp |
| known seed 会恢复零空间攻击 | `K=8/32/64`、三个 rho 下 attack detection 与 honest detection 完全相同 |
| K 必须边界感知 | `rho=.01`、95% power：C1 max K=19，C2=20，C3=928 |
| adaptive K 能节约容易样本证据 | C1/C2 `rho=.02` 平均 K 约 8.3；C3 `rho=.02` 平均 K 约 50 |
| 当前校准不足 | 仅 6 个独立 calibration prompt；C3 infinite-K honest exceedance 33.3% |
| LUT16 接近理想 Gaussian | 最坏 support spread 0.368%；本地比 online Gaussian 快约 37%--43% |
| transcript 的绑定逻辑可执行 | 六个真实边界通过，prefix expansion 和上下文扰动检查通过 |
| 本地状态机能拒绝 replay/conflict/late evidence | 15 条正常、攻击和重启路径全部通过 |

### 4.2 尚未建立

- 参考执行的真实经济性；
- 1% task-level FPR；
- 对真实语义攻击的检测或升级能力；
- PACT-G16 的跨硬件一致性；
- Ed25519/public signature、真实 beacon 和公共 durable record；
- 三节点端到端开销与吞吐；
- risk-adaptive policy 的 Pareto 优势；
- 相对强 baseline 的公平比较。

任何论文段落都必须从这两张表中判断自己是在写“事实”还是“目标”。

---

## 5. 资产地图

### 5.1 路线 A：只读科学背景和攻击证据

| 资产 | 路径 | 用途 |
|---|---|---|
| 当前路线 A 论文 | `route_a_detection_ceiling/paper/main_accountedge_ndss2027.tex` | detection ceiling、harmful evasion、refreshability |
| 路线 A PDF | `route_a_detection_ceiling/paper/main_accountedge_ndss2027.pdf` | 与 TeX 对照阅读 |
| evidence ledger | `route_a_detection_ceiling/docs/evidence_ledger.md` | claim/anti-claim/红线 |
| 学生实验手册 | `route_a_detection_ceiling/docs/NDSS27_STUDENT_EXPERIMENT_HANDBOOK.md` | 交付格式和实验纪律参考 |
| harm-aware 理论 | `route_a_detection_ceiling/docs/ROUTE_A_HARM_AWARE_THEORY_LAYER1_2026-08-24.md` | `R||P_ker(A)g||` 与攻击 baseline |
| 完整审计 artifact | `route_a_detection_ceiling/artifacts/expanded_remote_audit_artifact/` | 原始捕获、prototype、summary CSV、绘图脚本 |

路线 A 论文中的攻击数字可用于动机和对照，但路线 B 必须在 PACT 的未知 seed 时序下重新运行攻击，不能把路线 A 的 known/fixed-check 结果当作 PACT 结果。

### 5.2 路线 B：当前主线

| 资产 | 路径 | 状态 |
|---|---|---|
| 项目总账 | `docs/VERIEDGE_ROUTE_B_RESEARCH_HANDBOOK_2026-08-24.md` | 当前权威 |
| PACT 设计 | `docs/ROUTE_B_REDESIGN_PACT_2026-08-24.md` | 当前权威 |
| PACT 代码与报告 | `experiments/pact_offline/` | 活跃 |
| PACT 机器可读结果 | `experiments/pact_offline/results/` | 活跃，保留原始版本 |
| PCRA | `experiments/pcra_offline_retired/` | 已退役，只做负 baseline |

### 5.3 路线 B：共享和继承资产

`shared/accountedge_runtime_and_captures/` 包含：

- `raw_captures/e2_live_subset/`：两栈、6 calibration + 12 eval 的匿名原始子集；
- `data/`：旧论文的 verifier profile、placement、delivery summary；
- `prototype/`：接口级 orchestrator/PPD/TSTC/ledger smoke demo；
- `data_collection/`：单机 HF 或 synthetic 采集示例；
- `multi_node_runner/`：匿名 SSH/rsync dry-run 模板；
- `scripts/` 和 `figs/`：旧论文复现和绘图资产。

必须注意三个限制：

1. `data/verifier_profiles.csv` 中有旧实验的 200 calibration/200 eval 汇总，但完整 raw tensor corpus 不在当前共享目录，不能直接用于 PACT-G residual-energy 校准。
2. `stack_02_rerun_eval_12` 与 `stack_02_eval_12` 的 NPZ 按 hash 完全相同，不是独立重跑。
3. `prototype/` 是接口 smoke demo，`multi_node_runner/` 是采集模板；二者都不是当前可直接声称的生产级三节点 VeriEdge。

### 5.4 路线 B：历史资产

`legacy_veriedge_eurosys/` 包含旧论文 TeX/PDF、placement/delivery/TSTC 数据和实验交付。它适合：

- 提取旧 runtime 接口和系统图；
- 复用 workload trace 和 candidate profile 格式；
- 构造 TSTC、duplicate execution 和 placement baseline；
- 查找硬件、网络和实验组织经验。

它不适合：

- 直接写入新论文结果；
- 继续扩展 fixed-sketch TSTC 作为新方案；
- 依据旧 FPR/TPR 声称 PACT 已完成校准。

### 5.5 本地相关工作

- `2501.16007v2.pdf`：TOPLOC，top-k activation locality-sensitive hash 和 reference recomputation。
- `2509.24257v4.pdf`：VeriLLM，commit/re-verification、teacher-forced verification 和激励机制。
- `2511.20621v1.pdf`：DiFR，Token-DiFR 与 Activation-DiFR；后者使用随机正交 projection 压缩 activation。

比较时要区分“论文报告结果”“我们复现实测结果”和“概念差异”。未运行对方代码时只能写前两者中的第一种。

---

## 6. 文件和数据规范

### 6.1 新实验目录

每个工作包在路线 B 内建立独立目录：

```text
experiments/
  reference_economics/       # WP0
  calibration_corpus/        # WP1
  semantic_attacks/          # WP2
  veriedge_runtime/           # WP3
  risk_policy/                # WP4
  baselines/                  # WP5
```

不要把新结果写进 `legacy_veriedge_eurosys/`、`shared/` 或已有 `pact_offline/results/`。

### 6.2 每次实验的 run 目录

```text
results/<experiment>/<RUN_ID>/
  command.txt
  config.json
  environment.json
  manifest.csv
  raw/
  summary/
  figures/
  checks.json
  RESULT_MEMO.md
```

`RUN_ID` 建议格式：`YYYYMMDD_HHMM_<short_name>`。任何图必须能由该 run 内的机器可读表重新生成。

### 6.3 每个数的来源标签

所有成本和风险输入必须带一个标签：

- `measured`：由本次真实运行得到；
- `derived`：由 measured 数据和明确公式计算；
- `assumed`：用于参数扫描，不是实测；
- `reported_external`：来自他人论文；
- `legacy_measured`：来自旧 VeriEdge/AccountEdge 实验，尚未按新协议复核。

图表不得把这些类别混成一条无标记曲线。

### 6.4 execution signature

一个 calibration profile 至少绑定：

```text
model_id + model_snapshot/hash
boundary definition/layer range
producer device/backend/precision
reference device/backend/precision
framework + library + driver versions
kernel/quantization configuration
tokenizer version
tensor shape/dtype/serialization
PACT coefficient family/version
accumulation dtype/order
```

任何字段发生会影响数值行为的变化，都应生成新 signature 或触发 profile expiration。

---

## 7. 入门复现：第一天必须完成

以下命令都从仓库根目录执行。active PACT 脚本的默认数据路径已在本次手册整理中修复；为使实验输入一眼可审计，本手册仍显式传入数据路径。

### 7.1 设置当前 PowerShell 会话变量

```powershell
$RouteB = if (Test-Path "research_routes/route_b_veriedge_system") {
  "research_routes/route_b_veriedge_system"
} else {
  "."
}
$Pact = "$RouteB/experiments/pact_offline"
$Data = "$RouteB/shared/accountedge_runtime_and_captures/raw_captures/e2_live_subset"
```

### 7.2 检查环境

```powershell
python --version
python -c "import numpy, scipy, matplotlib, pandas, yaml; print('dependencies-ok')"
```

若缺包，在项目虚拟环境中安装：

```powershell
python -m pip install numpy scipy matplotlib pandas pyyaml
```

记录 Python、NumPy、SciPy、BLAS 和操作系统版本。不要在不同环境中混合 timing 结果。

### 7.3 验证 raw capture

```powershell
Push-Location "$RouteB/shared/accountedge_runtime_and_captures"
python "scripts/validate_raw_captures.py"
Pop-Location
```

预期：manifest 中所有 NPZ 存在、hash 匹配、每个文件包含 `prefill__C1/C2/C3`，张量为数值类型。

### 7.4 运行最小 PACT smoke

```powershell
python "$Pact/pact_projection.py" --smoke `
  --data-root "$Data" `
  --output "$Pact/results/onboarding_smoke"
```

检查输出至少包含 thresholds、pair-level rates、aggregate rates 和 metadata。smoke 只用于确认代码路径，不得作为论文数字。

### 7.5 运行协议和状态机

```powershell
python "$Pact/pact_g16_protocol.py" `
  --data-root "$Data" `
  --output "$Pact/results/onboarding_g16_protocol" `
  --repeats 2

python "$Pact/pact_g16_state_machine.py" `
  --data-root "$Data" `
  --output "$Pact/results/onboarding_g16_state_machine"
```

预期：LUT hash 固定；六个真实边界可完成 receipt/adjudication；状态机 15 条路径通过；timeout 进入 `ABORTED`，冲突进入 `FROZEN_CONFLICT`。

### 7.6 入门交付

在 `docs/` 新增 `YYYY-MM-DD_ROUTE_B_ONBOARDING_REPORT.md`，只需包含：

- 实际运行命令；
- 环境版本；
- raw capture 校验结果；
- smoke、protocol、state machine 是否通过；
- 与已有报告不一致的任何数值；
- 阻塞项。

通过条件：所有命令可执行且能解释为什么 6 calibration prompt 不能支撑 1% FPR。未通过时先修复路径或环境，不进入 WP0。

---

## 8. 总体执行路线

| Gate | 工作包 | 核心问题 | 未通过时 |
|---|---|---|---|
| G0 | WP0 Reference economics | 系统是否有低于复制执行的可行区间 | 停止大规模系统投入 |
| G1 | WP1 Calibration + WP2 Semantic attacks | 统计上能否区分 honest 与 harmful attack | 降级到协议/分析工作 |
| G2 | WP3 Three-node runtime | 机制接入后是否仍有系统优势 | 重做数据路径或停止 |
| G3 | WP4 Policy + WP5 Baselines | 自适应策略是否形成 Pareto 优势 | 去掉 Risk-Adaptive 强主张 |
| G4 | WP6 Theory/paper/artifact | 主张、证据、实现是否闭环 | 不投稿强系统论文 |

WP1 和 WP2 可以在 G0 通过后并行。WP3 必须等待 G0 和 G1 的主要结论，不要先花数周搭系统再发现参考经济性或校准不成立。

---

## 9. 工单 RB-G0-01：reference 架构与经济模型

### 9.1 目标

用最小实现和可审计模拟回答：在哪些 workload、任务价值和攻击模式下，V1/V2 的平均验证成本显著低于 always-on duplicate，同时达到预声明风险目标？

预计研究工作量：5 个工作日。第一轮只求 Go/No-Go，不做完整运行时。

### 9.2 输入资产

- `docs/VERIEDGE_ROUTE_B_RESEARCH_HANDBOOK_2026-08-24.md` 第 5.3、9.1、10/WP0 节；
- `experiments/pact_offline/results/conditional_power/`；
- `experiments/pact_offline/results/adaptive_gaussian/`；
- `experiments/pact_offline/results/g16_protocol/`；
- `shared/accountedge_runtime_and_captures/data/placement_workload.csv`；
- 旧论文中的 replay/delivery/runtime 数字，只能标 `legacy_measured`。

### 9.3 新建目录

```text
experiments/reference_economics/
  README.md
  configs/
    reference_modes.csv
    risk_targets.json
  simulate_reference_economics.py
  tests/
    test_risk_equations.py
  results/
  REFERENCE_MODE_FEASIBILITY.md
  WP0_REFERENCE_ECONOMICS_MEMO.md
```

### 9.4 Task A：reference mode 可行性审计

对 full-model replay、shard-local replay、redundant shard、trusted/TEE referee 分别填写：

- 验证单位：full task、single shard、single boundary 或 operator；
- reference 从哪里开始执行；
- 需要保存和绑定哪些状态；
- 是否需要 prompt plaintext、embedding、boundary activation、token positions、attention mask、KV/cache；
- reference 是否能在输出承诺后才知道被审计任务；
- 是否支持异步、batch 或 cache amortization；
- producer、receiver、reference 的串谋边界；
- 计算、网络、存储、等待和隐私成本；
- 当前仓库中可复用的代码；
- 缺失代码、模型、硬件和凭证；
- 最小可运行实验；
- 明确的 bypass 风险。

交付 `REFERENCE_MODE_FEASIBILITY.md`。每一格写事实或 `UNKNOWN`，不要凭感觉填“低成本”。

### 9.5 Task B：统一成本模型

实现：

`C_task = C_commit + p_a * (C_ref + C_PACT(K,boundary)) + p_upgrade * C_upgrade`

至少拆分：

- `C_commit`：actual/reference root、接收端 root、签名与状态记录；
- `C_ref`：reference compute、输入/状态搬运、排队和冷启动；
- `C_PACT`：projection、receipt、adjudication、证据字节；
- `C_upgrade`：full replay/per-operator/TEE；
- tensor retention 的 memory-time product；
- clean 与 attack workload 的不同升级率。

输入表 `reference_modes.csv` 至少含：

```text
mode,component,value,unit,source_type,source_path,notes
```

不能只给一个“overhead %”。必须保留各组件原始单位，再派生任务级比例。

### 9.6 Task C：统一风险模型

模拟至少包含：

- `p_a in {0, .001, .002, .005, .01, .02, .05, .1, .2, .5, 1}`；
- `m in {1, 5, 10, 50, 100}` 次连续作弊；
- C1/C2/C3 分开；
- `rho in {.01, .02, .05}` 作为已有数值 baseline；
- `gamma_p` 来自 conditional-power/adaptive-K 结果，缺失时用明确标记的参数扫描；
- V0/V1/V2/V3；
- normal/high-value 两类任务；
- clean provider 与不同作弊频率。

必须输出：

- 单次恶意任务检测概率；
- 连续 `m` 次作弊至少一次被发现概率；
- 每任务平均、P95 和 worst-case 验证成本；
- reference compute 占比；
- expected undetected harm，若没有可用 harm 数据则保留为参数，不得造数；
- 相对 always-on duplicate 的成本比。

### 9.7 Task D：实现和自检

`simulate_reference_economics.py` 必须：

- 所有输入来自配置文件；
- 固定并记录随机种子；
- 不把 missing value 自动替换成 0；
- 输出长表 CSV，不只输出图片；
- 每个数字保留 `source_type`；
- 对公式边界写测试。

最低测试：

- `p_a=0` 时 active detection 为 0；
- `p_a=1,gamma_p=0` 时单次检测为 1；
- `m` 增大时 cumulative detection 不下降；
- `p_a` 增大时平均 reference cost 不下降；
- V2 等价于 `p_a=1` 的覆盖语义；
- V0 不得被标成提供主动正确性保证。

### 9.8 机器可读输出

```text
results/<RUN_ID>/
  mode_cost_grid.csv
  risk_curves.csv
  workload_summary.csv
  pareto_frontier.csv
  go_nogo_summary.json
  fig_cost_vs_risk.pdf
  fig_cost_vs_risk.png
```

### 9.9 结果 memo 必须回答

1. 第一种可实现的 reference mode 是什么？
2. shard-local replay 需要绑定哪些状态？其状态成本是否接近 full replay？
3. 是否存在使 V1 同时满足成本和风险目标的 `p_a` 区间？
4. 对高价值单次任务，V2 是否实质退化为 duplicate execution？
5. 哪些结论来自实测，哪些只是参数敏感性？
6. WP0 的结论是 `GO`、`CONDITIONAL_GO`、`NO_GO` 还是 `BLOCKED`？

### 9.10 通过和停止条件

`GO`：至少一个可实现 reference mode 在有意义 workload 区间内，平均验证成本明显低于 always-on duplicate，并达到预声明风险目标。

`CONDITIONAL_GO`：只有在一个明确待测组件落入给定成本上限时成立；memo 必须给出该组件和上限。

`NO_GO`：有意义的单任务风险目标都迫使 `p_a` 接近 1，且 reference 无法局部化或摊销；或 shard-local replay 的状态/计算等价于 full replay。

`BLOCKED`：缺失真实 runtime、模型或状态接口，无法判定。必须列出精确缺失项和最小解锁实验，不能只写“需要更多数据”。

---

## 10. WP1：独立 honest corpus 与校准

### 10.1 目标

建立足以支持 deployment-level task FPR 的原始 tensor corpus、execution signature 和冻结阈值。当前 6-prompt 数据只能做几何 smoke。

### 10.2 先做资产缺口审计

当前 `data/verifier_profiles.csv` 虽含旧 200/200 汇总，但没有对应完整 raw tensors。先确认以下三种路径中的哪一种成立：

1. 找回原始完整 capture corpus；
2. 在可用模型和硬件上重新采集；
3. 若只能得到 summary，则明确判定不能用于 PACT-G 校准。

提交 `CORPUS_ASSET_AUDIT.md`，记录每个目录、文件数、prompt 数、hash、模型和硬件来源。不要把 summary row 数误当成 raw prompt 数。

### 10.3 主 signature 的建议规模

第一轮只选择一个最重要 execution signature，避免一开始铺满笛卡尔积：

- calibration：建议 200--500 个独立 prompts，绝对最低 99；
- held-out：若只看 1% 点估计，至少 100；若要在 0 次 false failure 时让单侧 95% 上界不超过 1%，至少需要 299 个独立 held-out tasks，因此强论文建议 300 或更多；
- runtime repeats：选择至少 30 个 prompts，每个默认真实重跑 5 次；资源不足时可先 3 次并上报。

重复运行用于估计 runtime nondeterminism，不能增加 independent-prompt 样本量。

### 10.4 prompt split

在运行前冻结：

- prompt 来源和许可证；
- 去重规则；
- token-length 范围和任务类别；
- calibration/held-out/repeat 的划分；
- 基于 prompt canonical hash 的 split 方法；
- 不允许因结果不好而移动 prompt。

同一 canonical prompt 的改写、重复 seed 或复制文件不得跨 split。

### 10.5 capture 格式

每个 prompt 每个 stack 至少保存：

```text
captures/<split>/<stack>/<prompt_id>.npz
  prefill__C1
  prefill__C2
  prefill__C3

metadata.jsonl
  prompt_id
  prompt_hash
  split
  model_id/model_hash
  tokenizer_hash
  stack_id
  execution_signature
  checkpoint layer definitions
  tensor shape/dtype
  run_id/repeat_id
  start/end timestamp
  software/hardware versions
```

prompt plaintext 若有隐私限制，可独立受控保存；实验目录至少保留不可逆 prompt hash 和公开来源 ID。

### 10.6 校准方法

每个 boundary/signature 分开计算 honest full residual energy。至少报告：

- empirical distribution 和极值；
- split-conformal 阈值；
- parametric tail model 作为可选对照，但不能伪装成 distribution-free；
- boundary-specific threshold；
- task-level 多边界组合规则；
- profile shift 前后结果；
- `PASS/FAIL/INCONCLUSIVE` 比例。

对于 one-sided split conformal，`n` 个独立 calibration scores 的最细非零 miscoverage 分辨率是 `1/(n+1)`。`n<99` 时不得声称非平凡的 1% distribution-free threshold。

任务级控制推荐同时报告两种实现：

1. 对 C1/C2/C3 分配预提交 `alpha_k`，再做 union-bound composition；
2. 对固定边界集直接校准一个 task-level max-normalized score。

不要在看完 held-out 后选择更有利的一种作为唯一结果。

### 10.7 distribution shift

至少做一次受控 shift：

- backend/library 版本；或
- device/driver；或
- precision/quantization；或
- model snapshot/width；或
- prompt-length/task-type 分布。

测试旧 profile 是否应过期，以及系统能否返回 `INCONCLUSIVE/admission failure`，而不是带着旧阈值继续 `PASS`。

### 10.8 输出

```text
experiments/calibration_corpus/
  CORPUS_ASSET_AUDIT.md
  DATASET_CARD.md
  preregistration.json
  collect_*.py
  validate_corpus.py
  calibrate_honest_envelope.py
  results/<RUN_ID>/
    manifest.csv
    prompt_energy.csv
    thresholds.csv
    heldout_verdicts.csv
    task_level_fpr.csv
    shift_results.csv
    checks.json
    WP1_CALIBRATION_MEMO.md
```

### 10.9 通过和停止条件

通过：held-out task-level FPR 达到预声明目标；置信上界和样本量解释完整；大多数诚实任务直接 `PASS`；C3 不再出现当前 15%--33% 的误报崩溃。

停止/改设计：合理样本量下 honest drift tail 仍严重非平稳，大多数任务只能 `INCONCLUSIVE`；或 execution signature 数量导致校准成本无法维持。此时应考虑更强 per-block verifier、在线校准或缩小部署范围。

---

## 11. WP2：真实语义攻击与强自适应攻击

### 11.1 目标

证明 PACT 处理的是现实有害执行，而不只是人工增加 `L2` residual。

当前仓库保留了路线 A 论文中的攻击设计和结果，但没有在路线 B 活跃目录中保留完整 `joint_null`/语义攻击生成环境。开始前先定位原始攻击代码、模型权重、prompt 和运行脚本；找不到时，将“攻击环境恢复”作为正式子任务，不得假设已有代码可运行。

### 11.2 攻击分层

第一层，普通故障/篡改 baseline：

- Gaussian/noise；
- stale substitution；
- wrong-shard output；
- layer skip；
- scale/precision/quantization；
- model or system-prompt modification，若环境支持。

第二层，路线 A 复用的 fixed-check white-box baseline：

- SignRadial null/sign-balanced；
- ProjCos nullspace；
- `joint_null`；
- tolerance-hugging；
- harm-optimal projected-gradient null attack `e*`。

这些攻击属于路线 A 的发现。路线 B 的新问题是它们在 attack-before-seed 的 PACT 时序下表现如何。

第三层，PACT 主攻击：

- unknown-seed EOT：最大化下游 harm，同时最小化未来 PACT challenge 上的期望检测；
- boundary-specific attack：C1/C2/C3 分开；
- low-energy/high-harm attack：最小化 residual energy 并维持目标攻击成功；
- support/effective-rank sweep；
- audit-prediction attack；
- root grinding/commit replacement；
- abort/withhold/late receipt；
- profile-shift attack。

known-seed nullspace 必须保留为负对照，并应继续成功绕过。若 known-seed 对照被检测，先怀疑实现或攻击构造错误。

### 11.3 正确的 seed 隔离

每个攻击实验至少分三个不重叠 seed domain：

- optimization seeds：EOT 梯度和候选生成；
- selection seeds：从候选中选择最终攻击；
- final-test seeds：攻击冻结后才产生，攻击代码不能读取。

最终测试前必须序列化并 hash 攻击后的 tensor，记录 `attack_commitment`。final-test seed 必须绑定该 root。只在内存里“承诺”不算协议证据。

### 11.4 harm 指标

至少包含：

- continuation token agreement；
- ROUGE-L 或明确选择的文本相似度；
- next-token/top-k agreement；
- targeted attack success rate 或任务正确率；
- last-token/logit margin 等可微 surrogate；
- residual `L2/F2`；
- `PASS/FAIL/INCONCLUSIVE`；
- stopping K 和升级模式。

可微 surrogate 用于优化，token/任务结果用于证明实际危害。不能只用 `rho` 代表语义 harm。

### 11.5 预注册 harm floor

运行前冻结：

- 哪个语义指标定义“materially harmful”；
- harm floor；
- 允许的 residual/compute budget；
- success 的任务级聚合方式；
- C1/C2/C3 和攻击强度矩阵；
- 主要结果和探索性结果。

不要在看到攻击效果后选择最容易过线的 harm 定义。

### 11.6 输出

```text
experiments/semantic_attacks/
  ATTACK_ASSET_AUDIT.md
  THREAT_MODEL.md
  preregistration.json
  attacks/
  run_attack_matrix.py
  validate_commit_then_challenge.py
  results/<RUN_ID>/
    attack_manifest.csv
    verdicts.csv
    semantic_metrics.csv
    seed_domain_audit.json
    examples.jsonl
    checks.json
    WP2_SEMANTIC_ATTACK_MEMO.md
```

每条定性文本样例必须能回到 prompt ID、attack ID、commitment、seed domain 和机器可读指标，不能手工挑图后丢失索引。

### 11.7 通过和停止条件

通过：在预声明 harm floor 上，未知 seed、post-commit 攻击被稳定 `FAIL` 或升级；检测结果跨 prompt/boundary 有统计支持；known-seed 对照清楚展示时序边界。

停止/降级：攻击能以显著语义危害稳定停留在 honest residual envelope 内，即使 K 接近 1000 也无法区分。此时 PACT 只能声称数值一致性检测，不能支撑强 semantic-risk 系统主张。

---

## 12. WP3：三节点 VeriEdge 集成

### 12.1 开始条件

只有 WP0 得到 `GO/CONDITIONAL_GO`，且 WP1/WP2 已证明至少一个可用 signature/harm operating point，才开始完整集成。

当前共享资产是接口 prototype 和 multi-node capture 模板，不是可直接声明的 live VeriEdge。第一项工作是提交 `RUNTIME_ASSET_AUDIT.md`，列出真实可运行节点、代码仓、模型缓存、网络、凭证和缺失接口。

### 12.2 最小 live path

按以下顺序实现：

1. producer 在 boundary serialization/发送路径中计算 streaming `actual_root`；
2. receiver 对实际消费字节计算 `receive_root`；
3. 输出/root commitment 完成后，scheduler 才抽取 audit decision；
4. reference path 生成并提交 `reference_root`；
5. seed service 绑定 task、boundary、model、shape、dtype、两 roots 和 beacon；
6. receiver/reference 运行同版本 PACT-G16 kernel；
7. 双方使用公钥签名回执；
8. adjudicator 验证上下文并进行三态裁决；
9. `INCONCLUSIVE` 使用 row-addressable prefix expansion；
10. durable state 处理 deadline、replay、conflict、abort 和 V3 hook。

### 12.3 必须绑定的状态

对 shard-local replay，至少审计：

- 输入 boundary bytes/root；
- token positions；
- attention mask；
- KV/cache 及其生命周期；
- model/shard weights hash；
- operator/backend/precision config；
- RNG/sampling state，若相关；
- upstream task and boundary identity；
- output tensor shape/dtype/root。

若少一个状态能让恶意 provider 在局部重放中使用不同上下文而仍通过，则 local replay 设计不完整。

### 12.4 实现优先级

先保证协议正确，再优化：

1. hash 与 serialization/network copy 融合；
2. projection 与 receiver tensor handling 融合；
3. prefix row reuse；
4. reference batching；
5. tensor retention 生命周期；
6. GPU kernel 或结构化 projection。

结构化/稀疏 projection 只能作为后续优化，并必须重新做 support invariance 和 adaptive-attack 审计。

### 12.5 正确性测试

至少覆盖：

- honest full flow；
- actual/receive root mismatch；
- root replacement；
- seed before root 的非法时序；
- wrong task/boundary/model/shape/dtype；
- replayed receipt；
- conflicting receiver receipts；
- late/missing commit/reveal/receipt；
- last-revealer abort；
- reference unavailable；
- K prefix consistency；
- process restart 后终态和 replay protection；
- float32/float64 跨硬件差异。

### 12.6 性能矩阵

对 clean 和 attack workload，至少报告：

- V0/V1/V2；
- `p_a in {.01,.05,.1,1}` 或 WP0 选定值；
- C1/C2/C3；
- K stopping distribution；
- mean/P50/P95/P99 end-to-end latency；
- throughput/goodput；
- producer/receiver/reference CPU/GPU 利用率；
- network/evidence bytes；
- tensor retention bytes * seconds；
- commitment、beacon、reference、projection、receipt、adjudication 分解；
- amortized reference compute。

同时报告同步关键路径和异步 settlement 路径，不得只把昂贵步骤移到后台后称为“零开销”。

### 12.7 通过和停止条件

目标：非 reference 的逐任务控制开销争取低于 3%--5%，reference 成本能按 WP0 的 `p_a` 摊销，并保持风险目标。

停止/重构：commitment、retention、beacon 和 projection 的非 reference 开销本身超过约 5%，或 reference 无法局部化/批处理而使平均成本失去优势。

---

## 13. WP4：风险自适应策略

### 13.1 输入和输出

策略输入：

- task value/security tier；
- provider 历史、处罚和近期 drift；
- boundary honest drift、conditional power 和 harm sensitivity；
- profile 样本量、年龄和 shift 信号；
- reference queue/load；
- 当前 PACT interval 和升级成本。

策略输出：

- `p_a`；
- protected boundaries；
- `K0/Kmax/expansion schedule`；
- reference mode；
- escalation mode。

### 13.2 必须比较的策略

- fixed `p_a` + fixed K；
- fixed `p_a` + adaptive K；
- task-value only；
- boundary-depth only；
- provider-history only；
- full risk-adaptive policy；
- always-on duplicate；
- V0 no-audit lower-cost reference point。

### 13.3 评价方式

主图应是：

- 同等 overall risk 下的 average/P95 cost；或
- 同等 average cost 下的 undetected-risk/harm；
- 再报告 reference saturation、INCONCLUSIVE 和 upgrade rate。

不能只展示“自适应策略选择了不同 placement”。Risk-Adaptive 必须形成可见的 Pareto 改进。

### 13.4 通过条件

在真实或由真实 trace 驱动的 workload 上，full policy 相对固定策略形成稳定 Pareto 优势，且该优势不是由放松 FPR/harm floor、忽略 tail latency 或减少高价值任务保护造成。

---

## 14. WP5：baseline 与规模化

### 14.1 baseline 层级

第一层，仓库内可直接实现：

- AccountEdge/TSTC fixed sketch；
- retired PCRA coordinate opening；
- full residual oracle，仅作上界；
- always-on duplicate execution；
- PACT-R、PACT-G、PACT-G16；
- fixed K 与 adaptive K。

第二层，需要复现或接入：

- TOPLOC；
- Token-DiFR/Activation-DiFR；
- VeriLLM teacher-forced verification；
- TensorCommitments；
- NAO/TAO 类 tolerance-aware per-operator dispute；
- TEE/full per-operator escalation。

### 14.2 公平比较规则

所有方案必须尽量统一：

- model/prompt/workload；
- attack family 和 harm floor；
- honest execution signatures；
- task-level FPR target；
- reference compute 是否计入；
- evidence、storage、network 和 setup/calibration cost；
- online critical path 与 asynchronous cost；
- collusion/trust assumptions。

若某 baseline 的保证不同，不要强行压成一个 detection rate。先列出保证和信任模型，再比较共同部分。

### 14.3 规模矩阵

至少覆盖：

- 两个明显不同的模型宽度/规模；
- 三个 boundary depths；
- 多个 device/backend/precision pairs；
- 多个 prompt length/task type；
- clean、普通故障、语义攻击；
- 多个 audit budgets 和 provider malicious rates。

### 14.4 统一输出指标

- task-level FPR 和置信区间；
- conditional/overall detection；
- semantic attack success；
- `PASS/FAIL/INCONCLUSIVE/escalation`；
- average/P95/P99 latency；
- throughput/goodput；
- reference compute；
- evidence/network/storage；
- attribution/localization accuracy；
- calibration/setup cost。

---

## 15. WP6：理论、论文和 artifact

### 15.1 理论最低要求

- 理想 Gaussian one-shot commit-before-seed 定理；
- known-seed 不可能性/负对照边界；
- adaptive K 的 anytime-valid 或预提交 alpha-spending；
- audit coverage、projection、calibration 和 multi-boundary risk composition；
- G16 finite-table 的保守处理；
- V1 连续作弊检测与成本模型。

### 15.2 论文贡献结构

- `C1` 双层风险自适应验证架构；
- `C2` receiver/reference-bound commit-then-challenge PACT；
- `C3` support-invariant、boundary-aware、three-valued evidence；
- `C4` 三节点实现和真实安全-成本评测。

没有 C4，前三项不足以支撑强系统论文。

### 15.3 claim-evidence ledger

每条论文主张必须记录：

```text
claim_id
exact claim sentence
scope/assumptions
supporting table/figure
source CSV and run_id
code command
confidence interval/statistical test
known limitation
status: supported/partial/unsupported
```

摘要中的每个数字都必须能落到一个 ledger 条目。

### 15.4 artifact 要求

- 一键重建 summary/figures，不要求重新跑昂贵硬件实验；
- raw/summary/derived 文件分开；
- 固定 seed、manifest、hash 和环境；
- 提供小型 smoke corpus；
- 明确哪些是 measured、legacy、modeled、external；
- 删除 host/IP/user/token 等身份或秘密；
- README 中写清不实现的内容。

---

## 16. 数据纪律和实验红线

以下任一条违反，都可能使一整组结果不可用。

1. calibration、attack optimization、candidate selection 和 final test 必须分离。
2. 重复 projection seeds 不是独立 prompts。
3. byte-identical 文件不是 genuine rerun。
4. 不能从 held-out 调阈值后继续称其为 held-out。
5. C1/C2/C3 必须分开报告，除非有预提交的 task-level aggregation。
6. `conditional detection` 与 `overall detection` 必须分开。
7. timeout、withholding、missing reference 不能记为 `PASS`。
8. `INCONCLUSIVE` 不能被丢出分母或隐藏。
9. known-seed 和 unknown-seed 结果不能混合。
10. synthetic perturbation、真实硬件 drift、真实语义 attack 必须分标签。
11. 旧 EuroSys 数字必须标 `legacy_measured`，复核后才能升级。
12. WAN/profile simulation 必须写 `modeled`，不能写成真实链路测量。
13. activation inversion/harm attack 测到的是当前攻击能力的下界，不是隐私/安全上界。
14. 图中不得手工抄数；图必须由同目录 CSV 生成。
15. 负结果和失败配置必须保留，不能只交最优 seed、prompt、boundary 或 stack。
16. 任何 1% FPR 主张必须同时说明独立样本量、阈值方法和置信区间。
17. 所有新随机协议必须证明 seed 在 attack commitment 后产生。
18. public/reused projection 被 adaptive input 攻击时，不得引用 one-shot PACT 保证。

---

## 17. 每周汇报和结果 memo 模板

### 17.1 每周汇报

每周只回答：

```text
本周结论：一句话
完成的 run_id：
支持/反驳了哪个假设：
最重要的图或表：
数据质量检查：
与预期不一致的结果：
当前 blocker：
下周最小可证伪任务：
是否触发 Go/No-Go：
```

不要用“完成了 80%”代替研究结论。

### 17.2 每个实验的 RESULT_MEMO

```text
# 实验名

Date / Run ID / Owner / Status

## Question
一个可证伪问题。

## Preregistered decision rule
参数、阈值、主要指标、通过/停止条件。

## Inputs
数据、signature、hash、代码版本、source_type。

## Method
足以让另一位同学复现。

## Integrity checks
split、seed、constraint、manifest、missing data。

## Results
主表、置信区间、负结果、INCONCLUSIVE。

## Interpretation
允许说什么，不允许说什么。

## Decision
GO / CONDITIONAL_GO / NO_GO / BLOCKED。

## Reproduction
完整命令和输出路径。
```

### 17.3 blocker 报告

一个合格 blocker 必须说明：

- 缺哪个文件、接口、模型、硬件、权限或定义；
- 已检查哪些路径；
- 为什么现有替代不能回答研究问题；
- 解锁所需的最小动作；
- 不解锁时可以继续做的只读或模拟工作。

---

## 18. 总 Go/No-Go

继续投入强系统路线必须同时满足：

1. reference economics 有非平凡可行区间；
2. 独立 prompt 上 task-level FPR 受控，且大多数 honest task 可 PASS；
3. 对预声明 harm floor 的未知 seed 攻击具有检测或升级能力；
4. 非 reference 控制开销低，reference 成本可摊销；
5. risk-adaptive policy 形成真实 Pareto 改进；
6. 相对强 baseline 至少在跨提供方边界、平均成本、风险语义或部署约束上有明确优势。

出现以下任一项，应停止或降级：

- 所有有意义风险目标都要求 `p_a` 接近 1；
- shard-local replay 实际等价于 full replay；
- C3 在扩充数据后仍无法控制 FPR；
- harmful attack 稳定处于 honest envelope；
- K 接近 1000 仍不能达到目标 harm detection；
- 大多数任务进入 `INCONCLUSIVE/V3`；
- 三节点非 reference 开销本身超过约 5% 且没有其他系统收益；
- 与已有工作相比只剩“换了投影分布”。

降级后仍可保留的成果包括：commit-time unpredictability 证据、PACT-G/G16 协议原型、校准失败分析、reference economics 负结果，以及 workshop/short paper 级别的风险审计工作。

---

## 19. 前十个工作日安排

### Day 1：入门和资产校验

- 完成第 7 节全部命令；
- 提交 onboarding report；
- 阅读路线 A 论文 abstract、blind subspace、adaptive attack、refreshability 和 conclusion；
- 阅读路线 B 总账、PACT spec 和全部 active result memos。

### Day 2：WP0 reference mode 审计

- 建立 `experiments/reference_economics/`；
- 完成四种 reference mode 的状态、信任和成本矩阵；
- 标出 current repo 可运行资产与缺口。

### Day 3：成本输入和来源审计

- 提取 G16、旧 runtime、placement workload 可用数字；
- 每个数字加 `source_type/source_path`；
- 未知组件设置参数范围，不填单点假数。

### Day 4：风险/成本模拟器

- 实现公式和配置读取；
- 完成边界测试；
- 输出 V0--V3、`p_a`、`m`、boundary grid。

### Day 5：WP0 结论

- 生成 cost-risk frontier；
- 完成 `WP0_REFERENCE_ECONOMICS_MEMO.md`；
- 做 G0 `GO/CONDITIONAL_GO/NO_GO/BLOCKED` 评审。

### Day 6：WP1/WP2 资产审计

- 盘点完整 raw corpus 是否可恢复；
- 盘点语义攻击代码、模型和 prompt；
- 分别提交 `CORPUS_ASSET_AUDIT.md` 和 `ATTACK_ASSET_AUDIT.md` 草稿。

### Day 7：冻结数据和攻击 preregistration

- 定义 primary execution signature；
- 冻结 prompt split 和样本量；
- 冻结 harm metric/floor、seed domains 和攻击矩阵。

### Day 8：最小新数据路径

- 先采集 6--12 个全新 prompt 做 schema smoke；
- 验证 hash、metadata、C1/C2/C3、跨 stack 对齐；
- 不把这批 smoke 合入正式 calibration，除非 preregistration 预先允许。

### Day 9：最小 unknown-seed semantic path

- 跑一个 boundary、一个攻击目标、一个小 prompt 集；
- 证明 tensor 在 final-test seed 前已序列化并承诺；
- 记录 PASS/FAIL/INCONCLUSIVE、harm 和 stopping K。

### Day 10：G1 设计复核

- 展示数据路径与攻击路径，不追求漂亮结果；
- 确认正式采集/攻击矩阵的成本；
- 由负责人批准后再开始 200--500 prompt 采集和大规模攻击优化。

---

## 20. 学生离开前的最终检查

在声称一个工作包完成前，逐项回答：

- 我回答的是一个可证伪问题吗？
- 我是否明确区分了 measured、derived、assumed、external 和 legacy？
- 每个图能否从 CSV 一键重建？
- calibration/selection/final test 是否严格隔离？
- 我是否完整报告了 C1/C2/C3、负结果和 INCONCLUSIVE？
- seed 是否确实在 tensor commitment 后产生？
- reference compute、storage 和 asynchronous cost 是否全部计入？
- 我是否误用了路线 A 的贡献或旧 EuroSys 的数字？
- 当前结论允许论文说什么，又明确不允许说什么？
- 结果是否触发了预先写好的停止条件？

如果其中任何一项回答不清楚，工作包还没有完成。
