# VeriEdge 路线 B 研究备忘手册

**拟定题目：** *VeriEdge: Risk-Adaptive Verification for Cross-Provider LLM Inference at the Edge*  
**系统名称：** VeriEdge  
**核心校验协议：** PACT（Post-commit Activation Consistency Test）  
**当前实现候选：** PACT-G16  
**文档日期：** 2026-08-24  
**当前阶段：** 已完成核心几何、协议时序和本地控制原型；尚未形成端到端系统论文结论

---

## 0. 这份手册的用途

本文是 VeriEdge 强版路线 B 的项目总账，用于统一：

1. 论文究竟要解决什么系统问题；
2. 哪些结论已经被实验支持；
3. 哪些只是设计目标，尚不能写成论文事实；
4. 接下来应做哪些实验、按什么顺序做；
5. 哪些结果意味着值得继续投入，哪些结果意味着应及时停止；
6. VeriEdge、PACT 与原 AccountEdge/NDSS 稿之间如何划分。

本手册优先于早期 PCRA/coordinate-opening 设计。早期设计仅作为失败路径和设计演化记录保留。

---

## 1. 项目的一页结论

### 1.1 研究问题

边缘 LLM 流水线把模型分片交给多个互不完全信任、硬件与软件栈不同的提供方。系统需要判断某个提供方是否正确执行了自己的分片，但面临两个矛盾：

- 不同硬件上的诚实执行不会产生逐比特一致的中间激活值；
- 低开销静态校验只观察低维信息，一旦攻击者在输出前知道校验子空间，就可以把恶意扰动放入其零空间。

因此，问题不是简单设计一个“更好的统计量”，而是：

> 如何以可部署的成本，为跨提供方、异构边缘 LLM 推理建立一个在攻击输出承诺时不可预测、能够适应边界风险和诚实数值漂移的验证系统？

### 1.2 核心洞见

决定低维随机检查是否有用的关键，不是笼统的“刷新频率”，而是：

> **unpredictability at attack commitment**：攻击者固定并绑定输出时，不能知道本任务最终使用的检查随机量。

任何固定的 `K x N` 线性检查在矩阵已知后都有高维零空间；单纯使用稠密投影并不能消灭零空间。VeriEdge 的安全单位必须是完整时序：

`执行输出 -> 承诺实际张量 -> 生成不可预测挑战 -> 参考/接收方计算证据 -> 三态裁决或升级`

### 1.3 系统方案

VeriEdge 是完整的风险自适应验证系统；PACT 是其任务内校验协议。

VeriEdge 采用两层风险控制：

1. **跨任务审计调度：** 根据任务价值、提供方历史、边界风险和成本预算，决定某个已承诺任务是否触发独立参考执行。低风险任务采用不可预测抽样审计，高风险任务可采用逐任务参考执行。
2. **任务内证据扩展：** 对已触发审计的边界，PACT 从小 `K` 开始，用 commit-then-challenge 的稠密随机投影比较实际激活与参考激活；证据不足时增加 `K`，仍不确定则升级为更强验证器或完整重放。

这两层不能混淆：审计概率控制“哪些任务产生参考”，自适应 `K` 控制“一个已审计边界需要多少检查证据”。

### 1.4 当前判断

目前已经立住：

- 静态/预知检查的攻击时序问题；
- commit-before-seed 是必要条件；
- 理想高斯投影对攻击支撑位置具有精确不变性；
- 边界必须使用不同的检查预算；
- PACT-G16 可以形成确定性、可重放、上下文绑定的协议记录；
- 本地状态机能够拒绝替换、重放、晚到和冲突证据。

目前尚未立住：

- 不为每个任务完整复制推理时，VeriEdge 的真实成本与安全收益；
- 1% 任务级误报率；
- 对真实语义攻击的端到端检测能力；
- 三节点异构运行时中的延迟、吞吐和跨硬件数值行为；
- 相对 NAO、TensorCommitments、DiFR/TOPLOC 和完整复制执行的系统优势。

因此，当前产物是一个有明确技术核心的研究原型与论文骨架，不是已经完成的系统顶会论文。

---

## 2. 论文定位

### 2.1 目标 venue 形态

路线 B 是系统论文，而不是以攻击为中心的安全分析论文。目标形态接近 EuroSys/OSDI/SOSP 类论文：

> 提出一套完整、正向、可部署的验证系统，并证明它在异构边缘推理中以显著低于逐任务完整复制或细粒度验证的平均成本，获得可解释的风险控制。

安全分析是设计依据，不是论文主角。已知 seed 下的零空间攻击应出现在动机、威胁模型和安全评测中；标题、摘要和第一贡献应首先描述 VeriEdge 系统带来的能力。

### 2.2 建议的一句话主张

英文工作版：

> VeriEdge makes cross-provider verification practical for heterogeneous edge LLM pipelines by combining unpredictable post-commit audits across tasks with support-invariant, boundary-adaptive checks within each audited execution.

中文：

> VeriEdge 将跨任务的不可预测承诺后审计与任务内支撑不变、边界自适应的检查相结合，使异构边缘 LLM 流水线能够以风险可控的平均成本完成跨提供方验证。

