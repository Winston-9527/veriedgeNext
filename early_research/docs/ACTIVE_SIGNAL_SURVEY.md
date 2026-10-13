# 主动信号式推理验证：相关工作调研

- **日期**：2026-10-09
- **问题**：在"边缘节点聚合算力跑大模型"的场景里，有没有人**主动地制造一个专供检测器识别的信号**，而不是在已有表示里找差异（TSTC 的思路）？
- **配套文档**：方法推导见 [QFC_METHOD_DERIVATION.md](QFC_METHOD_DERIVATION.md)
- **可信度说明**：2026 年的 arXiv 论文是通过检索结果和正文概要读到的，引用前请逐篇读原文核对。检索覆盖不可能穷尽，投稿前建议再对 CCS / S&P / USENIX Sec / NDSS 2025–26 做一次定向检索。

---

## 0. 结论

1. 分布式和外包 LLM 推理的验证工作，**绝大多数是被动的**：拿执行方交出来的表示（激活、logits、输出分布）和参考值比较。
2. **主动方向有人碰过，但只做了一半**，可以分成三档：
   - **已知答案探针**（ringer / canary）：信号是预先算好的参考值，检测本质上仍然是"比差异"。
   - **输入侧放大**（敏感样本）：用输入去放大差异，但没有往模型里埋任何东西。
   - **权重侧植入**：机制已经被证明可行（全精度和量化版本行为不同），但用途都是知识产权保护或攻击，**没有人拿它来验证不可信方的执行**。
3. **我们找到的空白**：在下面四条同时满足的组合上，没有检索到先例。
   - 可信的分发方在权重里植入一个**对精度脆弱**的信号；
   - 用**执行方分不清**的探针去触发它；
   - 用途是验证**不可信 provider 的执行精度**；
   - 放在**分片推理**场景里，能做逐段定位。
4. **最大的竞争者**是 Cihangiroglu & Nocera（arXiv 2607.19490，2026 年 7 月）：同样是 P2P 分片 LLM 推理 + canary，但它只做被动比对，诚实噪声是合成的，攻击者也不自适应，而且没有测量化。

---

## 1. 分类框架

按"信号从哪里来"把现有工作分成四档：

| 档位 | 信号来源 | 检测器在做什么 | 代表工作 |
|---|---|---|---|
| **P：被动** | 模型天然产生的表示 | 和参考值或分布比较 | TOPLOC、DiFR、SVIP、TSTC（我们）、MET、IRIS |
| **A1：已知答案** | 验证方预先算好答案的输入 | 比较实际输出和预存答案 | Ringers（2001）、Fusion（2022）、P2P canary（2026） |
| **A2：输入放大** | 验证方挑选或优化出的敏感输入 | 放大后再比较 | Sensitive-Sample（2019）、Not-to-Break（2026） |
| **A3：权重植入** | 可信方事先改造过的权重 | 检测植入的行为是否还在 | Li et al. 2023（IP 保护）、Egashira 2024 / 2026（攻击）、DeepiSign |

我们的方案（QFC）属于 **A3 + A1**：在权重里植入只有全精度才会表现出来的行为，再用已知答案的 canary 去读出。

---

## 2. 逐篇摘要

### 2.1 和我们场景最接近

**[C1] Cihangiroglu & Nocera, *Integrity of peer-to-peer distributed LLM inference under malicious nodes*, arXiv 2607.19490（2026-07）**
- **场景**：P2P 流水线式 LLM 推理，连续若干层分给不同的不可信节点。
- **机制**：
  - 验证方为 n=100 个 canary 预存 fp32 下的逐段激活；
  - canary 从真实流量分布中采样，混进真实请求；
  - 线上流水线跑 fp16，按各分片的相对 L2 偏差 `‖h−a*‖/‖a*‖` 排序，偏差最大的分片被判为恶意。
- **结果**：在 σ_hw=0.002 的合成高斯硬件噪声下，6 种攻击（高斯噪声、符号翻转、缩放）都达到 AUROC=1.0。
- **局限（作者自述）**：
  - 噪声模型是各向同性高斯，而真实漂移是有结构的；
  - 模型只有 124M–410M；
  - 攻击者不自适应，而且每条请求都篡改；
  - σ_hw 接近篡改幅度 ε 时方法失效。
