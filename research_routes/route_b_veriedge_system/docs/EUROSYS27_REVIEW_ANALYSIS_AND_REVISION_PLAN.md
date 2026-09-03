# EuroSys '27 Spring — Paper #955 (VeriEdge) 审稿意见、分析与后续修订计划

- **状态**：已拒稿（Weak Reject ×2），无需 rebuttal。本文件仅用于记录审稿意见原文 + 分析 + 后续投稿其他venue时的修订计划。
- **记录日期**：2026-07-16
- **对应稿件**：`main_eurosys.tex`（EuroSys '27 Spring 投稿版）

---

## 1. 审稿意见原文

### Review #955A — Overall merit: 2 (Weak reject) — Reviewer expertise: 1 (No familiarity)

**Paper summary**
VeriEdge supports the outsourcing of LLM inference tasks to groups of heterogeneous edge nodes. Since heterogeneous executions do not necessarily result in bit-identical intermediate tensors, VeriEdge applies a tolerance-aware approach to handle disputed executions.

**Strengths / Weaknesses**
- \+ The paper convincingly motivates that heterogeneity should not only be taken into account when making resource-allocation decisions, but also in the context of verification.
- − Despite the paper highlighting accountability as a key selling point, the proposed approach apparently makes it impossible to hold individual providers accountable in case they leak private data.
- − The implications of VeriEdge's privacy-preserving delivery (PPD) mechanism are not comprehensively explored.
- − Important details about the evaluation environments are missing (e.g., LAN/WAN bandwidth and latencies).