### 2.3 目标贡献结构

#### C1：双层风险自适应验证架构

设计 VeriEdge，将参考执行从“每个任务都完整复制”改为按任务风险选择的乐观审计，并在被审计任务内部按证据逐步扩展 PACT 检查。系统明确区分：

- 审计抽样造成的任务覆盖风险；
- 随机投影造成的估计风险；
- honest drift 校准误差；
- 多边界和多轮检查的组合风险。

#### C2：PACT commit-then-challenge 协议

PACT 把实际发送/接收的边界张量绑定到不可替换的承诺，再生成任务和边界特定的随机挑战。接收方与参考方分别出具上下文绑定的证据，裁决器只接受根、身份、随机量、参数和任务记录全部一致的回执。

#### C3：支撑不变且边界感知的检查策略

理想 PACT-G 使用稠密高斯投影。对挑战前固定的残差，投影能量分布仅取决于残差总能量和 `K`，而不取决于扰动支撑位置。VeriEdge 根据不同边界的 honest drift 和危害灵敏度选择起始 `K`、最大 `K` 和升级方式。

#### C4：端到端实现与真实部署评测

实现 PACT-G16、参考执行调度、三态裁决、重放保护和异构三节点流水线集成，并在真实攻击、模型宽度和硬件组合上测量安全—成本前沿。

其中 C4 尚未完成；没有 C4，前三项不足以支撑强系统论文。

### 2.4 明确不应声称的内容

VeriEdge 不应声称：

- 证明生成文本的语义正确性；
- 发明随机投影、JL/AMS sketch、哈希承诺或顺序统计；
- 消灭任意线性检查的零空间；
- 在攻击者提交输出前已经知道 seed 时仍然安全；
- 防御生产方、接收方和参考方全部串谋；
- 在没有独立参考或可信重放路径时证明计算正确；
- 对低于声明 materiality floor 的扰动提供检测保证；
- 只凭当前六个校准 prompt 达到 1% 分布无关误报率。

推荐的准确表述是：

> VeriEdge checks consistency with an independently generated reference activation under a committed execution and threat model; it does not directly prove semantic correctness.

---

## 3. 与原项目的关系

### 3.1 名称层级

- **VeriEdge：** 完整系统与新系统论文名称。
- **PACT：** VeriEdge 内部的 Post-commit Activation Consistency Test 协议。
- **PACT-G：** 采用理想 iid Gaussian 投影的分析模型。
- **PACT-G16：** 使用固定 16-bit inverse-CDF LUT 和确定性 PRG/XOF 的实现候选。

### 3.2 与 EuroSys 被拒版本的关系

不能把新工作写成旧 VeriEdge 的小修重投。新旧主线应明确区分：

- 旧主线：placement、disclosure、accountability 边界；
- 新主线：低成本、风险自适应、跨提供方异构验证。

旧 placement 机制可以降为审计策略的一个输入，例如决定哪些边界风险较高、哪些参考路径可用；它不应继续占据论文主叙事。披露边界可以作为参考路径的约束或讨论内容，但不应与新验证主线并列成另一半论文。

### 3.3 与当前 AccountEdge/NDSS 稿的关系

AccountEdge/路线 A 的核心是暴露轻量 verifier 的结构性盲区并讨论 accountability/disclosure。VeriEdge/路线 B 应把该发现当作设计动机，然后给出正向系统答案。

需要控制的内容重叠：

- A 可主张静态低维 verifier 存在高维盲子空间和实证攻击；
- B 不再把该发现作为自己的首要贡献，而是引用/重述为设计需求；
- B 的新贡献必须来自跨任务审计、PACT 协议、风险组合策略和端到端系统实现；
- 在 A 尚处于匿名审稿期间，正式投稿 B 前必须重新核对 dual-submission 与匿名引用规则。

---

## 4. 威胁模型和系统假设

### 4.1 攻击者能力

恶意 shard provider：

- 知道模型、协议、投影族、阈值、审计概率的策略形式和升级规则；
- 可以离线优化任意语义攻击或残差扰动；
- 可以针对未来随机挑战的分布做 expectation-over-challenges 优化；
- 可以拒绝提交、拒绝揭示或拖延回执，但这些行为必须进入可审计失败状态；
- 在张量承诺后可以看到 seed，但不能替换已承诺张量；
- 不应能预知本任务是否被审计，也不应在张量承诺前预知本任务的投影 seed。

### 4.2 最低信任条件

对每个受检边界，至少需要：

- 生产方与实际接收方不同时完全串谋；或存在第二个独立 receipt witness；
- 参考/重放路径不与恶意生产方串谋；
- 随机源在攻击输出承诺时不可预测；
- 任务记录能够阻止 root、策略、身份和终态的事后替换。

### 4.3 失败与可用性

最后揭示者可能在看到对方 reveal 后中止，这首先是可用性攻击。正确行为是 `ABORTED` 或惩罚，绝不能将 timeout 转换为 `PASS`。部署版需要公共随机信标、阈值随机协议、保证金/惩罚或预承诺 fallback。