- **和我们的关系**：协议骨架几乎相同，**必须引用并作为 baseline**。它的 canary 只是把 reference 移到了离线，检测仍然是"比差异"，没有制造新信号。我们有真实的异构硬件数据（720 池），正好能打它最弱的假设。

### 2.2 A1：已知答案

**[R1] Golle & Mironov, *Uncheatable Distributed Computations*（CT-RSA 2001）**
- 在志愿计算任务中植入答案已知的 "ringer"：返回结果里没有 ringer，就说明节点没算。
- 这是"主动植入 + 已知答案"思路的鼻祖。
- 只适用于精确计算，不处理诚实的数值漂移。

**[R2] Fusion（Dong et al., 2022）**
- 两方安全图像分类中，把已知答案的样本混进查询。
- 假设结果完全精确，不考虑诚实变化。
- 我们是通过 [C1] 的引用知道这篇的，未读原文。

### 2.3 A2：输入侧放大

**[S1] He, Zhang, Lee, *Sensitive-Sample Fingerprinting of DNNs*（CVPR 2019）/ VerIDeep（arXiv 1808.03277）**
- 优化出一小批输入，让输出对权重的微小改动高度敏感。
- 只用黑盒 API 就能验证云端模型完整性；检测率超过 99.95%，号称零误报。
- **局限**：
  - 优化出来的输入不自然，执行方可以认出探针；
  - 诚实异构漂移和量化同样会被放大，会产生误报；
  - 敏感点在输入侧，**攻击者的廉价模型自己也能感知**（见推导文档 §2 的不确定性升级攻击）。

**[S2] Wilding, Shaker, Ganji, *Not to Break, but to Attest*, arXiv 2608.27954（2026-08）**
- 从重复 token、罕见 token、embedding 扰动等候选中，挑出能放大 logit 漂移的探针。
- 用 Poseidon Merkle 承诺，再用 Groth16 证明部署模型的输出与承诺的基线一致。
- **局限**：缺端到端检测率；校准扰动是 LoRA 和高斯噪声，不代表真实攻击；只测了两个约 1B 的模型。

### 2.4 A3：权重侧植入

**[W1] Li, Jiang, Wang, Ren, Yan, Qiu, *Watermarking LLMs with Weight Quantization*（EMNLP 2023 Findings）**
- **利用全精度权重和量化格点之间的空隙存放水印**：水印在 fp32 下表现出来，量化到 int8 后消失。
- 目的是保护开源模型的知识产权（防止拿 fp32 权重去微调）。
- **对我们的意义**：这是"精度选择性信号"的直接机制先例。我们的用途相反：不是防止别人拿到全精度，而是**验证执行方确实用了全精度**。

**[W2] Egashira, Vero, Staab, He, Vechev, *Exploiting LLM Quantization*（NeurIPS 2024）**
- 三步法：
  1. 先微调出恶意模型；
  2. 算出所有"量化后等于该恶意模型"的全精度权重构成的盒约束；
  3. 在盒内做 PGD，把全精度版本的行为洗回良性。
- 结果是全精度良性、量化后恶意。
- **对我们的意义**：把方向反过来用就是我们的植入算法——在"量化结果不变"的盒内做 PGD，让全精度版本带上秘密行为。

**[W3] Zhan, Egashira, Staab, Vero, Vechev, *Widening the Gap: Exploiting LLM Quantization via Outlier Injection*, arXiv 2605.15152（2026-05）**
- 注入离群值，让同组其他权重在量化时被舍入为 0。
- 把 [W2] 的攻击扩展到 AWQ、GPTQ 和 GGUF I-quants。
- **对我们的意义**：说明"全精度与量化行为分离"可以覆盖带误差补偿的量化器，对应我们的假设 A3。

**[W4] DeepiSign（arXiv 2101.04319）/ DeepiSign-G（arXiv 2407.01260）**
- 脆弱水印：把秘密和它的哈希嵌入权重的小波 / Walsh-Hadamard 系数，任何改动都会破坏水印。
- **前提是验证方能直接读取权重**，所以不适用于远程推理。

