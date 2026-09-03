# 论文1实验补全手册

项目名称：

`VeriEdge: Verification-Aware Orchestration for Trustworthy Decentralized Edge LLM Inference`

主稿文件：

- [eurosys_draft.tex](C:/Users/Win10%20Pro/Desktop/A_Blockchain_Based_Resource_Allocation_Mechanism_for_Edge_AI_Networks/paper1_veriedge/eurosys_draft.tex)

配套材料：

- [PAPER1_RESTRUCTURE_PLAN.md](C:/Users/Win10%20Pro/Desktop/A_Blockchain_Based_Resource_Allocation_Mechanism_for_Edge_AI_Networks/paper1_veriedge/PAPER1_RESTRUCTURE_PLAN.md)
- [PAPER1_STUDENT_TASK_BOARD.md](C:/Users/Win10%20Pro/Desktop/A_Blockchain_Based_Resource_Allocation_Mechanism_for_Edge_AI_Networks/paper1_veriedge/PAPER1_STUDENT_TASK_BOARD.md)
- [evidence_ledger.md](C:/Users/Win10%20Pro/Desktop/A_Blockchain_Based_Resource_Allocation_Mechanism_for_Edge_AI_Networks/paper1_veriedge/notes/evidence_ledger.md)

## 手册目的

这份手册的作用，是让“论文主稿继续写”和“关键实验继续补”能够并行推进，而且两条线始终围绕同一个核心问题展开：

`verification-aware orchestration for trustworthy heterogeneous decentralized inference`

下面列出的每一组实验，都必须直接服务于这条主线。如果某个实验不能明显增强这句话，它就不应占用当前最关键的时间和资源。

## 论文主张与实验映射

| 主张编号 | 论文中的核心主张 | 必须补的实验 |
| --- | --- | --- |
| C2 | PPD 在当前评估路径上可以降低任务分发开销 | `E5`，以及可选的 `E6` |
| C4 | 严格 THC 在诚实异构执行下非常脆弱 | `E1` |
| C5 | TSTC 能在保留检测/定位能力的同时降低误报 | `E1 + E2 + E3` |
| C6 | TSTC 的 tolerance 设计具有可解释的响应行为 | `E2` |
| C7 | 多节点协同执行会引入真实协调开销 | `E4` |
| C8 | 编排策略应该显式考虑网络成本与验证风险 | `E4 + E5` |

## 实验优先级

除非受硬件条件阻塞，否则按下面顺序推进：

1. `E1` 真实异构 honest-honest paired capture
2. `E2` verifier ablation
3. `E3` attack coverage
4. `E4` verifier operational overhead
5. `E5` verification-aware placement comparison
6. `E6` deployment / delivery 扩展实验

## E1：真实异构 honest-honest paired capture

### 实验目标

把当前部分依赖 synthetic heterogeneity 的 verifier 叙事，替换为真实硬件 / 真实后端组合下的直接证据。

### 为什么最关键

这是论文1当前最重要的一组补实验。如果没有它，审稿人很容易认为 TSTC 主要是在“校准过的环境”或“人工噪声注入环境”里有效，而不是真正解决了异构执行问题。

### 最低实验设置

- 所有设备使用同一组 prompt
- 所有设备使用同一 shard plan
- 至少覆盖 3 组硬件 / 后端组合
- 推荐组合：
  - Mac mini M4 + Metal/int8
  - Mac mini M4 + BF16
  - Linux RTX3090 + FP32 或 BF16

### 实验协议

1. 固定一组 calibration prompts 和一组完全不重叠的 evaluation prompts。
2. 对每个设备 / 后端组合，在相同 shard plan 下执行同一批 prompts。
3. 直接从真实执行路径采集 `C1`、`C2`、`C3` 三个 shard-boundary checkpoints。
4. 构造设备两两之间的 honest-honest 对照。
5. 在完全相同的 checkpoint traces 上同时评估 THC 和 TSTC。

### 需要报告的指标

- false-positive rate
- 各 checkpoint 的 mismatch 分布
- honest-honest 条件下的 localization 应为 `N/A` 或空值
- 可选：各设备组合之间的数值漂移统计

### 主文预期产出

- 一张替换或强化当前 heterogeneity comparison 的核心图
- Section 6.3 的一段核心结果分析

### 附录建议产出

- 设备两两组合的详细表格
- calibration / evaluation split 的详细说明

### 建议负责人

- `Owner C`

## E2：Verifier Ablation

### 实验目标

证明 TSTC 的设计选择不是拍脑袋调出来的，而是有清晰设计动机和 operating point 的。

### 必须回答的问题

- sample size 如何影响 FPR、TPR 和 runtime？
- tolerance 如何影响 FPR 与 TPR？
- checkpoint-specific tolerance 是否优于单一全局 tolerance？
- 哪个 checkpoint 对误报最敏感？

### 实验协议

至少做以下 sweep：

- sample size：`4, 8, 16, 32, 64`
- tolerance scale：围绕当前 calibration 值做 `0.5x, 1x, 1.5x, 2x`
- tolerance mode：
  - checkpoint-specific
  - global shared tolerance

运行场景至少包括：

- honest homogeneous
- 来自 `E1` 的 real honest heterogeneous
- 来自 `E3` 的 tamper traces

### 需要报告的指标

- false-positive rate
- true-positive rate
- localization accuracy
- verifier runtime per trace

### 主文预期产出

- Section 6.4 的一张 ablation 图
- 一段解释为什么当前 operating point 合理的文字

### 附录建议产出