---

## 5. VeriEdge 目标系统架构

### 5.1 控制面

任务开始前，控制面提交：

- 模型和 shard placement；
- 被保护边界与风险等级；
- 参考执行模式和参考身份；
- 审计概率或逐任务审计要求；
- PACT 版本、系数族、`K0`、扩展序列和 `Kmax`；
- execution-signature-specific calibration profile；
- 任务级 `alpha`、漏检预算和 materiality floor；
- receipt deadline、随机源、升级和结算规则。

所有影响攻击可见子空间和裁决阈值的参数都必须在看到本任务张量前固定。

### 5.2 数据面

每个 provider 产生并发送边界激活。系统在序列化/传输路径上计算发送 root；接收方对实际消费的字节计算接收 root。二者不一致时立即进入传输争议，不等待统计检查。

### 5.3 跨任务审计层

推荐将系统设计成三种模式：

| 模式 | 参考执行 | 适用场景 | 保证语义 |
|---|---|---|---|
| V0：记录模式 | 不主动生成参考，仅绑定执行记录 | 极低风险、诊断与争议取证 | 不提供静默恶意计算的主动检测 |
| V1：乐观抽样审计 | 在输出承诺后以不可预测概率触发参考重放 | 常规工作负载 | 单任务检测率由审计概率乘以 PACT 条件检测率决定 |
| V2：逐任务保护 | 每个任务都有独立参考执行或冗余边界 | 高价值任务 | 不受跨任务抽样覆盖损失，但成本更高 |
| V3：强升级 | per-operator/full replay/TEE/更强证明 | PACT 仍不确定或极高风险 | 由升级机制决定 |

V1 是解决参考执行经济性的核心候选。设审计概率为 `p_a`，PACT 在已审计任务上的条件漏检率为 `gamma_p`，则单个恶意任务的检测概率近似为：

`p_detect = p_a * (1 - gamma_p)`。

若同一提供方连续作弊 `m` 次，且审计选择独立，则至少一次被发现的概率为：

`1 - (1 - p_detect)^m`。

这不是逐任务正确性保证，而是可明确计价的乐观审计/威慑保证。高价值单次任务必须提高 `p_a`，必要时使用 V2/V3。

#### 5.3.1 参考执行的粒度

“独立参考”不应默认等同于整模型从 prompt 开始重跑。WP0 必须比较四种实现：

1. **full-model replay：** 语义最清楚，但成本最高，作为 upper-cost baseline；
2. **shard-local replay：** 从被审计 shard 的已承诺输入激活和执行状态开始，只重放该 shard 并生成目标边界参考；
3. **redundant shard：** 调度第二个 provider 同步或延迟执行同一 shard；
4. **trusted/TEE referee：** 由可信服务按需执行目标 shard。

当前最值得验证的是 shard-local replay，因为它可能把参考成本从完整模型降为一个 shard。但它不是免费能力：自回归推理还需要绑定并提供正确的 token position、attention mask、KV/cache 或其他状态。若这些状态没有被承诺，恶意 provider 可以通过状态替换绕过局部重放；若全部状态必须长期保存和传输，成本也可能重新变高。

局部重放验证的是“该 shard 是否对其实际收到且已绑定的输入正确执行”。若上游输入已经恶意，逐边界检查应以第一个失败边界完成定位；它并不把恶意上游输入自动变成正确输入。

### 5.4 任务内 PACT 层

对触发参考执行的任务：

1. 实际张量 `h` 与参考张量 `h_ref` 分别被绑定；
2. 只有在 roots 不可替换后才派生 seed；
3. seed 定义全覆盖投影矩阵 `A_s`；
4. 接收方和参考方计算 `y=A_s h` 与 `y_ref=A_s h_ref`；
5. 裁决器计算投影残差能量并给出 `PASS/FAIL/INCONCLUSIVE`；
6. `INCONCLUSIVE` 时按预提交前缀增加 `K`，或进入 V3。

### 5.5 三态裁决

- **PASS：** 在当前风险预算下，残差上界落入 honest envelope。
- **FAIL：** 残差下界超过提交的 material discrepancy boundary，或出现 root/身份/时序冲突。
- **INCONCLUSIVE：** 校准支持不足或置信区间重叠。系统必须扩展证据或升级，不能静默通过。

---

## 6. PACT 的统计核心

设实际与参考边界张量之差为：

`v = h - h_ref in R^N`。

理想 PACT-G 在张量承诺后生成：

`A_s in R^(K x N), A[j,i] ~ N(0, 1/K)`。

对在 seed 生成前固定的 `v`，投影能量估计满足精确条件分布：

`K * T_K / F_2 ~ chi-square_K`，

其中 `F_2 = ||v||_2^2 / N`，`T_K` 为相应归一化投影能量。

因此，理想模型下检测分布依赖总残差能量和 `K`，不依赖攻击修改了 1、16 还是 256 个坐标。这解决了 coordinate-opening 的 support-hit ceiling，但不解决两个独立问题：