**[W5] Sigil, arXiv 2511.14422**
- 在 split federated learning 的激活空间里定义秘密约束，通过梯度注入把水印嵌进客户端模型。
- 用途是证明模型归属，不验证执行。

**鲁棒指纹（iSeal arXiv 2511.08905、各类 backdoor 指纹）**
- 设计目标是量化后仍然保留，和我们需要的"脆弱"正好相反。

### 2.5 P：被动方法（主流）

| 工作 | 机制要点 | 局限（就本问题而言） |
|---|---|---|
| **TOPLOC**（Prime Intellect, 2025） | 对末层 top-k 激活做局部敏感哈希，验证方复算比对 | 需要复算；对精度降级的区分依赖阈值 |
| **DiFR**（arXiv 2511.20621） | Token-DiFR / Activation-DiFR，在非确定性下做推理验证 | 需要权重和复算 |
| **SVIP**（NeurIPS 2025, arXiv 2410.22307） | 返回 hidden states，验证方用保密的 proxy head 判断是否来自指定模型；FNR<5%，FPR<3% | 主要针对换成小模型；信号是天然表示，不是植入的 |
| **Model Equality Testing**（arXiv 2410.20247） | 用 MMD 检验 API 输出分布 | 黑盒统计量，对量化不敏感 |
| ***Are You Getting What You Pay For?***（arXiv 2504.04715） | 审计 API 偷偷换模型，包括 INT8 / FP8 / NF4 量化替换 | 结论是仅凭文本输出很难检出量化替换，这正是我们的动机 |
| **IRIS**（arXiv 2607.20860） | 有预算的黑盒审计，覆盖模型替换和路由稀释 | 被动；用随机生成探针 |
| ***One Token Is Enough***（arXiv 2607.10252） | 单 token 输出分布的 JS 散度指纹 | 被动 |
| **Rank-Based Uniformity Test**（arXiv 2506.06975） | 黑盒 API 审计 | 被动 |
| **VeriLLM**（arXiv 2509.24257） | 承诺 + VRF 抽取 hidden-state 位置做链上比对 | 需要复算 |
| **TensorCommitments**（arXiv 2602.12630） | 轻量张量承诺 | 被动 |
| **Proof of Sampling**（Hyperbolic, arXiv 2405.00295） | 博弈论抽样复算 | 需要复算 |
| **Weight-exfiltration 推理验证**（arXiv 2511.02620） | 验证推理以检测权重外泄 | 被动 |
| **TSTC（我们，main_ndss.tex）** | 分片边界 sketch + 校准容差 + 首个越界点定位 | 见 §3 |

---

## 3. 逐项对比表

图例：✅ 支持 / ⚠ 部分支持或有条件 / ❌ 不支持 / — 不适用

