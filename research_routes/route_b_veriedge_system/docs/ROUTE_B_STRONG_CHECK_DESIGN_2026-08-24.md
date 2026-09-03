# 强版路线 B 设计：Post-Commit Risk-Limiting Activation Audit

> **已于 2026-08-24 被替代。** 本文档的 coordinate-opening 组合在
> harm-preserving 白盒自适应实验中失败：稀疏攻击仍受抽样覆盖率控制。
> 当前设计请使用 `ROUTE_B_REDESIGN_PACT_2026-08-24.md`；本文档仅保留为
> 设计演化记录。

日期：2026-08-24  
工作名：**PCRA**（Post-Commit Risk-Limiting Activation Audit）  
状态：系统与协议蓝图；未修改 AccountEdge/NDSS 主稿

## 0. 一句话主张

> 对异构流水线 LLM 推理，先把实际传输的边界张量做位置绑定承诺，再产生不可预测的随机挑战；验证器对承诺张量执行可顺序扩展的多统计量审计，在严格控制 honest false dispute 的同时，对预先声明的有害残差包络给出漏检风险上限，并在证据不足时自动升级而不是宣称正确。

这不是“再设计一个低秩 score”，而是由四个部分组成的 checking scheme：

1. attack commitment 之前不可预测的挑战时序；
2. 对实际传输张量的位置绑定；
3. 同一批 openings 上的互补统计检查；
4. 根据风险、证据和预算顺序扩样或升级的策略。

## 1. 先划清新颖性边界

以下内容不能再单独当创新：

- 完整 trace/tensor commitment 后再随机 opening；
- Merkle/vector commitment 的 position binding；
- 根据层敏感度选择检查位置。

原因是近期工作已经覆盖这些部分：