1. prompt 之间 honest drift 分布未知；
2. seed 在承诺前已知时，攻击者仍可选择 `ker(A_s)` 中的向量。

PACT-G16 用固定 65,536 项 inverse-CDF LUT 近似理想 Gaussian。理想 Gaussian 是定理模型；G16 是实现候选，两者的保证必须分开陈述。

---

## 7. 已完成工作与证据

### 7.1 失败但重要：coordinate-opening/PCRA

早期方案在随机坐标上组合 spike、energy 和 directional statistics。实验证明，只要这些统计量观察同一组坐标，稀疏攻击的检测上限仍由“是否抽中攻击支撑”决定。

- `q=64, rho=.05`：自适应攻击检测率 9.70%，honest FPR 3.87%；
- `q=512, rho=.05`：检测率 36.26%，honest FPR 已达 13.80%；
- 优化器通常选择 16-coordinate support。

结论：增加同一批 openings 上的统计量不能消除 support coverage ceiling，PCRA 已被 PACT 替代。

### 7.2 Rademacher P0：全覆盖方向正确，但小 K 仍有形状效应

真实异构 residual 上，稠密 Rademacher 投影消除了 `q/N` 命中上限。`K>=32` 时，所测支持规模之间的检测率最大差异低于 0.9 个百分点；但 `K=1, rho=.02` 时最大差异达到 26 个百分点。

结论：全覆盖是必要的，但 Rademacher 在小 `K` 下不具有精确支撑不变性。

### 7.3 Gaussian P0：支撑不变性成立

对 supports `1/16/256`、`K=1..64`、`rho=.01/.02/.05`，采用 256 个选择挑战和 4,096 个独立测试挑战：

- 21 个 `(K,rho)` 设置中的最大 support spread 为 0.70 个百分点；
- 精确 Gram sampler 已与显式稠密 Gaussian 矩阵验证；
- 本地 NumPy materialized Gaussian 比 Rademacher 慢约 2--3.4 倍。

结论：理想 Gaussian 是正确的分析默认值；其新意不在投影本身，而在 post-commit 协议和系统策略。

### 7.4 已知 seed 负对照：时序是必要条件

攻击者看到 `K x N` 矩阵后，仅用 `K+2` 个坐标即可构造同时满足：

- `A delta = 0`；
- `delta` 与 honest residual 正交；
- 任意指定相对 L2 强度。

实测 `K=8/32/64`、`rho=.01/.02/.05` 下，攻击检测率与 honest 检测率完全相同；最大 rate difference 为 0，最大相对 nullspace residual 为 `9.66e-15`。

结论：论文必须写 **unpredictability at attack commitment**，不能只写 refreshability。

### 7.5 精确 conditional power：K 必须边界感知

在假定每个 prompt 的 honest full residual energy 已知的理想条件下，`rho=.01`、95% 条件检测功效需要：

| 边界 | median K | max K |
|---|---:|---:|
| C1 | 8 | 19 |
| C2 | 8 | 20 |
| C3 | 303 | 928 |

`rho=.02` 时 C3 为 median 37、max 89；`rho=.05` 时 C3 为 median 6、max 10。

结论：统一 `Kmax=256` 对浅层边界浪费、对最难 C3 弱攻击仍不足。边界感知预算不是可选优化，而是系统设计要求。

### 7.6 自适应 K：能够节省容易样本的证据成本

策略 `K=8 -> 16 -> 32 -> 64 -> 128 -> 256`，使用精确 chi-square 区间和六次查看的 Bonferroni 预算：

- C1/C2，`rho=.02`：平均约 `K=8.3` 即 FAIL；
- C1/C2，`rho=.01`：平均约 `K=19`；
- C3，`rho=.02`：99.99% FAIL，平均 `K=50`；
- C3，`rho=.01`：33.6% FAIL、65.7% INCONCLUSIVE，平均 `K=212`。

结论：自适应 `K` 能处理投影不确定性，不能弥补 prompt-level calibration 数据不足。

### 7.7 校准审计：当前数据不能支撑 1% FPR

当前 calibration 只有 6 个独立 prompt。即使使用精确 full residual energy、令 `K -> infinity`，held-out honest exceedance 在 C1/C2/C3 仍为约 8.3%/16.7%/33.3%。`stack_02_rerun_eval_12` 与原 eval 数据逐字节相同，不能算独立复现。

分布无关 split-conformal 阈值的最细 miscoverage 分辨率为 `1/(n+1)`；要得到非平凡的 1% 阈值，至少需要 99 个独立 calibration prompt。重复 seed 不会增加 prompt 样本量。

结论：当前只能声称检查几何成立，不能声称 deployment-level 1% FPR。

### 7.8 G16 系数实现候选

高精度实验结果：

| 系数族 | 最坏 support spread |
|---|---:|
| Rademacher | 65.51% |
| LUT8 | 0.777% |
| LUT16 | 0.368% |
| ideal Gaussian | 0.302% |

LUT16 在所测 simultaneous interval 上与 Gaussian 接近；本地 `N=16,384` CPU microbenchmark 中比 online Gaussian 快约 37%--43%。固定 LUT 的 SHA-256 为：