| 维度 | TSTC（现有） | P2P canary [C1] | Sensitive-Sample [S1] | Not-to-Break [S2] | SVIP | Quant-WM [W1] | **QFC（拟议）** |
|---|---|---|---|---|---|---|---|
| 信号档位 | P | A1 | A2 | A2 | P（加秘密） | A3 | **A3 + A1** |
| 谁嵌入信号 | — | 验证方（预存答案） | 验证方（优化输入） | 验证方（挑选输入） | — | 模型所有者 | **可信分发方（权重）+ 验证方（canary）** |
| 读出位置 | 分片边界 sketch | 分片边界激活 | 输出 | logits（经 ZK） | hidden states | 输出 | **输出 token（黑盒）** |
| 要不要在线复算 | ✅ 要（成本痛点） | ❌ 不要（预存） | ❌ 不要 | ❌ 不要 | ❌ 不要 | ❌ 不要 | **❌ 不要（只比 token）** |
| 目标威胁 | 篡改、跳层、替换分片 | 激活篡改 | 任意模型改动 | 模型改动 | 换小模型 | 知识产权 | **精度降级、量化替换** |
| 对诚实异构漂移的处理 | 校准阈值，有重叠 | 合成高斯，未用真实数据 | 未考虑 | 未考虑 | 训练覆盖 | — | **植入时做鲁棒训练，有可推导的精度窗口** |
| 精度降级检出 | ⚠ 只能和漂移拼阈值 | ❌ 未测 | ⚠ 会和诚实漂移混淆 | ⚠ | ⚠ | 机制有，但不是用来检测的 | **✅ 设计目标** |
| 抗不确定性升级攻击 | — | ⚠ 未分析 | ❌ 敏感点廉价模型可感知 | ❌ | — | — | **✅ 量化模型的计算过程与植入完全无关（引理 1）** |
| 探针不可区分 | — | ✅ 同分布采样 | ❌ 输入不自然 | ❌ 重复 / 罕见 token | — | — | **✅ 自然 prompt 当触发器** |
| 分片定位 | ✅ 首个越界点 | ✅ 偏差排序 | ❌ | ❌ | ❌ | ❌ | **✅ 逐层块独立的触发器族** |
| 对已知方法的攻击者（Kerckhoffs） | ⚠ 公开投影 P 的零空间、scale 盲区 | ⚠ 未分析 | ⚠ | ⚠ | ⚠ 依赖秘密 | — | **⚠ 依赖假设 A1：触发器难以从权重反推** |
| 需要改模型 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | **✅（一次性离线 PGD）** |
| 已知的定量盲区 | projcos 对 scale 扰动 TPR 0.0107；projscalar 对零空间攻击 TPR 0 | 噪声接近 ε 时失效 | 误报 | 缺端到端率 | 替换为相近模型 | — | **诚实规格为 bf16、作弊为 int8 时窗口太窄（推导 §5）** |

---

## 4. 对我们的含义

- **可以主张的新意**：把 A3 的机制（[W1]、[W2]、[W3]）用到"验证不可信执行"这个用途上，并放进分片推理场景。具体是：
  1. 用盒约束植入，让量化模型的计算过程和植入完全无关，从而**在构造上抵抗不确定性升级攻击**——这是 A1 和 A2 都没有的性质；
  2. 用逐层块的触发器族做定位；
  3. 在真实异构硬件上推导并测量精度窗口。
- **审稿人会说的话**："这是 [W2] 加 [C1] 的组合。"回应方式是：上面三点是组合本身才会遇到的难点，[W2] 和 [C1] 都没处理。
- **必须做的 baseline**：
  - [C1] 风格的被动 canary，在真实漂移上跑；
  - 自然 top-1 翻转式 canary，包括它在不确定性升级攻击下的表现；
  - TSTC 的 projcos4 和 projscalar1_abs。

## 参考链接

- [C1] https://arxiv.org/html/2607.19490v1
- [R1] https://www.microsoft.com/en-us/research/?p=145466
- [S1] https://openaccess.thecvf.com/content_CVPR_2019/html/He_Sensitive-Sample_Fingerprinting_of_Deep_Neural_Networks_CVPR_2019_paper.html ・ https://arxiv.org/pdf/1808.03277
- [S2] https://pith.science/paper/2608.27954
- [W1] https://arxiv.org/abs/2310.11237
- [W2] https://papers.nips.cc/paper_files/paper/2024/hash/496720b3c860111b95ac8634349dcc88-Abstract-Conference.html
- [W3] https://arxiv.org/abs/2605.15152
- [W4] https://ar5iv.labs.arxiv.org/html/2101.04319 ・ https://arxiv.org/pdf/2407.01260
- [W5] https://arxiv.org/html/2511.14422
- SVIP https://arxiv.org/html/2410.22307v2 ・ DiFR https://arxiv.org/pdf/2511.20621 ・ MET https://arxiv.org/pdf/2410.20247
- Substitution audit https://arxiv.org/html/2504.04715 ・ IRIS https://arxiv.org/pdf/2607.20860 ・ One Token https://arxiv.org/html/2607.10252
- Rank test https://arxiv.org/pdf/2506.06975 ・ VeriLLM https://www.arxiv.org/pdf/2509.24257 ・ TensorCommitments https://arxiv.org/html/2602.12630
- PoSP https://arxiv.org/html/2405.00295 ・ Exfiltration https://arxiv.org/pdf/2511.02620 ・ iSeal https://arxiv.org/html/2511.08905v1