- 全量 sweep 表格

### 建议负责人

- `Owner C`

## E3：Attack Coverage

### 实验目标

证明 TSTC 不只是对 Gaussian noise 有响应，而是对真正和 decentralized inference 相关的攻击模式也有意义。

### 最低攻击集合

- random perturbation
- single-shard malicious recomputation
- boundary tensor replacement
- stale replay of earlier checkpoint
- cross-checkpoint coordinated tampering
- adaptive evasion against sampled coordinates

### 实验协议

对每类攻击都要明确：

1. 攻击者控制了什么
2. 攻击注入在哪个 checkpoint / 哪个 shard
3. THC 和 TSTC 各自是否触发
4. first mismatch 被定位到哪里

### 需要报告的指标

- true-positive rate
- localization accuracy
- 各攻击类型的 miss rate
- 可选：不同攻击强度下的 detection threshold

### 主文预期产出

- 一张 attack coverage 汇总表
- Section 6.3 或 6.4 中一段攻击面分析

### 附录建议产出

- 各攻击实现细节

### 建议负责人

- `Owner C`

## E4：Verifier Operational Overhead

### 实验目标

把 verifier 的证据从“能检测”推进到“有系统部署意义”。

### 必须测的量

- 每个任务的 checkpoint capture size
- 每个任务的 commitment size
- verifier replay runtime
- end-to-end challenge latency
- validator 侧存储占用

### 实验协议

至少在以下三种 trace 上测量：

- honest trace
- challenged trace
- tamper 或 failed challenge trace

如果条件允许，尽量把时间拆成：

- capture
- commitment generation
- replay
- verdict emission

### 主文预期产出

- Section 6.4 中一张开销表
- 只有完成这组实验后，abstract 里才适合更强地写 deployability 相关表述

### 附录建议产出

- 按 checkpoint / shard count 的详细 breakdown

### 建议负责人

- `Owner C`

## E5：Verification-Aware Placement Comparison

### 实验目标

把论文1从“verifier + system wrapper”推进成真正的 orchestration 系统稿。

当前主稿里已经有一个基于现有 EXO deployment trace 的 `proxy` 结果图：它直接展示了随着协同宽度增加，系统会同时走向更高 latency inflation 和更低 success retention。学生后续要补的，不是从零开始画 E5，而是在这个 proxy 结果之上，把它推进成完整的 policy comparison。

### 必须比较的策略

- random placement
- cost-only placement
- reputation-aware placement
- network-aware placement
- verification-aware placement

### verification-aware 特征建议

- 预期 WAN 传输代价
- 预期协同宽度惩罚
- provider 的近期 challenge rate
- 基于设备 / 后端组合的 heterogeneity-risk proxy

### 工作负载要求

- 尽量与 Section 6.1 使用相同任务族，保证可比性
- 如果可能，加入 honest + adversarial mixed traces
- 至少增加一个 multi-task 或 queued setting

### 需要报告的指标

- task latency
- success rate
- challenge rate
- verifier workload
- goodput
- 可选：requester-visible completion utility

### 主文预期产出

- Section 6.5 的一张图或一张表
- 一段明显更强的 orchestration takeaway
- 如果新实验暂时来不及，至少要把当前 proxy 结果扩成 `policy -> metrics` 的直接对照

### 建议负责人

- `Owner A` + `Owner C`

## E6：Deployment / Delivery 扩展实验

### 实验目标

增强 verifier 之外的系统证据，让整篇文章更像系统论文，而不只是验证论文。

### 子任务

#### E6a：并发部署工作负载

- 增加 multi-task 或 queued runs
- 观察任务重叠时 coordination bottleneck 是否变得更严重

#### E6b：更大的 prompt mix 或第二类 workload

- 尽量超出当前单一 workload family

#### E6c：PPD 的 winner-group-size scaling

- 改变 winner count
- 测量 winner group 增大时 PPD 优势是否扩大

### 主文预期产出

- 最强结果优先进入 Section 6.1 或 6.2
- 较弱扩展结果可以放 appendix

### 建议负责人

- `Owner A` 负责 deployment
- `Owner B` 负责 delivery scaling

## 交付格式

每个实验负责人最终都必须提交：

1. 一份 `results.md`
2. 一份原始汇总数据文件，格式可以是 CSV 或 JSON
3. 一张可直接用于论文的 figure 或一张 table
4. 一份明确指出应补入 `eurosys_draft.tex` 哪一节的 patch proposal

## 论文插入位置映射

| 实验 | 建议插入章节 |
| --- | --- |
| E1 | Section 6.3 |
| E2 | Section 6.4 |
| E3 | Section 6.3 或 6.4 |
| E4 | Section 6.4 |
| E5 | Section 6.5 |
| E6a | Section 6.1 |
| E6b | Section 6.1 或 appendix |
| E6c | Section 6.2 或 appendix |

## 完成判据

一个实验不是“画出图”就算完成。只有同时满足下面四条，才算完成：

- 它支持的论文主张已经写回正文
- 图或表已经有最终 caption
- 结果已经有一句明确的 systems takeaway
- 原始数值已经保存，便于后续复核

## 最后提醒

这份手册的目标不是把实验越做越多，而是尽快闭合论文1最小必要的证据链：

- decentralized inference 确实存在协同执行成本
- selective disclosure 确实改善数据路径
- strict deterministic verification 在 heterogeneity 下确实失效
- TSTC 确实改善了这个 tradeoff
- orchestration 确实应该同时考虑网络代价和验证风险