`8babbcaf96568f10165a1eab530c0e5c92d04de96761b6dbb3dadfa94baba37f`

结论：PACT-G16 是实现候选，但 LUT16 不能直接继承理想 Gaussian 的精确 chi-square 定理；仍需有限表界或保守经验区间。

### 7.9 可执行协议 transcript

已实现：

- canonical little-endian float32 tensor commitment；
- 绑定 task、boundary、model、shape、dtype、actual/reference roots 和 beacon 的 SHAKE256 seed；
- row-addressable SHAKE256/LUT16 投影与 prefix expansion；
- receiver/reference receipts；
- roots、peer roots、seed、K、coefficient digest、角色和上下文交叉校验；
- tamper、wrong key、context mutation 和跨任务 replay 拒绝。

六个真实边界（eval_001/eval_005 的 C1--C3）均通过 transcript 一致性检查。`K=64` 的 JSON/HMAC receipt pair 为 2,809 B（float64 sketch）或 2,129 B（float32 sketch）；`K=16` float32 pair 为 1,619 B。

限制：当前使用 HMAC 验证 canonicalization 和篡改拒绝，不是公开签名；尚未测试跨硬件 accumulation。

### 7.10 状态机和重放控制

SQLite 原型实现：

`ROOTS_COMMITTED -> BEACON_COMMITTING -> BEACON_COMMITTED -> BEACON_REVEALING -> SEED_READY -> RECEIPTS_PENDING -> ADJUDICATED`

以及 `ABORTED`、`FROZEN_CONFLICT` 终态。15 条正常、恶意、超时和重启路径全部通过，包括 root 不可替换、早 reveal、错误 reveal、late receipt、冲突回执冻结、重启后 replay 拒绝等。

限制：SQLite 只提供本地原子性和持久化，不是 Byzantine/tamper-evident 共识记录。

---

## 8. 当前代码和结果索引

核心设计：

- `ndss2027/docs/ROUTE_B_REDESIGN_PACT_2026-08-24.md`
- `ndss2027/docs/ROUTE_B_STRONG_CHECK_DESIGN_2026-08-24.md`（已退役 PCRA，仅作演化记录）

实验入口与脚本：

- `experiments/pact_offline/README.md`
- `pact_projection.py`：Rademacher/Gaussian P0
- `calibration_audit.py`：prompt-level 校准审计
- `adaptive_gaussian_policy.py`：自适应 K
- `known_seed_nullspace.py`：已知 seed 零空间负对照
- `conditional_power.py`：精确条件功效与边界预算
- `quantized_gaussian.py`：LUT/Gaussian 系数族
- `benchmark_projection_cost.py`：本地投影成本
- `pact_g16_protocol.py`：可执行 transcript
- `pact_g16_state_machine.py`：commit-reveal 与持久状态机

结果报告：

- `P0_RESULTS_2026-08-24.md`
- `GAUSSIAN_P0_RESULTS_2026-08-24.md`
- `ADAPTIVE_GAUSSIAN_RESULTS_2026-08-24.md`
- `CALIBRATION_AUDIT_2026-08-24.md`
- `KNOWN_SEED_NEGATIVE_CONTROL_2026-08-24.md`
- `CONDITIONAL_POWER_2026-08-24.md`
- `QUANTIZED_GAUSSIAN_RESULTS_2026-08-24.md`
- `PACT_G16_PROTOCOL_RESULTS_2026-08-24.md`
- `PACT_G16_STATE_MACHINE_RESULTS_2026-08-24.md`

---

## 9. 尚未解决的核心研究问题

### 9.1 参考执行经济性：第一优先级

当前所有 PACT 比较都默认 `h_ref` 已存在。如果每个任务都要完整重复一次 LLM 推理，系统可能失去相对冗余执行的价值。

需要回答：

1. 参考执行是逐任务、抽样、风险触发还是争议触发？
2. 抽样发生在什么时刻，如何防止 provider 预知本任务不被审计？
3. 未被审计任务提供何种保证，是否只是威慑与事后责任？
4. 参考任务能否批处理、使用不同层级、复用缓存或只重放可疑 shard？
5. 参考路径引入的 plaintext/activation disclosure 是否违反原隐私边界？
6. 参考执行的成本与 `p_a`、任务价值和攻击持续次数如何共同决定策略？
7. shard-local replay 需要绑定和保留哪些输入/KV/cache 状态，是否仍明显低于 full replay？

推荐主线：V1 乐观抽样审计 + V2 高价值逐任务保护 + V3 不确定升级。纯 dispute-only replay 不能发现没有外部投诉的静默恶意计算，不能单独承担主方案。

### 9.2 校准规模和分布漂移

至少需要：

- 每个主要 execution signature 至少 99 个独立 calibration prompt，建议 200--500；
- 另设独立 held-out prompts 报告 FPR，不能与 calibration 重用；
- genuine repeat executions 区分 prompt variation 与 runtime nondeterminism；
- C1/C2/C3 分开校准；
- 软件、驱动、模型、量化配置变化后的 profile expiration；
- task-level 多边界/多轮组合误报控制。