- [TensorCommitments](https://arxiv.org/abs/2602.12630) 使用 tensor-native commitment/Terkle tree，并根据 layer sensitivity 分配检查预算；
- [Towards Verifiable AI with Lightweight Cryptographic Proofs of Inference](https://arxiv.org/abs/2603.19025) 明确采用 `trace commitment -> random challenge -> path opening`；
- [VeriLLM](https://arxiv.org/abs/2509.24257) 使用 Merkle commitment 与 VRF 生成抽样位置；
- [AFTUNE](https://www.usenix.org/conference/usenixsecurity26/presentation/jin) 使用记录、抽查和 TEE 完成可审计推理。

PCRA 的差异化应固定在下面四点：

1. **异构漂移**：比较的是不同硬件/后端的合法执行，不能使用精确相等；
2. **白盒非前瞻攻击者**：攻击者知道全部协议、阈值和采样分布，但在随机挑战揭示前必须固定张量；
3. **多提供方流水线边界**：需要绑定“实际发送/实际接收”的边界张量并支持责任定位；
4. **风险限制顺序决策**：检查量不是静态 layer selector，而是由误报预算、声明攻击包络和当前证据共同决定，并允许 `INCONCLUSIVE -> upgrade`。

## 2. 威胁模型与保证范围

### 2.1 攻击者能力

恶意 provider：

- 知道模型、边界、校准数据摘要、所有统计量、阈值、抽样分布和升级规则；
- 可以在任一边界注入任意扰动，并针对下游输出危害优化；
- 可以用大量离线采样挑战做 expectation-over-challenges（EOC）优化；
- 在提交边界 root 后，可以看到挑战并选择如何打开，但不能改变已承诺位置的值；
- 可以拒绝 opening；拒绝或超时按协议失败结算。

攻击者在承诺前不知道本任务最终挑战随机量。随机量不能由 provider 或 scheduler 单方选择。

### 2.2 最小信任与非目标

- 至少有一个诚实的 reference/replay path；
- 对相邻发送方与接收方，默认至少一方诚实。两方串谋并对同一伪造张量给出一致 receipt 不在基础模型保证内；
- commitment 只绑定张量值与位置，不证明它由正确模型计算；计算正确性来自与 reference 的统计比较；
- PCRA 不证明语义正确性。它只对明确声明的残差攻击包络给出检测/漏检界；
- honest drift profile 失效或设备栈改变时，结果应是 `INCONCLUSIVE` 或重新校准，而不是继续沿用旧保证。

## 3. 协议对象

任务策略在数据移动前提交：

`P_j = (boundaries, strata, block_size, alpha, gamma, schedule, tests, escalation, reference_path)`。

其中：

- `alpha`：honest task 被错误判为 mismatch 的总风险上限；
- `gamma`：对声明 material-attack envelope 错误返回 PASS 的风险上限；
- `schedule = (q_1,...,q_R)`：逐轮累计 opening 数；
- `tests = {spike, energy, directional}`；
- `escalation`：达到最大预算仍不能判定时使用的高秩检查、冗余执行、TEE 或 full replay。

每个 boundary `k` 的 committed object 为

`C_{j,k} = Commit(task_id, boundary_id, shape, dtype, canonical_bytes(H_{j,k}))`。

实现首选带 multiproof 的 block Merkle tree；不把新的 commitment primitive 当论文贡献。

## 4. 消息时序

### Phase A：策略承诺

1. Orchestrator 选定 placement、reference path 和 PCRA policy；
2. `P_j` 写入 tamper-evident record；
3. policy 明确随机源的未来 beacon round，防止临时换随机源。

### Phase B：执行与双端绑定

对每个流水线边界：

1. 发送 provider 产生 `H_{j,k}`；
2. 在张量序列化/网络发送过程中同步计算 block hashes 和 root `C^out_{j,k}`；
3. 接收 provider 对实际收到的 bytes 同步计算 `C^in_{j,k}`；
4. 只有 `C^out_{j,k} = C^in_{j,k}` 时，边界 receipt 才成立；双方签名 receipt；
5. 所有 boundary roots、最终输出 digest 和 receipts 聚合成 task root `C_j`。

双端 root 的作用是防止 provider “承诺诚实张量、实际发送攻击张量”。若 roots 不一致，协议立即进入边界争议，不等待统计审计。

### Phase C：不可磨随机挑战

所有待审张量固定后，使用未来公共随机信标生成

`xi_j = H(task_id || C_j || policy_id || beacon_value)`。

不能只用 `H(C_j)`：恶意 provider 可以轻微修改张量、反复计算 roots，磨出有利采样位置。公共信标必须在 root deadline 之后才可预测；provider 在看到不利随机量后拒绝继续，按失败结算。

### Phase D：顺序 opening

1. 从 `xi_j` 派生每个 boundary、round、stratum 的无放回样本；
2. provider 返回 sampled blocks 与 Merkle multiproof；
3. verifier/reference path 生成对应 reference values；
4. checker 更新三类统计量并返回 `FAIL`、`PASS` 或 `INCONCLUSIVE`；
5. `INCONCLUSIVE` 时按预提交 schedule 扩大样本；超过预算则触发 escalation。

后续轮次不需要重新承诺张量；root 已经固定。轮次随机量从公共信标和完整 transcript 派生，且不得由 provider 选择。

## 5. 异构漂移标准化

对 execution-profile key

`kappa = (model, boundary, sender_backend, reference_backend, precision, shape)`

维护独立 drift profile。将 tensor 按 token position 与 channel block 分成 strata。对坐标 `i`，定义

`z_i = ((H^prov_i - H^ref_i) - mu_{kappa,g(i)}) / (s_{kappa,g(i)} + eps)`，

其中 `g(i)` 是 stratum，`mu` 与 `s` 使用独立 honest calibration set 的稳健 location/scale；也可以直接对下面的 batch statistics 做非参数校准，避免假设单坐标为 Gaussian。

profile 必须带：

- 软件/驱动/模型/量化版本；
- 校准样本量与置信区间；
- 过期条件；
- 未见 prompt 与未见随机 seed 上的 held-out FPR。

当前 200 条 calibration trace 不足以支撑“多 boundary × 多 round × 多 statistic”下的严格 1% 总误报校准；强版 B 需要更多独立 honest traces，或采用能给出 anytime-valid 保证的校准方法。不能把同一 trace 上大量随机 seeds 直接当成同数量的独立样本。

## 6. 同一批 openings 上的三类检查

### 6.1 Spike test：局部尖峰与稀疏篡改

`T_spike(Q) = max_{i in Q} |z_i|`

也记录超过高分位阈值的数量。它不做求和，因此不存在 SignRadial 的样本内正负抵消。适合检测少量大幅坐标修改、stale block 和局部跳层痕迹。

### 6.2 Energy test：弥散低幅扰动

`T_energy(Q) = (1/|Q|) sum_{i in Q} min(z_i^2, B^2)`。

截断使统计量有界，可以使用有限总体浓缩界；它检测许多坐标上的小幅能量，而不依赖统一方向。

### 6.3 Directional test：一致性偏移

`T_dir(Q) = |(1/|Q|) sum_{i in Q} sign(H^ref_i) clip(z_i,-B,B)|`。

它保留 SignRadial 对 scale/bias 类错误的高功效，但坐标在攻击承诺后才产生，因此攻击者不能针对本次样本精确配平。

三类统计量使用同一批 opened values，新增的主要是本地加法，不增加 reveal bytes。最终 checker 不应简单 OR 三个各自按 1% 校准的 verdict；必须预先分配 family-wise `alpha`，或对固定 composite statistic 做一次整体校准。

## 7. 三态决策与风险语义

### 7.1 两个不同错误预算

- `alpha` 控制 honest execution 被错误判为 FAIL；
- `gamma` 控制属于声明 attack envelope 的执行被错误判为 PASS。

二者不能用同一个 TPR@FPR 数字替代。

### 7.2 声明攻击包络

基础版至少定义三类有限总体 alternative：

1. `H_spike(s,delta)`：至少 `s` 个坐标的标准化偏移超过 `delta`；
2. `H_energy(Delta)`：完整边界的截断标准化能量均值至少为 `Delta`；
3. `H_dir(Beta)`：完整边界的 sign-aligned 标准化均值绝对值至少为 `Beta`。

离线 harm profiling 负责测量哪些 `(s,delta,Delta,Beta)` 与“token agreement 低于目标”相关。正式保证只针对包络，不把该经验关系写成语义正确性证明。

### 7.3 PASS / FAIL / INCONCLUSIVE

- `FAIL`：任一统计量在分配给它的 `alpha` 下显著偏离 honest drift；
- `PASS`：当前累计样本已经足以把三个声明 alternatives 的漏检概率都压到 `gamma` 以下，且未发现反证；
- `INCONCLUSIVE`：没有足够证据判 FAIL，但样本量也不足以给出 PASS 的风险界。系统必须扩样或升级。

这是相对当前二元 `accept/mismatch` 的关键改动：**未命中不等于通过。**

## 8. 可证明的基础界

### 8.1 Spike envelope

在 `N` 个坐标中至少有 `s` 个确定超过检测阈值，累计无放回抽取 `q` 个坐标时，完全漏掉它们的概率为

`gamma_spike(q) = C(N-s,q) / C(N,q)`。

因此检测率至少为

`1 - gamma_spike(q)`，

并可反解满足目标风险的最小 `q`。当 `q << N` 时，近似为

`q >= (N/s) log(1/gamma_spike)`。

这也明确暴露不可能性：若 material attack 可以只改一个坐标，低采样率不可能提供强保证，policy 必须升级。

### 8.2 Energy 与 directional envelopes

将单坐标贡献截断归一化到 `[0,1]`。若完整总体均值与 PASS 阈值之间至少有 margin `m`，保守的无放回 Hoeffding 界给出

`Pr[wrong PASS] <= exp(-2 q m^2)`，

有限总体修正只会进一步收紧。于是基础样本量满足

`q >= log(1/gamma) / (2 m^2)`。

论文版需要把 honest threshold 的估计误差、stratified sampling 和多轮可选停止一起纳入正式定理；这里的式子用于确定设计量级。

### 8.3 多轮与多统计量

最简单的严谨实现使用预提交 alpha-spending：为 round `r`、statistic `u` 分配 `alpha_{r,u}`，满足

`sum_{r,u} alpha_{r,u} <= alpha_task`。

每轮使用独立 held-out calibration 得到有效 p-value；任一 `p_{r,u} <= alpha_{r,u}` 则 FAIL。由 union bound，任意停止时刻的总 false dispute 不超过 `alpha_task`。后续可以用 e-process/confidence sequence 提高效率，但不是第一版必须项。

## 9. 风险自适应 policy

每个 placement candidate 不再只有一个经验 TPR，而是一个 mode profile：

`profile(k,m,q) = (FPR bound, miss-risk bounds, commit cost, reveal bytes, replay cost, latency)`。

Orchestrator 求解：

`min expected_execution_latency + challenge_probability * expected_audit_cost`

约束为：

- 每个被允许攻击的 boundary 的 `gamma_k <= gamma_task`；
- task-level family-wise `alpha <= alpha_task`；
- commitment、reveal、challenge latency 不超过预算；
- disclosure set 与 reference path 满足任务隐私策略；
- 无法用抽样达到 risk target 的 boundary 必须绑定 escalation mode，不能被静默 admission。

建议的 mode menu：

| Mode | 行为 | 用途 |
|---|---|---|
| M0 | 小批量 PCRA，快速拒绝明显异常 | 低风险常规任务 |
| M1 | 几何扩样，直到 PASS/FAIL | 中风险任务 |
| M2 | 高采样率 + block expansion | 深层或高 harm sensitivity boundary |
| M3 | redundant execution / operator-level verifier / TEE / full replay | 稀疏攻击包络使抽样无力时 |

深度只用于估计 harm sensitivity 与升级优先级；不能把“深层更危险”写成普遍规律，因为不同模型的敏感层并不一致。真正进入 admission constraint 的应是每个 model/boundary 实测的 attack envelope 和 miss-risk profile。

## 10. 实现落点

### 10.1 Streaming boundary commitment

在发送边界张量时按 block 计算 leaf hash，使 hashing 与 serialization/network copy 重叠。额外延迟近似为

`max(T_network, T_hash) - T_network`，

而不是单独再遍历一次张量。应实现 CPU hash、GPU hash、不同 block size 和 Merkle arity 的版本。

### 10.2 Multiproof

抽中多个相邻坐标时合并为 block opening，并用 Merkle multiproof 去重共享路径。需要同时报告 raw opened bytes 与 authentication bytes，不能只报告叶值大小。

### 10.3 Reference path

沿用 AccountEdge 已有的 replay/reference abstraction，但必须在系统稿中具体实现至少一种：

- dispute-only trusted reference worker；
- downstream shard redundant execution；
- TEE referee；
- requester-authorized reference service。

若 reference 需要额外 plaintext access，必须计入 disclosure set；不能以验证为名绕过 A 已经建立的披露边界。

## 11. 必须实现的最强攻击

不能只重跑当前六个单 seed attack。至少加入：

1. **EOC attack**：优化 `harm - lambda * E_xi[audit_score]`，每一步对大量随机 challenges 求期望；
2. **envelope-minimizing attack**：在保持下游 harm 的同时联合压低 spike、energy、directional 三类总体量；
3. **support sweep**：固定 L2/harm，控制 `s` 和有效维度；
4. **beacon/root grinding attempt**：验证 root-deadline + future beacon 阻断磨 seed；
5. **abort/withhold attack**：不利挑战下拒绝 opening，确认 settlement 不把它当 benign failure；
6. **profile-shift attack**：利用软件版本或硬件状态漂移逼近 calibration tail。

若 EOC attack 能稳定制造高 harm、低三统计总体信号，PCRA 应返回 `INCONCLUSIVE` 并升级；不能通过重新调阈值把它包装成检测成功。

## 12. 评测矩阵

### RQ1：position binding 是否真正覆盖传输路径

- `C_out`/`C_in` 一致性；
- commit-honest/send-malicious 与 send-honest/claim-malicious；
- 相邻单方恶意时的定位；
- collusion scope。

### RQ2：异构 FPR 是否受控

- unseen prompts、independent seeds；
- 多 device/backend/precision pairs；
- software update 前后 profile expiry；
- task-level 而非单 statistic 的实际 FPR。

### RQ3：对白盒 post-commit adversary 的功效

- 当前六族 + EOC + envelope-minimizing；
- `q`、`N`、support/effective dimension、boundary 扫描；
- harmful evasion 与 `PASS/FAIL/INCONCLUSIVE` 分解。

### RQ4：顺序策略是否节省成本

- 每轮停止比例；
- clean/attack workload 的平均与 P95 opening 数；
- 与固定 `q`、always-full、AccountEdge SignRadial/ProjCos 的比较。

### RQ5：placement 是否因此改变

- risk-constrained admission；
- goodput/latency/reveal bytes；
- 多少候选被 cheap-pass、upgrade 或 reject；
- 高风险 boundary 的预算是否被自动提高。

## 13. 与相邻工作的对比主张

| 方案 | Post-commit binding | 异构容差 | 白盒非前瞻攻击 | 多 provider boundary | 顺序风险界 | placement 联动 |
|---|---:|---:|---:|---:|---:|---:|
| AccountEdge/TSTC | 部分：只绑定预选 sketch | 是 | 揭示盲区，无防御 | 是 | 否 | 是 |
| VeriLLM | 是 | 同构 group 为主 | 未系统评测 | 是 | 否 | 否 |
| TensorCommitments | 是 | 未处理 cross-hardware drift | tailored attacks | 单 prover | 否 | 静态 layer selector |
| Random-path trace proof | 是 | 未处理 cross-hardware drift | 更强 adaptive attack 留作后续 | 单 prover/referee | separation-based | 否 |
| **PCRA** | **是，绑定实际传输边界** | **是** | **是，EOC** | **是** | **是，三态升级** | **是** |

这里最脆弱的 novelty claim 是“顺序风险界”：风险限制审计和 confidence sequences 本身是成熟统计工具。新意必须来自它们与 post-commit activation openings、heterogeneous drift、adaptive tensor attacks 和 multi-provider placement 的结合及端到端实现，而不能声称发明了 risk-limiting audit。

## 14. Go / No-Go

### Go 条件

- streaming commitment 的 P95 执行开销不超过约 3%；
- 对主要 harmful attacks，PCRA 在打开不超过约 1% 的 tensor coordinates 时，大部分任务能 PASS 或 FAIL，而不是 INCONCLUSIVE；
- held-out task-level FPR 满足 1% 目标；
- EOC attack 相比 single-seed attack 仍无法在 declared envelope 内实现高 harmful evasion；
- 相比固定 `q`，顺序策略把平均 reveal/challenge cost 至少降低一个有意义的倍数；
- placement replay 确实产生不同的 admit/upgrade/reject 决策。

### No-Go 条件

- 语义危害可以稳定集中在极少坐标，导致达到目标 `gamma` 必须打开接近全张量；
- honest drift tail 无法跨任务稳定校准，绝大多数任务只能 INCONCLUSIVE；
- commitment 与 multiproof 成本接近或超过已有 TensorCommitments，而没有多 provider/heterogeneity 上的明显收益；
- EOC attack 同时压低三类总体统计并保留高 harm；
- reference path 的成本或新增 plaintext disclosure 破坏系统核心目标。

## 15. 最小论文与顶会论文的区别

### 最小可发表版本

- block Merkle post-commit protocol；
- spike + energy 两类检查；
- 固定两轮扩样；
- 单模型、三节点、当前攻击套件。

这更像 SaTML/安全二线系统稿。

### 顶会强版

- streaming 双端 commitment + future-beacon anti-grinding；
- 三统计量、三态顺序审计与正式 `alpha/gamma` 定理；
- EOC/包络最小化攻击；
- 多模型宽度、多异构栈、真实流水线；
- risk-aware placement 与 escalation 的端到端收益；
- 清楚展示哪些攻击能 cheap-certify，哪些必须升级，以及为什么。

## 16. 第一版原型的最短路径

1. 不先实现新密码学：用 SHA-256 block Merkle tree；
2. 在现有 E2-R raw tensors 上离线模拟 `commit -> future seed -> q openings`；
3. 先实现 `spike/energy/directional` 三统计与 `q={64,128,256,512}`；
4. 加 EOC attack，检查三统计总体量是否能同时被压低；
5. 只有离线结果通过 Go 条件，再把 streaming commitment 接入三节点运行时。

这一步能最快回答强版 B 是否值得投入系统实现：若离线 PCRA 在 post-commit、EOC 攻击下仍大量 INCONCLUSIVE 或被高 harm 绕过，应该立即停止，而不是先花两个月做 Merkle/runtime 工程。