**Detailed comments**
> I'm not sure if I completely understand the use cases for which VeriEdge has been designed. The paper (and especially Section 2.3) discusses a number of assumptions regarding what an adversary can or cannot do, however one of the most problematic issues does not seem to be addressed: the fact that individual providers may reveal the data that was given to them for processing. In fact, in contrast to alternative approaches, VeriEdge appears to make it impossible to identify and convict a particular provider that leaks secrets. In VeriEdge, only a single copy of the data is uploaded to the off-chain store, from which all selected providers retrieve it. As a consequence, if one of them reveals this information, there is no chance to determine which of the providers it was. On the other hand, using replicated payload delivery (RPD; i.e., the approach used as baseline in the evaluation) the requester directly sends a copy of the data to each provider. It is not mentioned in the paper, but to my understanding this would allow the requester to generate provider-specific payload versions (e.g., by adding different watermarks), and hence offer the opportunity to know which provider to blame after a leak.
>
> On a related note, I was surprised to see that the discussion of PPD (i.e., VeriEdge's approach) vs. RPD only centers around performance, because (as illustrated above) there seem to be other important aspects to take into account when it comes to designing the data flow between requester and providers.
>
> Figure 1 appears to be missing some arrows. For example, there is no connection between the requester and the off-chain data store even though the requester publishes the encrypted task object to this store (see Phase 3 on page 5).
>
> Figure 3: Please increase the font size.

**Questions for authors' response**
> Section 5.3 mentions "explicit LAN/WAN bandwidth and RTT profiles" but does not provide any details. Specifically, which values have been used as RTTs for the different experiments?

---

### Review #955B — Overall merit: 2 (Weak reject) — Reviewer expertise: 2 (Some familiarity)

**Paper summary**
VeriEdge aims to avoid scheduling jobs across a group of ill-suited heterogeneous nodes for a given task thereby reducing the median distribution latency. To identify ill suited groups of nodes, VeriEdge runs a representative task on a subset of the input and compares its output, profile traces, etc. to the expected counterparts.

**Strengths / Weaknesses**
- \+ Improves median latency across jobs by considerable margin of ~75%
- \+ Leverages tensor sketches to tolerate computational variations across devices
- − The definition of verification doesn't seem quite satisfactory
- − Relying on a blockchain/ledger appears to be an overkill (especially since adversarial guarantees are not strong)
- − Tight coupling of storing payloads on IPFS doesn't seem necessary (since these are already off the ledger)
- − Unless the task requires encryption, a simple cryptographic hash + plain text can be sufficient

**Detailed comments**
> In my opinion, "feasibility" is a more appropriate term instead of "verification" in this context of this paper. VeriEdge does not provide strong security guarantees and instead relies on a best effort strategy against fabrication, collusion and replay attacks. Instead it tests mainly for the computations capabilities of the heterogeneous group and simply validates it by throwing a challenge.
>
> Based on the text, I'm unsure if the prototype used an existing blockchain/ledger or was it a custom implementation from scratch. However, it seems to be an overkill to maintain a public ledger to record challenge and responses. Since the orchestrator is trusted - as per the trust model - it can maintain this information in a database and convey it to the relevant parties.
>
> Similarly the use of IPFS and encryption doesn't seem justified. The payload could be an open-source model and in that case the cryptographic overhead would be redundant. For confidential inputs, these can be simply put behind authenticated storage, e.g., S3.

**Questions for authors' response**
> \* Is there a specific need for a public ledger?
> \* Why can't we benchmark the endpoints, store them in a table and then try to match a job against the pre-computed table?

---

## 2. 分析

### 2.1 总体判断

两条都是 Weak Reject。核心不是质疑实验数据可信度,而是质疑：
1. **设计选择的合理性**（ledger、IPFS、PPD 的必要性）；
2. **论文措辞与实际保证不匹配**（"verification"/"accountable" 用词比正文实际限定的保证更强）。

两位评审都在手稿已写了大量 non-goals / 免责声明（"TSTC is not a cryptographic proof..."）的情况下，仍然觉得论文"声称的保证"偏强。说明问题不只是评审没读细，而是**标题和贡献点处用词偏硬**，正文限定条件分散在后面，导致评审先入为主。这是一个结构性/框架叙事问题，优先级高于单点打补丁。

### 2.2 逐条拆解

| 来源 | 问题 | 判断 | 严重度 |
|---|---|---|---|
| A | PPD 下所有 selected provider 拿同一份密文，泄密后无法溯源具体是哪个 provider；RPD 可加 per-provider 水印做到 | **真问题，切中核心**。手稿把 "accountable placement" 作为核心卖点（G2），但 accountability 目前只覆盖*执行*层面（哪个 shard/provider 导致 divergence），完全没讨论*数据泄露*的可追责性。评审的类比是对的，PPD 为了效率牺牲了这个维度，论文没讨论这个 trade-off。 | 高 |
| A | PPD vs RPD 对比只谈性能，没谈其他维度 | 同一问题的另一表述 | 高 |
| A | Figure 1（`fig_system_model_workflow.drawio.pdf`）缺 requester→off-chain store 的箭头 | 需要核对图；Phase 3 workflowstep 4 明确写了 requester 发布密文到 off-chain store，若图上没画就是真漏了 | 低，易修 |
| A | Figure 3（`fig_material_tamper_focus.pdf`）字号太小 | 纯排版问题 | 低，易修 |
| A | §5.3 提到 "explicit LAN/WAN bandwidth and RTT profiles" 却未给出具体数值 | **已核实为真实缺口**：正文和 supplementary 都只给了延迟*结果*，没给建模用的带宽/RTT*输入参数*。已找到实际数值（见 §3）。 | 中，易补 |
| B | "verification" 用词不准，应叫 "feasibility"；VeriEdge 不提供强安全保证，只是 best-effort | 半真半误解。TSTC 本来就自称 "bounded arbitration primitive" 而非密码学证明；但 abstract/贡献点/标题里 "verifiability-constrained placement" 听起来比实际保证强，评审自然觉得用词膨胀。 | 中，措辞/框架问题 |
| B | 公共 ledger 是 overkill，orchestrator 既然被信任，直接用数据库即可 | **抓住了论文没讲清楚的关键点**。威胁模型写的是 "orchestrator trusted to run coordination logic, but not with task plaintext"——这不等于"被信任如实记录历史"。私有 DB 下，行为不当的 orchestrator 可事后篡改 placement/settlement 记录而无人能验证；公共 ledger 提供的是对 **orchestrator 自身不诚实** 的防御（tamper-evidence），而非防外部攻击者。论文隐含了这个动机但没有明说。 | 中高 |
| B | IPFS + 加密没必要，若是开源模型直接哈希+明文即可 | **误解，但责任在论文表述不清**。加密保护的是 `x_j`（私有任务输入 payload），不是 `M_j`（模型本身，模型 ID 是公开描述符的一部分）。论文定义里其实区分清楚了，但显然不够醒目，导致评审读完仍混淆两者。 | 中，讲清楚即可解决 |
| B | 为什么不直接对 endpoint 做基准测试建表，拿 job 去匹配，而不需要这套机制 | **这基本上就是论文已经在做的事**——"Measured verifier profiles"（§3.2 Eq. 1–2）本质上是一张按 (model, boundary, device/backend, sketch, tolerance) 为 key 的离线校准表，候选 placement 拿去查表做准入判断。评审没看出这一点，说明这段内容埋得太深/太数学化，没有一开始就用大白话点明。 | 中，presentation 问题 |

---

## 3. 已核实的补充事实：LAN/WAN 带宽·RTT 数值

来源：
- `experimental_assets/第二轮新增实验/实验B交付物/实验B交付物/脚本与元数据/network_config.md:8-23`
- 同样数值硬编码于 `run_experiment_b_delivery_sweep.py:38,46-56`（以及对应的 `run_experiment_b_delivery_sweep_live_store.py`）

| 参数 | LAN | WAN |
|---|---|---|
| requester 上行带宽 | 940.0 Mbps | 40.0 Mbps |
| store→provider 带宽 | 940.0 Mbps | 80.0 Mbps |
| RTT | 2.0 ms | 80.0 ms |
| 丢包率 | 0.0% | 1.0% |
| 抖动 | 1.5 ms | 25.0 ms |

**注意**：940 Mbps（LAN）是 iperf3 千兆网实测典型有效吞吐；但 WAN 的 40/80 Mbps + 80ms RTT + 1% 丢包只是硬编码的**经验性默认值**，代码/元数据中未发现实测依据或引用来源。这些数值目前只存在于实验交付物中，**没有进入 `main_eurosys.tex` 或 `supplementary_evaluation.tex` 正文**——印证了评审A的质疑。若未来投稿把这些数字补进论文，措辞上要如实说明是 "calibrated/modeled network profile"（论文原话已经这么写），不要暗示是真实链路实测，避免节外生枝。

---

## 4. 后续修订计划（用于下一次投稿，非本次 rebuttal）

### 4.1 易改、低风险（几乎必做）
- [ ] Figure 1（`fig_system_model_workflow.drawio` / `.pdf`）核对并补上 requester → off-chain store 的箭头（对应 Phase 3 / workflowstep 4）
- [ ] Figure 3（`fig_exp_tikz/fig_material_tamper_focus_tikz.tex` 或对应文件）增大字号
- [ ] 在 §5.3（selective delivery microbenchmark）正文或表格脚注中，补上 LAN/WAN 建模用的带宽/RTT/丢包/抖动数值（见上表），并注明是 calibrated model 而非真实链路实测

### 4.2 需要正面论证、不需要改设计
- [ ] 加一段清楚说明"为什么 orchestrator 被信任跑协调逻辑 ≠ 被信任如实记账"，从而证成公共 ledger 的 tamper-evidence 作用（可放在 §2.1 Roles and Trust Boundaries 或 §3 Design 里）
- [ ] 在 Prototype/System Model 中更醒目地强调：加密保护的是私有 payload `x_j`，不是模型权重 `M_j`（模型可以是公开的）——避免评审把两者混为一谈
- [ ] 在 §3.2（Measured verifier profiles）开头用一句大白话先点明"这是一张预计算的兼容性查找表"，再进入数学表述，呼应"为什么不直接查表"的疑问

### 4.3 需要承认边界、可能要加 Discussion / Non-goals 段落
- [ ] 在 Non-goals 段落中明确加一句：VeriEdge 不提供**数据泄露溯源**（leak attribution）；若需要，可以通过给每个 provider 发放重新随机化/加水印的密文副本来扩展 PPD，但这会部分牺牲 PPD 的效率收益——把这个 trade-off 讲清楚而不是回避
- [ ] 考虑在 abstract / 贡献点里把最强的措辞略微收敛（例如更明确使用 "bounded arbitration" 而非单纯 "verification"），但不建议为迎合审稿人换掉整套术语体系，因为正文已经在系统性地限定这个词的含义

### 4.4 尚待确认（下次投稿前）
- 目标 venue：EuroSys 被拒后考虑投哪个 venue？（系统类 vs 更偏安全/隐私的 venue，会影响上述修订的取舍，尤其是 leak-attribution 和 lednecessity 这两点该"加强设计"还是"仅在文字上限定范围"）
- 是否要真的实现 provider-specific re-encryption/watermarking 作为设计扩展，还是仅在 Discussion 里讨论可行性

---

## 5. Recycle 分析：投哪个 CCF-A 会议

（记录日期 2026-07-16，基于当日网络搜索到的各会议 CFP 信息，具体日期以官方 CFP 为准）

### 5.1 候选 CCF-A 会议对比

| 会议 | CCF-A 方向 | 下一轮截稿 | 会议时间/地点 | 与本文契合度 | 需要的改动量 |
|---|---|---|---|---|---|
| **USENIX ATC '27**（现由 ACM SIGOPS 主办） | 体系结构/并行与分布式/存储 | 恢复传统 1 月截稿（具体日期待官方 CFP 公布） | 2027年7月，法国 | **高**——审稿风格偏"扎实系统原型+测量研究"，历史上对"design rationale"追问比 OSDI/SOSP 宽松，审稿人群与 EuroSys 高度重合 | 低~中（对应 §4.1/4.2 的小修+论证路线） |
| **USENIX OSDI '27** | 体系结构/并行与分布式/存储（顶会） | 摘要 2026-12-01 / 全文 2026-12-08 | 2027年7月，美国巴尔的摩 | 高但门槛高——同样的"为什么用 ledger/IPFS"问题在 OSDI PC 会问得更狠，必须实质性补强设计 | 高（对应 §5.2 Option 2：补 accountability 机制） |
| **ACM SOSP**（传统奇数年召开，2027 年符合周期） | 体系结构/并行与分布式（顶会） | 待官方 CFP | 待定 | 同 OSDI，门槛同样高 | 高 |
| **USENIX Security '27** | 网络与信息安全 | 2026-01-26（第一轮；通常有后续轮次） | 待定 | 中——若把"leak accountability"缺口做成真正的安全机制，可以把这篇论文最大的弱点变成安全贡献，但需要更严格的威胁模型/形式化定义 | 高（Option 2 的安全向变体） |
| **NDSS 2027** | 网络与信息安全 | 2026-08-19（夏季轮，已经很紧张）；可能有秋季轮 | 2027年3月，首尔 | 中，同上 | 高，且夏季轮时间上来不及 |
| **ACM CCS 2027** | 网络与信息安全 | 具体日期未查到（常规一年两轮） | 待定 | 中，同上 | 高 |
| **USENIX NSDI '27** | 计算机网络 | 秋季轮：摘要 2026-09-10 / 全文 2026-09-17（已经较近）；春季轮已过 | 2027年5月，美国普罗维登斯 | **低~中**——本文核心贡献是verification/placement准入约束，不是网络协议本身；delivery microbenchmark只是次要实验，NSDI 审稿人可能觉得"网络贡献不够核心" | 若走这条路需重新包装为"去中心化交付"为主线，不建议优先 |

### 5.2 三条可选路径

**路径 A（推荐首选）：USENIX ATC '27，小修 + 论证路线**
- 直接沿用本文件 §4.1/§4.2/§4.3 已列的修订清单：补图、补 LAN/WAN 数值、加 ledger 必要性论证段、澄清 `x_j` vs `M_j`、加 leak-attribution 的 Non-goals 说明。
- 时间最从容（距离预计截稿约6个月），工作量最小，风险最低。
- 局限：核心设计（ledger、IPFS、PPD 不可追责泄露）本身没变，如果 ATC 审稿人里恰好也有类似"系统极简主义"倾向的评审，同样的批评可能复现——但用诚实的 Non-goals + 论证段正面接住，通过概率仍显著高于本次。

**路径 B（更高档位，工作量大）：USENIX OSDI '27，实质性重新设计**
- 针对 Review A 最锋利的批评（PPD 下无法追责数据泄露），真正设计并实现一个扩展机制——例如给每个 selected provider 发放经过重新随机化/加水印的密文副本（在 broadcast encryption 或 proxy re-encryption 框架下），用可控的额外开销换回 leak attribution 能力，并做该机制的 evaluation（对比纯 PPD 的效率损失）。
- 截稿 2026-12-08，时间够但工作量显著更大：本质上是在原论文基础上新增一个子系统 + 一组新实验。
- 收益：直接把评审A最大的弱点变成论文的差异化贡献，也顺带回应了评审B"ledger到底为什么需要"的质疑（因为新机制天然需要一个可审计、防篡改的记录来追责）。

**路径 C（转型，高风险高回报）：安全会议（USENIX Security / CCS / NDSS）**
- 把"leak attribution"和"orchestrator 不可信记账"的威胁模型正面做成安全贡献，补充形式化定义/安全博弈，论文整体从"系统论文"改写为"可追责去中心化推理的安全机制"论文。
- 时间压力大（NDSS 夏季轮已来不及，USENIX Security 第一轮1月26截止较紧），且安全会议对形式化程度要求远高于系统会议，返工量最大。
- 只有在你确实想把 leak-accountability 机制做实（路径 B 的工作量）、且愿意再补形式化安全论证的前提下才值得走这条路，否则性价比不如路径 A/B。

**不建议：NSDI**——本文核心不是网络协议问题，delivery microbenchmark 分量不够撑起 NSDI 的评审预期，秋季轮时间也偏紧。

### 5.3 纯中稿概率视角（不计返工量，只问"投哪儿命中率最高"）

> 这一节的优化目标与 §5.2 不同。§5.2 是"性价比"视角（首选 ATC，因为改动小）；本节假设**不考虑工作量和是否需要大重构**，只问哪里中稿概率最高。结论与 §5.2 **故意相反**。

**核心判断：这篇论文在系统类会议是"逆风"，在安全类会议是"顺风"。**

两条 EuroSys 审稿意见的本质，不是孤立技术挑刺，而是**顶级系统会议评审群体对"去中心化/区块链味"工作的系统性排斥**：
- 评审B："blockchain/ledger 是 overkill"、"IPFS 没必要"、"verification 用词不对、没有强安全保证"。
- 评审A："号称 accountability，却无法追责数据泄露"。

同一批弱点，换到不同社区，性质完全不同：

| | 系统 venue（OSDI/SOSP/ATC/EuroSys） | 安全 venue（USENIX Sec/CCS） |
|---|---|---|
| ledger / commitment / IPFS | 被质疑"overkill"，需反复辩护 | 可审计/防篡改记账是标配动机，母语 |
| "verification 不算强保证" | 扣分项 | 规定动作——本来就要求写严威胁模型与保证边界 |
| "泄露不可追责"（评审A） | 致命伤 | 天然贡献位（leak attribution / traitor tracing） |

**同一批弱点，在系统 venue 是致命伤，在安全 venue 是"待填的贡献位"。** OSDI/SOSP 对 blockchain-flavored 设计天生高度怀疑，评审B那句"为什么要区块链"只会问得更狠——因此纯概率视角下 **OSDI/SOSP 是这篇论文最差的去处**，ATC 只是"同一批人、同样偏见"的稍好版本。

四个候选（OSDI/ATC/USENIX Sec/CCS）接收率都在 15–20%，接收率不是区分点；**venue fit（论文气质是否顺着社区口味）才是**。本文顺安全、逆系统。

**为什么在安全会议里选 USENIX Security：**
- 四大安全顶会里最"系统友好"，接受 systems-security / measurement / best-effort 机制类工作；不像 IEEE S&P（Oakland）偏向强形式化保证与新攻击——本文"best-effort arbitration primitive"的定位在 Oakland 易被嫌保证不够硬，在 USENIX Security 站得住。
- ML security 是当前大热 track，"LLM 推理外包 + 可验证性"正卡在风口。
- 一年两个 cycle = 更多射门机会。
- **CCS 作为第二选择**（同为 CCF-A，对系统/ML 安全都友好），可作为不同 cycle 之间的备胎。

> 勘误：§5.1 表格把 NDSS 标为 CCF-A 不够严谨——NDSS 在 CCF 目录中的定级有争议（常被列为 B）。确定为 CCF-A 的安全会议是 **USENIX Security、CCS、IEEE S&P**，以这三个为准。

**纯概率优先级：USENIX Security ≳ CCS ≫ ATC > OSDI/SOSP（对本文框架是负分区）。**

**唯一前提**：投安全 venue 能拉高概率，前提是**真的把论文重心挪到安全叙事**（写严威胁模型、把 leak-attribution 做成真机制、明确 TSTC 保证/不保证什么）。若只是原样换投稿系统，安全评审会用"威胁模型不清、保证太弱"拒掉——那还不如去 ATC。既然本轮决定"不计返工量"，此前提成立。

### 5.4 决定（2026-07-16 确认，含 venue 演变）

决策演变：EuroSys（拒）→ 一度定 USENIX Security（§5.3 纯概率视角）→ **最终定 NDSS 2027 fall 主攻 + ATC 保底**（timing + scope + NDSS 对 best-effort 更宽容三重理由，见下）。

**主攻 venue：NDSS 2027（CCF-A，网络与信息安全）Fall cycle。保底 venue：ATC '27（去区块链化系统论文版本，约 2027-01 截稿）。**

为何 NDSS 优于 USENIX Security（在本 timing-first 策略下）：
- **scope 本命**：NDSS = "Network and **Distributed System** Security"，本文本质即分布式系统安全，正中靶心；NDSS 对实用型/新场景/非强形式化保证的工作**比 USENIX Security 更宽容**，对冲本文 best-effort 软肋。
- **timing 更优**：NDSS summer（5/7）已过，只剩 fall（截稿 **2026-08-19**、通知 **2026-11-04**）；结果比 USENIX Security Cycle 1（~12/4）**早一个月**出，给 ATC（约1月）保底留足余量。
- **序列策略**：NDSS fall 主攻 → 11月初出结果 → 若拒，去区块链化 ATC（约1月）保底。两者时间不冲突。
- **产能前提**：LLM+agent 产能约 3–5X，到 8/19 的窗口 ≈ 传统 ~4–5 个月投入，**本轮做深度安全重构**（威胁模型半形式化 + traitor tracing），真正消除"保证太弱"风险。

CCF 定级勘误：NDSS 确为 **CCF-A**（此前 §5.1/§5.3 一度存疑，作废该疑问）。

NDSS 2027 关键 CFP 事实（2026-07-16 部分查证，**页数/模板/伦理细节以官方 CFP 复核**）：
- Fall cycle 截稿 2026-08-19 (AoE)，通知 2026-11-04，会议 2027-03 首尔。
- 每 cycle 至多 6 投；NDSS 自有双栏模板（正文上限近年约 13 页，需核对 '27）。
- Ethics considerations（以 CFP 为准）；Open Science / Artifact Evaluation（通过 AE 得 badge + 2 页附录）。匿名评审。

详细重构方案见配套文件：**`NDSS27_REVISION_HANDBOOK.md`**（已取代原 USENIX 版手册，后者因过度以两位评审为组织骨架 + ledger 方向判断错误而作废删除）。

---

## 6. 备注
- 本文件为只读记录 + 计划，尚未对 `main_eurosys.tex` 做任何实际修改。
- 相关历史文档：[veriedge_revision_workbook.md](veriedge_revision_workbook.md)、[veriedge_comprehensive_final_revision_runbook.md](veriedge_comprehensive_final_revision_runbook.md)（EuroSys 投稿前的修订记录，供交叉参考）。