### 9.3 真实语义攻击

当前大多数实验使用 L2 受控、harm-preserving 的合成 residual perturbation，只验证几何和检测机制。系统论文必须回答恶意 shard 能否：

- 显著改变生成 continuation、任务答案或安全属性；
- 同时压低 PACT residual energy；
- 针对审计概率、`K` 策略和阈值分布进行 EOT 优化；
- 利用 deeper-boundary honest drift 隐藏语义危害；
- 通过 abort/withholding 避免负面裁决。

### 9.4 真实三节点运行时

需要把 commitment、seed、projection、receipt、reference scheduling 和 state machine 接入现有三节点流水线，测量：

- clean/attack workload 的平均、P95、P99 延迟；
- throughput/goodput；
- CPU/GPU 利用率和网络字节；
- commitment 是否能与 serialization/network copy 融合；
- projection 是否能与 receiver tensor handling 融合；
- tensor retention 与挑战窗口的内存成本；
- float32/float64 在真实异构节点上的一致性；
- 不同 `p_a`、`K` 和 escalation 的端到端成本。

### 9.5 强 baseline

至少需要对比：

- 原 AccountEdge/TSTC 静态 sketch；
- coordinate-opening/PCRA 失败版本；
- DiFR/TOPLOC 类 lightweight verifier；
- NAO/TAO 类 tolerance-aware per-operator dispute；
- TensorCommitments 类 tensor-native commitment；
- always-on duplicate execution；
- full/per-block verifier 或 TEE escalation（若可实现）。

比较不能只报检测率，应同时报 FPR、INCONCLUSIVE、平均审计成本、P95 成本、证据字节和任务级检测概率。

### 9.6 形式化与协议工程

仍需：

- 理想 Gaussian 下的正式 one-shot commit-before-seed 定理；
- 多轮 `K` expansion 的 anytime-valid 或 alpha-spending 证明；
- 审计抽样、投影误差、校准误差和多边界组合风险公式；
- LUT16 的保守 finite-table concentration/coverage 处理；
- Ed25519 或系统公钥签名；
- 真实 beacon/threshold randomness 与 last-revealer abort 处理；
- versioned wire format、PRG/XOF、counter、LUT、endianness 与 accumulator 规范；
- tamper-evident/Byzantine durable task record，而非单机 SQLite。

---

## 10. 研究计划与实验包

### WP0：锁定参考架构与经济模型

**目标：** 在继续大量工程前，证明 VeriEdge 有机会比逐任务完整复制更有价值。

工作项：

1. 实现或模拟 V0--V3 四种保护模式；
2. 分别测量 full-model replay、shard-local replay、redundant shard 和 trusted/TEE referee 的成本与状态需求；
3. 建立每任务成本模型：
   `C = C_commit + p_a*(C_ref + C_PACT) + p_upgrade*C_upgrade`；
4. 建立检测风险模型：
   `p_detect = p_a*(1-gamma_p)`；
5. 用现有 workload trace 模拟不同任务价值、攻击频率和 provider 历史下的最优 `p_a`；
6. 与 always-on duplicate execution 比较平均成本与风险；
7. 明确抽样审计 seed 也必须在任务输出承诺后生成。

**通过标准：** 存在实际工作负载区间，使平均验证成本显著低于 always-on duplicate，同时对声明攻击频率/任务价值达到预设风险目标。  
**停止条件：** 若所有有意义的单任务风险目标都迫使 `p_a` 接近 1，且参考执行无法局部化或摊销，则 VeriEdge 的系统优势不成立。

### WP1：独立 honest corpus 与校准

**目标：** 获得可以支撑任务级 FPR 的真实数据。

建议矩阵：

- calibration：每个主要 signature 200--500 个独立 prompts；最低不可低于 99；
- held-out：至少 100 个新 prompts；
- repeat：选取至少 30 个 prompts，每个做多次真实重跑；
- boundaries：C1--C3 分开；
- hardware/backend/precision：覆盖实际目标组合；
- model width：至少增加一个明显更宽的配置，如 `D=2048/4096`；
- version shift：至少一次软件或配置变化验证 profile expiry。

输出：honest full-energy distribution、projection distribution、split-conformal/upper-confidence threshold、task-level FPR、abstention rate。

**通过标准：** held-out task-level FPR 满足目标置信上界，C3 不再出现当前 15%--33% 的误报崩溃；正常任务大部分可 PASS，而不是依靠 INCONCLUSIVE 隐藏误报。  
**停止条件：** 若合理样本量下 honest drift tail 仍严重非平稳，使绝大多数任务只能 INCONCLUSIVE，则需改成更强 per-block verifier 或停止该主线。

### WP2：真实语义攻击与强自适应攻击

**目标：** 证明 PACT 检测的是现实有害执行，而不只是人为 L2 增量。

攻击套件：

1. 现有六类攻击作为可比基线；
2. EOT attack：优化下游 harm，同时对未来 PACT seeds 求期望；
3. boundary-specific semantic attack：分别攻击 C1/C2/C3；
4. low-energy/high-harm attack：最小化 residual energy 并维持输出破坏；
5. support/effective-rank sweep；
6. known-seed attack 作为必须失败的负对照；
7. audit-prediction、root grinding、abort/withhold 和 profile-shift 攻击。

语义指标至少包括 continuation token agreement、任务正确率/目标攻击成功率，以及与原稿一致的输出危害指标。所有检测结果必须拆成 PASS/FAIL/INCONCLUSIVE。

**通过标准：** 在预先声明的 harm floor 上，未知 seed、post-commit 攻击具有稳定检测或升级能力；known-seed 对照继续完全绕过，从而清楚验证时序边界。  
**停止条件：** 若攻击能以显著语义危害稳定停留在 honest residual envelope 内，即使 `K` 接近 1000 仍不可区分，则 PACT 只能检测数值差异，不能支撑强系统主张。

### WP3：三节点 VeriEdge 集成

**目标：** 将本地统计/协议原型变成真实系统。

实现顺序：

1. 双端 streaming commitment；
2. 输出承诺后的审计抽样与 seed service；
3. receiver/reference PACT-G16 kernel；
4. prefix expansion 和 tensor retention；
5. public signatures 与 receipt transport；
6. durable replay/settlement state；
7. V1/V2 reference scheduler；
8. V3 escalation hook。

性能优化优先级：先融合 hash 与 serialization，再融合 projection 与 tensor receive；不要在协议正确性之前过早优化结构化/稀疏投影，以免重新引入 support dependence。

**通过标准：** 在代表性 `p_a` 下，clean workload 的平均端到端开销具有系统意义上的优势；逐任务附加控制开销建议争取低于约 3%--5%，并明确报告参考审计的摊销成本。  
**停止条件：** 若 commitment、保留、beacon 和 projection 的非参考开销本身已超过约 5%，或参考审计无法摊销，则需要重新设计数据路径。

### WP4：风险自适应策略

**目标：** 让“Risk-Adaptive”成为实质贡献，而非标题形容词。

策略输入：

- 任务价值/安全等级；
- provider 历史和处罚状态；
- boundary honest drift 与 harm sensitivity；
- 当前 execution signature 的校准置信度；
- 参考资源负载；
- PACT 当前置信区间和升级成本。

策略输出：

- 审计概率 `p_a`；
- protected boundaries；
- `K0/Kmax` 和扩展序列；
- reference mode；
- escalation mode。

应比较：固定 `p_a`、固定 `K`、仅深度感知、仅历史感知和完整风险策略。核心指标是同等风险下的平均/P95 成本，或同等成本下的未检风险。

**通过标准：** 自适应策略相对固定策略在真实 workload 上形成清晰 Pareto 改进，而不是只改变几个 admission 决策。

### WP5：baseline 与规模化

**目标：** 回答系统审稿人“为何不用已有方案”。

至少覆盖：

- 1 个以上模型规模/宽度；
- 3 个边界深度；
- 多种 device/backend/precision pair；
- clean 与攻击 workload；
- 不同审计预算；
- 不同 provider 恶意频率。

统一报告：

- task-level FPR；
- conditional detection 与 overall detection；
- INCONCLUSIVE/escalation；
- average/P95/P99 latency；
- throughput/goodput；
- reference compute；
- evidence/network/storage；
- provider attribution accuracy。

### WP6：理论、写作与可复现性

**目标：** 将实现结果收束成可审查的系统论文。

需要完成：

- threat model 与 theorem；
- 理想 Gaussian/G16 保证分层；
- artifact scripts、固定 seeds、manifest 和环境记录；
- 论文中的 claim-evidence ledger；
- 失败情况与 non-claims；
- ethics/disclosure：投影 evidence 不公开，合法 receiver 已持有完整 activation；
- 与 A 的内容重叠审计。

---

## 11. 推荐执行顺序

### 阶段 G0：架构生死门

先完成 WP0，不再增加低价值的本地投影微基准。若参考执行经济模型没有可行区间，立即停止系统化投入。

### 阶段 G1：统计与攻击生死门

并行推进 WP1 与 WP2：新独立 prompts、genuine reruns、真实语义攻击。它们决定 PACT 是否能从几何实验升级成真实 detector。

### 阶段 G2：运行时生死门

只有 G0/G1 通过后，再全面投入 WP3 三节点集成。先做最小 live path，再做融合优化和签名/信标工程。

### 阶段 G3：系统论文增益

完成 WP4/WP5，证明 risk-adaptive policy 相对固定策略和已有 verifier 的系统收益。

### 阶段 G4：论文与 artifact

完成 WP6，冻结系统名称、协议版本和论文主张。

粗略工作量可按以下研究周估计，而非承诺日历：

| 阶段 | 主要工作 | 估计研究工作量 |
|---|---|---:|
| G0 | 参考模式、风险/成本模拟 | 约 1 周 |
| G1 | 新 corpus、重复运行、语义攻击 | 约 3--6 周 |
| G2 | 三节点集成与性能优化 | 约 3--5 周 |
| G3 | 策略、baseline、规模化 | 约 3--5 周 |
| G4 | 定理、写作、artifact | 约 2--4 周 |

实际墙钟时间取决于硬件可用性和并行人力；理论与攻击优化可能成为不可控路径。

---

## 12. Go / No-Go 总表

### 继续投入的必要条件

1. **参考经济性：** 不需要为每个普通任务完整重复推理，或逐任务复制在高价值模式下有清楚价值；
2. **真实校准：** 独立 prompt 上任务级 FPR 能受控，不能靠大量 INCONCLUSIVE 掩盖；
3. **语义相关性：** 对真实高危攻击，PACT 的数值证据与输出危害存在足够分离；
4. **端到端成本：** 控制面与投影本身开销较低，参考成本可由审计概率摊销；
5. **策略收益：** risk-adaptive policy 相比固定审计/固定 K 有显著 Pareto 改进；
6. **对比优势：** 相比 NAO、TensorCommitments、DiFR/TOPLOC 或完整复制，至少在跨提供方异构边界、平均成本或风险语义上有清楚不可替代性。

### 应停止或降级的条件

- 有意义的风险目标迫使 `p_a` 接近 1，且参考执行不能局部化；
- C3 等边界在扩充校准后仍无法维持合理 FPR；
- 语义危害能够以 honest-level residual 稳定实现；
- 即使 `K` 约 1000 仍不能检测目标 harm floor；
- 三节点非参考开销无法压到约 5% 以下且没有显著吞吐收益；
- 大多数任务都进入 INCONCLUSIVE/V3，PACT 仅增加一层前置成本；
- 与最接近系统相比，只剩“换了一种随机投影”的差异。

若停止强系统路线，现有成果仍可回收为：

- A 中对 refreshability 的精确校准；
- commit-time unpredictability 的负/正对照证据；
- 一个 workshop/short paper 级别的验证协议原型；
- 后续理论或风险审计工作的实验基础。

---

## 13. 论文预期结构

1. **Introduction：** 边缘跨提供方验证、异构漂移、静态检查盲区、VeriEdge 总览与结果。
2. **Background and Motivation：** 现有 verifier、参考执行成本、已知检查下的规避实例。
3. **Goals and Threat Model：** execute-once、commit-before-seed、非串谋与 non-claims。
4. **VeriEdge Design：** 双层风险控制、V0--V3、控制面和状态机。
5. **PACT：** transcript、receiver/reference evidence、三态裁决、G/G16。
6. **Risk-Adaptive Policy：** `p_a`、边界预算、`K` 扩展、升级选择。
7. **Implementation：** 三节点、streaming commitment、projection kernel、beacon/signature/ledger。
8. **Evaluation：** RQ1 安全边界；RQ2 FPR；RQ3 语义攻击；RQ4 性能；RQ5 自适应收益；RQ6 baseline/scale。
9. **Limitations and Discussion：** reference trust、collusion、semantic correctness、distribution shift、availability。
10. **Related Work and Conclusion。**

### 建议的核心图

- Fig. 1：VeriEdge 双层风险自适应架构；
- Fig. 2：commit-before-seed 时序与 known-seed 失败对照；
- Fig. 3：V0--V3 reference modes；
- Fig. 4：风险—成本 Pareto frontier；
- Fig. 5：不同边界的 adaptive K 分布；
- Fig. 6：真实语义攻击的 PASS/FAIL/INCONCLUSIVE；
- Fig. 7：三节点端到端 overhead breakdown。

---

## 14. 摘要骨架（尚非最终摘要）

> Cross-provider LLM inference at the edge makes verification difficult for two reasons: honest executions on heterogeneous devices exhibit numerical drift, while low-cost checks expose fixed low-dimensional structure that adaptive providers can evade. We present VeriEdge, a risk-adaptive verification system that separates verification into two decisions: when an execution warrants an independent reference, and how much evidence an audited boundary requires. VeriEdge commits the tensors actually exchanged between providers before deriving an unpredictable task-specific challenge. Its PACT protocol then compares actual and reference activations through support-invariant dense projections, expands evidence only when necessary, and escalates rather than silently accepting statistically unsupported cases. [End-to-end deployment result.] [Attack-detection result.] [Cost/Pareto result.] VeriEdge does not prove semantic correctness; it provides a risk-controlled consistency check under an explicit reference and non-collusion model.

方括号中的三项必须由后续真实实验填写，当前不得编造。

---

## 15. 下一次工作应直接做什么

下一步不是继续增加 LUT 或 NumPy microbenchmark，而是按以下顺序：

1. 写出并实现 V1/V2 reference scheduler 的最小模拟，画出 `p_a`—成本—检测风险曲线；
2. 盘点并开始生成至少 99 个独立 calibration prompts 与独立 held-out set；
3. 将现有语义 harm attack 接到 post-commit unknown-seed PACT 评测；
4. 若前三项显示可行，再接入三节点 runtime；
5. 并行准备 NAO、TensorCommitments、DiFR/TOPLOC 和 duplicate execution baseline。

这是当前最高信息增益、最低后悔成本的推进顺序。
