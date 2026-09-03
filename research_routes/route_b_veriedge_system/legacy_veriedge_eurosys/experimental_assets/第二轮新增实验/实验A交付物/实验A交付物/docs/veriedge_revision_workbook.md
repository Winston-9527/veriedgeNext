# VeriEdge 论文修订工作手册

**目标会议**：EuroSys  
**当前建议题目**：**VeriEdge: Verifiability-Constrained Placement for Heterogeneous Edge LLM Inference**  
**手册版本**：2026-05-13  
**适用对象**：论文主笔、实验负责人、学生执行者  
**核心策略**：补系统闭环，不补 verifier 炫技。

---

## 0. 一页总览

### 0.1 本轮修订的中心判断

新题目已经把论文重心从泛化的 “verification-aware orchestration” 收紧到：

> **用 measured verifier profile 作为 placement 的约束，让 heterogeneous edge LLM inference 的执行组选择同时满足性能、披露边界和可裁决性。**

这与当前稿子的最强系统线索一致：当前稿子已经把 placement 描述为 data boundary、execution boundary 和 evidence boundary；也已经有 placement replay 表显示 risk-constrained / adaptive-verifier policy 能降低 infeasible usage 和 challenge workload。现在要做的不是扩展 verifier 攻击族，而是把这些已有材料改写成一个清晰的 closed-loop placement story。

### 0.2 本轮最低成本实验包

只做两个实验，也可以支撑新题目：

| 优先级 | 实验 | 目标 | 最低交付 |
|---:|---|---|---|
| 1 | **Closed-loop verifiability-constrained placement replay** | 证明 measured verifier profile 不是事后评估，而是 placement admission constraint | policy ablation + alpha sweep + placement frontier figure |
| 2 | **Selective delivery group-size sweep** | 证明 placement 决定 data boundary，且 group width 增大时 PPD 比 RPD 更可扩展 | fixed 100MB, k=1/2/4/8, LAN+WAN, median/p95/egress |

### 0.3 本轮不建议主攻的实验

| 不主攻项 | 原因 |
|---|---|
| 大规模真实 edge deployment | 成本高，变量难控，容易稀释主线 |
| 新增大型模型或完整 decode-path | 有帮助但不是当前 title 的必要证据 |
| ZK / cryptographic proof integration | 会改变论文定位，且与 “bounded arbitration evidence” 冲突 |
| 更复杂的 market / auction | EuroSys reviewer 更关心 systems evidence，不会因市场机制复杂而自动加分 |
| verifier 攻击族大扩展 | 现在最危险的是系统证据不闭环，而不是 verifier 不够花哨 |

---

## 1. 新题目带来的修订约束

### 1.1 新题目是加分项

题目：

> **VeriEdge: Verifiability-Constrained Placement for Heterogeneous Edge LLM Inference**

这个题目比旧题目更适合当前论文，因为它把 contribution 绑定到 placement，而不是泛泛地说 orchestration。EuroSys reviewer 看到这个题目后，会自然期待三件事：

1. **Placement 有正式定义**：不仅是 latency/cost ranking，而是包含 verifiability constraints。
2. **Verifiability 是 measured profile**：来自真实 heterogeneous stack 的 FPR/TPR/cost，而不是抽象假设。
3. **Placement 结果改变系统 frontier**：降低不可裁决 placement、false dispute risk、challenge cost，同时尽量不牺牲 goodput。

### 1.2 需要避免的题目—正文冲突

| 潜在冲突 | 当前风险 | 修订动作 |
|---|---|---|
| `constrained` 比 `aware` 强 | 如果正文只写 weighted score，会显得题目夸大 | 把主 policy 改成 hard feasibility filtering；risk-weighted 作为 ablation |
| `placement` 是题目中心 | 当前 Evaluation 是 verifier-first | Evaluation 改成 placement-first；verifier section 降为 profile construction |
| `heterogeneous` 是题目关键词 | 若只展示 verifier 表，系统必要性不够 | 加 homogeneous-only 或 same-backend-only replay baseline，哪怕只做低成本版本 |
| `edge LLM inference` 是系统语境 | 若 delivery 实验只有 100MB 单点，会显得 evidence thin | 加 group-size sweep，体现 placement width 对 disclosure cost 的影响 |

---

## 2. 论文修订总路线

### 2.1 一句话主张

建议全篇统一到下面这一句：

> VeriEdge treats verifiability as a placement feasibility constraint: before disclosing task access, the orchestrator selects a heterogeneous edge execution group only if its measured verifier profile can satisfy task-level false-dispute, tamper-detection, sketch-budget, and challenge-cost targets.

中文解释：

> VeriEdge 的核心不是“有一个 verifier”，而是“placement 时就知道哪些 heterogeneous device/backend/sketch 组合可裁决、哪些必须升级 sketch、哪些必须避免”。

### 2.2 三条 claims

| Claim | 机制 | 证据 |
|---|---|---|
| C1. Placement defines accountability boundary | commit \((G, \sigma, \vartheta)\) before disclosure | system model + selective delivery sweep |
| C2. Verifiability is measured, not assumed | verifier profile: FPR/TPR/LocAcc/sketch cost/challenge ms | existing TSTC/THC/profile measurements |
| C3. Measured verifiability constrains placement | hard feasibility constraints + adaptive verifier selection | closed-loop placement replay |

### 2.3 建议 Evaluation 顺序

采用 **placement-first** 顺序：

1. **E1. Closed-loop verifiability-constrained placement**  
   证明 measured verifier profile 改变 placement frontier。
2. **E2. Sensitivity to verifiability targets**  
   扫 \(\alpha\)，证明不是 cherry-picked single point。
3. **E3. Selective delivery under placement width**  
   证明 committed placement 是 data boundary，且 PPD 随 group size 更可扩展。
4. **E4. Measured verifier profile construction**  
   原有 THC/TSTC、hard pair、overhead 结果作为 profile 的来源。
5. **E5. Scope and limitations**  
   明确不是 semantic proof，不覆盖 fully colluding self-consistent evidence。

---

## 3. 写作修订工作清单

### 3.1 Title

替换为：

```latex
\title{\system: Verifiability-Constrained Placement for Heterogeneous Edge LLM Inference}
```

### 3.2 Abstract 改写模板

目标：placement-first，少讲 verifier 技巧，多讲 measured profile → constraint → placement frontier。

```text
Heterogeneous edge LLM inference is usually treated as a resource-placement problem: select idle devices, split a model, and execute. We argue that dependable edge inference must additionally treat verifiability as a placement constraint. A placement determines not only latency and capacity, but also who receives task access, which heterogeneous device/backend mix produces boundary states, and whether a disputed execution can be adjudicated under bounded evidence.

We present VeriEdge, a verifiability-constrained placement framework for heterogeneous edge LLM inference. VeriEdge profiles device/backend/sketch signatures using checkpoint-sketch verification, then admits a candidate placement only if its measured false-dispute rate, tamper-detection rate, sketch budget, and challenge cost satisfy task-level targets. The selected group, shard map, and verifier policy are committed before task disclosure; only selected providers receive encrypted task-access material.

Our evaluation shows that strict tensor hashing is unusable under honest heterogeneous execution, while compact TSTC profiles expose which stack pairs are low-risk, high-risk, or inadjudicable. In placement replay, verifiability-constrained policies remove infeasible placements and reduce expected challenge workload while preserving queued-workload goodput relative to network-aware placement. A selective-delivery sweep further shows that placement-defined disclosure scales with group width, replacing replicated payload-sized transfers with one ciphertext publication and small per-provider access packages. VeriEdge does not provide a universal semantic correctness proof; it provides measured, policy-scoped arbitration evidence that becomes visible before placement.
```

填入数据时注意：

- 如果只保留现有 single 100MB result，不要写 “sweep”。
- 做完 group-size sweep 后，写具体 \(k\) 范围、LAN/WAN、median/p95 reduction。
- 如果没有补 verifier CI/hybrid，不要写 “detects all tampers”。

### 3.3 Introduction 改写要求

Intro 中要强化以下顺序：

1. Edge LLM inference 是 heterogeneous placement problem。
2. 但 placement 不只是 latency/capacity。
3. Placement 同时定义：
   - data boundary：谁收到 key/locator；
   - execution boundary：哪些 device/backend 产生 numerical drift；
   - evidence boundary：哪些 checkpoint/sketch 可以被 challenge；
   - settlement boundary：mismatch 如何映射到 provider 或 boundary。
4. 因此需要 **verifiability-constrained placement**。

建议加入一句硬定义：

```text
A placement is admissible only if the selected group, shard map, and verifier policy produce an adjudicable execution signature under the task's false-dispute, detection, sketch-budget, and challenge-cost targets.
```

### 3.4 Placement formalization 必改

把当前偏 weighted score 的 formulation 改为：先过滤 feasible set，再优化 latency/cost。

#### 3.4.1 Feasibility definition

```latex
\begin{aligned}
\mathrm{Feasible}(G,\sigma,\theta;\rho_j) \iff
&\ \widehat{\mathrm{FPR}}_{G,\sigma,\theta} \le \alpha_j, \\
&\ \widehat{\mathrm{TPR}}_{G,\sigma,\theta} \ge \beta_j, \\
&\ B_\theta \le B_j, \\
&\ C^{\mathrm{verify}}_{G,\sigma,\theta} \le C_j^{\max}, \\
&\ \mathrm{Cap}(G,\sigma) \ge d_j, \\
&\ |G| \le k_j^{\max}.
\end{aligned}
```

其中：

- \(\alpha_j\)：task-level false-dispute target。
- \(\beta_j\)：task-level tamper-detection target。
- \(B_j\)：sketch/reveal budget。
- \(C_j^{\max}\)：challenge-time verification budget。
- \(\theta\)：sketch/verifier mode，例如 scalar16, projcos4, projcos16。

#### 3.4.2 Aggregation rule

如果一个 placement 有多个 boundary pair，最低成本版本使用保守聚合：

```text
FPR_G = max over checked boundary signatures
TPR_G = min over checked boundary signatures
VerifyCost_G = sum over checked boundary signatures if all checked in a challenge; otherwise expected sum under challenge sampling policy
SketchBytes_G = sum over revealed checkpoint sketches
```

写作时解释：这是 conservative admission rule，避免一个 risky boundary 被平均值掩盖。

#### 3.4.3 Optimization after filtering

```latex
(G_j,\sigma_j,\theta_j) =
\arg\min_{(G,\sigma,\theta) \in \mathcal{F}_j}
\widehat{L}_j(G,\sigma) + \lambda_A \widehat{A}_j(G) - \lambda_\eta \widehat{\eta}(G).
```

#### 3.4.4 Risk-weighted policy 作为 ablation

```text
Risk-weighted placement does not reject candidates violating \alpha/\beta; it only adds estimated risk to the score. We include it to isolate the value of hard verifiability constraints.
```

### 3.5 Contributions 改写模板

```latex
\begin{itemize}[leftmargin=1.5em]
  \item \textbf{Verifiability-constrained placement.}
  We formulate heterogeneous edge LLM placement as a constrained decision in which a candidate group, shard map, and verifier mode must satisfy measured false-dispute, detection, sketch-budget, and challenge-cost targets before task disclosure.

  \item \textbf{A committed accountability boundary.}
  We design VeriEdge to commit the selected group, shard map, and verifier policy before disclosure; the same record governs selective task access, boundary evidence, challenge localization, settlement, and future placement history.

  \item \textbf{Measured profiles and closed-loop evidence.}
  We implement a prototype with selective delivery and a PyTorch sharded-inference verification harness. Our evaluation constructs verifier profiles from heterogeneous checkpoint captures and shows that using these profiles as placement constraints removes inadjudicable placements and reduces challenge workload while preserving useful goodput.
\end{itemize}
```

### 3.6 Discussion / Limitations 改写要求

删掉所有像“实验还没完成”的临时语言。改成 scoped limitation：

```text
The current evaluation is scoped to prefill checkpoint evidence, a modest heterogeneous device pool, and replayed placement workloads. VeriEdge does not prove semantic correctness for every output, and a fully colluding group may produce self-consistent incorrect evidence. The claim is narrower: measured verifier profiles can be exposed to placement so that the orchestrator avoids or upgrades heterogeneous placements that are not cheaply adjudicable under the task policy.
```

### 3.7 Hygiene 必做

| 项目 | 动作 |
|---|---|
| 旧题目 | 全文替换为新题目 |
| `verification-aware` | 主 claim 处改成 `verifiability-constrained`；系统 lifecycle 可保留 `orchestration` |
| 蓝色修订痕迹 | 删除所有 `\color{blue}` / `\textcolor{blue}` |
| figure slot | 提交版不能出现 placeholder |
| `.drawio` | `\includegraphics` 统一指向 `.pdf` |
| 数字一致性 | Abstract、Intro、Evaluation、Conclusion 数据必须完全一致 |
| 强安全措辞 | 避免 `detects all tampers`；改为 `under evaluated non-adaptive material tamper families` |
| conference metadata | 检查 EuroSys 年届次、地点、日期是否正确 |

---

# Part II. 实验手册

本部分写给学生执行者。目标是让学生不需要重新理解整篇论文，也能知道要跑什么、如何记录、如何回填、图如何画、结果如何交付。

---

## 4. 实验 A：Closed-loop Verifiability-Constrained Placement

### 4.1 实验目标

证明：**measured verifier profile 可以作为 placement 的硬约束，改变 heterogeneous edge LLM inference 的 placement frontier。**

不要把这个实验写成 “placement policy comparison” 的普通 replay。它必须回答：

> 如果 orchestrator 在 placement 前知道某个 device/backend/sketch signature 的 FPR/TPR/verification cost，它会不会避免不可裁决 placement、升级 verifier mode，或者在类似 goodput 下显著降低 dispute risk？

### 4.2 核心假设

H1. Network-aware 或 cost-only placement 会选择一些低 latency 但不可裁决的 heterogeneous pairs。  
H2. Verifiability-constrained placement 会过滤这些 pairs，使 infeasible usage 降到接近 0。  
H3. 在 queued workload 下，过滤 risky signatures 不一定显著损失 goodput。  
H4. Adaptive-verifier policy 可以通过升级 sketch mode 保留更多 candidate，同时满足 \(\alpha,\beta\) target。

### 4.3 输入数据

必须准备三个输入文件。

#### 4.3.1 `data/profile_matrix.csv`

每一行是一个 measured verifier signature。

```csv
profile_id,pair_id,stack_a,stack_b,boundary,sketch,bytes_ckpt,bytes_trace,fpr,tpr_primary,tpr_scale,locacc,verify_ms_honest,verify_ms_tamper,risk_class,source
AB_projcos4,A/B,A,B,C1-C3,projcos4,256,768,0.020,1.000,0.000,1.000,3.798,3.684,low,measured
BD_scalar16,B/D,B,D,C1-C3,scalar16,64,192,0.245,1.000,0.720,1.000,3.603,3.382,high,measured
BD_projcos4,B/D,B,D,C1-C3,projcos4,256,768,0.075,1.000,0.000,1.000,3.798,3.684,low,measured
```

字段说明：

| 字段 | 含义 |
|---|---|
| `profile_id` | 唯一 ID，建议 `pair_sketch` |
| `pair_id` | stack pair，例如 `A/B` |
| `boundary` | checked boundary set，例如 `C1-C3` |
| `sketch` | verifier mode，例如 `scalar16`, `projcos4`, `projcos16` |
| `bytes_trace` | 一个 challenge trace 需要 reveal 的总字节数 |
| `fpr` | honest heterogeneous false-positive rate |
| `tpr_primary` | primary material tamper true-positive rate |
| `tpr_scale` | scale-like attack TPR；如果不使用，保留但不作为 admission 主指标 |
| `locacc` | first-mismatch localization accuracy |
| `verify_ms_*` | challenge-time verifier latency |
| `risk_class` | low / medium / high / infeasible；由脚本根据 threshold 生成也可以 |

#### 4.3.2 `data/candidate_placements.csv`

每一行是 replay 中可被选中的 candidate placement。

```csv
candidate_id,group_size,provider_set,shard_map,pair_ids,network_latency_s,execution_latency_s,availability_cost,reputation,capacity_ok,backend_mix
cand_001,2,"P1;P2","C1:P1;C2:P2;C3:P2","A/B",1.008,0.870,0.20,0.91,1,heterogeneous
cand_002,2,"P3;P4","C1:P3;C2:P4;C3:P4","B/D",0.972,0.810,0.25,0.84,1,heterogeneous
cand_003,1,"P5","C1:P5;C2:P5;C3:P5","F/F",1.210,1.210,0.10,0.95,1,homogeneous
```

字段说明：

| 字段 | 含义 |
|---|---|
| `candidate_id` | candidate 唯一 ID |
| `group_size` | selected provider 数 |
| `provider_set` | provider IDs |
| `shard_map` | shard 到 provider 的映射 |
| `pair_ids` | candidate 涉及的 boundary signature；多个用 `;` 分隔 |
| `network_latency_s` | network-aware baseline 用的估计 latency |
| `execution_latency_s` | end-to-end 或 replay latency estimate |
| `availability_cost` | 可选；没有则填 0 |
| `reputation` | 可选；没有则填 1 |
| `capacity_ok` | 0/1 |
| `backend_mix` | heterogeneous / homogeneous |

#### 4.3.3 `data/workload.csv`

每一行是一个 replay task。

```csv
task_id,workload,arrival_s,deadline_s,demand,payload_mb,alpha,beta,sketch_budget_bytes,verify_budget_ms,max_group_size,challenge_prob
0001,single,0,5,small,100,0.10,0.90,3072,5.0,4,0.10
0002,queued-8,0,40,small,100,0.10,0.90,3072,5.0,4,0.10
```

### 4.4 Policy 定义

至少跑 5 个 policy。第 6 个可选但强烈推荐。

| Policy | 定义 | 作用 |
|---|---|---|
| `random` | 在 capacity-ok candidates 中随机选 | sanity baseline |
| `cost_only` | 最小 availability/cost 或 execution cost | 资源市场式 baseline |
| `network_aware` | 最小 network/execution latency | 强 latency baseline |
| `risk_weighted` | 在 score 里加入 verification risk，但不硬过滤 | 证明 hard constraint 的价值 |
| `verif_constrained` | 先过滤不满足 \(\alpha,\beta,B,C\) 的 candidate，再按 latency 选 | 主 policy |
| `adaptive_verifier` | 对每个 candidate 选择满足约束的最小 sketch；若无可行 sketch，则 reject | 主 policy 增强版 |
| `homogeneous_only` | 只允许 same-backend 或 homogeneous candidates | 可选；回答为什么不直接避免 heterogeneity |

### 4.5 Feasibility 计算

对每个 candidate 和 task policy，计算：

```text
candidate is feasible iff:
  capacity_ok == 1
  group_size <= max_group_size
  max_fpr(candidate, selected_sketch) <= alpha
  min_tpr(candidate, selected_sketch) >= beta
  bytes_trace(candidate, selected_sketch) <= sketch_budget_bytes
  verify_ms(candidate, selected_sketch) <= verify_budget_ms
```

多 boundary / 多 pair 聚合：

```text
max_fpr = max(fpr over all pair_ids)
min_tpr = min(tpr_primary over all pair_ids)
verify_ms = sum(verify_ms_honest or average of honest/tamper, depending on existing table convention)
bytes_trace = sum(bytes_trace over checked traces if all are revealed)
```

务必在 paper 中说明采用的是 conservative aggregation。

### 4.6 最低成本 alpha sweep

固定：

```text
beta = 0.90
sketch_budget_bytes = 3072
verify_budget_ms = 5.0
challenge_prob = 0.10
workloads = single, queued-8
```

扫：

```text
alpha ∈ {0.05, 0.10, 0.20}
```

输出：

```text
policy × workload × alpha
```

### 4.7 每次 replay 需要记录的输出

生成 `results/placement_runs.csv`：

```csv
run_id,seed,workload,alpha,beta,policy,task_id,candidate_count,feasible_count,selected_candidate,selected_group_size,selected_sketch,admitted,latency_s,goodput_contrib,challenge_ms_task,false_risk,infeasible,low_risk,reason
r001,0,queued-8,0.10,0.90,network_aware,0002,30,15,cand_002,2,scalar16,1,36.310,2.161,0.285,0.054,1,0,selected_low_latency_but_infeasible
r002,0,queued-8,0.10,0.90,verif_constrained,0002,30,15,cand_001,2,projcos4,1,36.310,2.161,0.054,0.010,0,1,selected_feasible_low_risk
```

字段说明：

| 字段 | 计算方式 |
|---|---|
| `candidate_count` | task 可考虑的 candidate 数 |
| `feasible_count` | 满足 verifiability constraints 的 candidate 数 |
| `selected_sketch` | policy 最终选择的 sketch；非 adaptive policy 可固定默认 sketch |
| `admitted` | 是否成功选出 placement |
| `latency_s` | replay 估计 latency 或 measured latency |
| `goodput_contrib` | workload-level goodput 统计所需值；也可在 summary 阶段计算 |
| `challenge_ms_task` | `challenge_prob × verify_ms` 或当前稿子已有定义，保持一致 |
| `false_risk` | `challenge_prob × max_fpr` 或当前稿子已有定义，保持一致 |
| `infeasible` | selected candidate 是否违反 \(\alpha,\beta,B,C\) |
| `low_risk` | selected candidate 是否 low-risk |
| `reason` | 方便 debug 的文字说明 |

### 4.8 Summary 表回填模板

生成 `results/placement_summary.csv`：

```csv
workload,alpha,beta,policy,latency_median_s,latency_p95_s,goodput,challenge_ms_task_mean,false_risk_mean,infeasible_rate,low_risk_share,admission_rate,feasible_candidate_mean
queued-8,0.10,0.90,network_aware,36.310,40.120,2.161,0.285,0.054,0.480,0.520,1.000,15.0
queued-8,0.10,0.90,verif_constrained,36.310,40.130,2.161,0.054,0.010,0.000,1.000,1.000,15.0
queued-8,0.10,0.90,adaptive_verifier,36.310,39.900,2.241,0.054,0.010,0.000,1.000,1.000,15.0
```

论文主表建议列：

| Workload | Policy | Latency s | Goodput | Chal. ms/task | False risk | Infeas. | Low-risk share |
|---|---:|---:|---:|---:|---:|---:|---:|

alpha sweep 表建议列：

| Workload | Alpha | Policy | Goodput | Infeas. | False risk | Admission rate |
|---|---:|---|---:|---:|---:|---:|

### 4.9 图怎么画

#### Figure A1：Placement frontier

**用途**：主图。展示 verifiability-constrained policy 把 frontier 从 high-risk 区域推到 low-risk 区域。

- x 轴：`latency_median_s` 或 `1/goodput`。
- y 轴：`false_risk_mean` 或 `infeasible_rate`。
- 点：policy。
- 标注：policy name。
- 如果图太挤，分成两张：`Latency vs False Risk` 和 `Goodput vs Infeasible Rate`。

Python 模板：

```python
import pandas as pd
import matplotlib.pyplot as plt

summary = pd.read_csv("results/placement_summary.csv")
plot_df = summary[(summary["workload"] == "queued-8") & (summary["alpha"] == 0.10)]

fig, ax = plt.subplots(figsize=(5.2, 3.2))
ax.scatter(plot_df["latency_median_s"], plot_df["false_risk_mean"])

for _, row in plot_df.iterrows():
    ax.annotate(row["policy"], (row["latency_median_s"], row["false_risk_mean"]),
                xytext=(4, 4), textcoords="offset points", fontsize=8)

ax.set_xlabel("Median latency (s)")
ax.set_ylabel("Expected false-dispute risk")
ax.set_title("Placement frontier under measured verifier profiles")
ax.grid(True, linewidth=0.3)
fig.tight_layout()
fig.savefig("figures/fig_placement_frontier.pdf")
```

建议 caption：

```text
Placement frontier under measured verifier profiles for the queued-8 workload. Network-aware placement preserves latency but selects high-risk or infeasible verifier signatures, while verifiability-constrained placement filters those signatures before disclosure and reduces expected false-dispute risk without reducing queued-workload goodput.
```

#### Figure A2：Risk-class composition

**用途**：解释机制。展示每个 policy 选中的 placements 中 low-risk / high-risk / infeasible 的比例。

Python 模板：

```python
import pandas as pd
import matplotlib.pyplot as plt

runs = pd.read_csv("results/placement_runs.csv")
df = runs[(runs["workload"] == "queued-8") & (runs["alpha"] == 0.10)]

agg = df.groupby("policy").agg(
    low_risk_share=("low_risk", "mean"),
    infeasible_rate=("infeasible", "mean")
).reset_index()
agg["other_risk_share"] = 1.0 - agg["low_risk_share"] - agg["infeasible_rate"]
agg = agg.sort_values("low_risk_share")

fig, ax = plt.subplots(figsize=(5.2, 3.2))
left = [0] * len(agg)
ax.barh(agg["policy"], agg["low_risk_share"], label="low-risk")
left = agg["low_risk_share"]
ax.barh(agg["policy"], agg["other_risk_share"], left=left, label="other risk")
left = left + agg["other_risk_share"]
ax.barh(agg["policy"], agg["infeasible_rate"], left=left, label="infeasible")

ax.set_xlabel("Share of selected placements")
ax.legend(fontsize=8)
ax.grid(True, axis="x", linewidth=0.3)
fig.tight_layout()
fig.savefig("figures/fig_risk_class_composition.pdf")
```

建议 caption：

```text
Risk-class composition of selected placements. Verifiability-constrained and adaptive-verifier policies route selected placements through profiles that satisfy the task's false-dispute and detection targets; latency-oriented baselines continue to use a substantial infeasible slice.
```

#### Figure A3：Alpha sensitivity

**用途**：证明不是 cherry-picked \(\alpha=0.10\)。

- x 轴：alpha。
- y 轴：infeasible rate 或 false risk。
- lines：policy。

Python 模板：

```python
import pandas as pd
import matplotlib.pyplot as plt

summary = pd.read_csv("results/placement_summary.csv")
df = summary[summary["workload"] == "queued-8"]

fig, ax = plt.subplots(figsize=(5.2, 3.2))
for policy, g in df.groupby("policy"):
    g = g.sort_values("alpha")
    ax.plot(g["alpha"], g["infeasible_rate"], marker="o", label=policy)

ax.set_xlabel("False-dispute target alpha")
ax.set_ylabel("Infeasible usage rate")
ax.set_title("Sensitivity to verifiability target")
ax.legend(fontsize=7)
ax.grid(True, linewidth=0.3)
fig.tight_layout()
fig.savefig("figures/fig_alpha_sensitivity_infeasible.pdf")
```

建议 caption：

```text
Sensitivity to the false-dispute target. Tightening alpha reduces the feasible candidate set; verifiability-constrained placement preserves the admission invariant by rejecting or upgrading candidates, while latency-oriented policies continue to select candidates that violate the target.
```

### 4.10 结果回填到论文的位置

| 论文位置 | 回填内容 |
|---|---|
| Evaluation opening | 把 RQ1 改成 verifiability-constrained placement |
| New subsection E1 | `Closed-loop Verifiability-Constrained Placement` |
| Main table | `placement_summary.csv` 的 alpha=0.10 主结果 |
| Main figure | `fig_placement_frontier.pdf` 或 `fig_risk_class_composition.pdf` |
| Sensitivity paragraph | alpha sweep 的 3–5 句话 |
| Abstract | 只填最强主结果，不要堆所有 policy |
| Conclusion | 强调 measured verifier profile becomes placement-visible state |

### 4.11 写作模板：实验 A 结果段

填入真实数字后使用：

```text
Closed-loop placement changes which heterogeneous executions are admitted before task disclosure. Under the queued-8 workload and alpha=..., beta=..., the network-aware policy achieves goodput ... but selects infeasible verifier signatures in ...% of placements. Verifiability-constrained placement removes these infeasible placements, reducing infeasible usage to ... and expected challenge workload from ... to ... ms/task. The goodput remains ... compared with ... for network-aware placement. Adaptive-verifier placement further preserves candidate availability by upgrading from cheap sketches to stronger measured profiles when necessary. These results show that verifier behavior is useful before execution: it moves the placement frontier by converting heterogeneous verifiability into an admission constraint rather than an after-the-fact checker.
```

### 4.12 Sanity checks

学生提交实验 A 前必须确认：

- [ ] 每个 policy 使用同一个 workload、candidate set、profile matrix。
- [ ] `verif_constrained` 没有选择任何违反 \(\alpha,\beta,B,C\) 的 candidate。
- [ ] `adaptive_verifier` 的 sketch upgrade 逻辑有日志。
- [ ] alpha sweep 不改变 workload，只改变 target。
- [ ] `false_risk` 和 `challenge_ms_task` 的定义和论文表格一致。
- [ ] 所有随机策略至少 5 个 seed；如果只有 1 个 seed，必须标注为 preliminary。
- [ ] 图里没有把 lower-is-better 和 higher-is-better 混在一个轴上。

---

## 5. 实验 B：Selective Delivery Group-Size Sweep

### 5.1 实验目标

证明：**placement 不只是选择谁执行，也决定谁收到 task-access material；当 group size 增大时，PPD 把 repeated payload-sized transfers 变成 one ciphertext publication + small per-provider access packages。**

这支撑论文中的 data boundary claim。

### 5.2 核心假设

H1. RPD requester egress 随 group size 近似 \(O(kS)\)。  
H2. PPD requester egress 近似 \(O(S + k\epsilon)\)，其中 \(S\) 是 payload size，\(\epsilon\) 是 locator/key package size。  
H3. 在 fixed payload 下，group size 越大，PPD 相对 RPD 的 latency/egress 优势越明显。  
H4. PPD 的收益不是“避免加密”，因为两个路径都传 encrypted payload；收益来自 post-placement targeted access release。

### 5.3 最低成本实验矩阵

优先做 group-size sweep：

```text
payload_size = 100MB
k ∈ {1, 2, 4, 8}
network ∈ {LAN, WAN 或 emulated-WAN}
mode ∈ {RPD, PPD}
runs_per_cell = 30
```

如果还有时间，再加 payload-size sweep：

```text
k = 4 或 8
payload_size ∈ {1MB, 10MB, 100MB, 500MB}
network ∈ {LAN, WAN}
mode ∈ {RPD, PPD}
runs_per_cell = 30
```

### 5.4 RPD 和 PPD 的公平定义

#### RPD baseline

```text
For each selected provider P_i in G:
  requester sends a full encrypted payload C_j to P_i.
```

要求：

- 使用 encrypted payload，不用 plaintext。
- 允许并行发送，但并发度要记录。
- 统计 requester egress 为所有 full-payload transfers 的总和。
- 如果使用 HTTP/TCP，记录连接复用和并发设置。

#### PPD path

```text
Requester encrypts payload once.
Requester publishes C_j once to off-chain store.
For each selected provider P_i in G:
  requester sends encrypted access package Enc_pk_i(locator, key).
Provider fetches C_j using locator and decrypts locally.
```

要求：

- 每次 run 使用 fresh payload 或 unique content hash，避免缓存污染。
- provider fetch latency 计入 all-providers-ready latency。
- 统计 requester egress 时，区分 payload publication bytes 和 per-provider access package bytes。

### 5.5 计时点定义

每次 run 记录以下 timestamp：

| Timestamp | 含义 |
|---|---|
| `t0_start` | placement committed, delivery starts |
| `t1_encrypt_done` | payload encryption done |
| `t2_publish_done` | PPD ciphertext publication done；RPD 可填空 |
| `t3_access_sent` | all access packages sent；RPD 为 all payload sends initiated/done，根据实现固定 |
| `t4_first_ready` | first provider ready to decrypt/execute |
| `t5_all_ready` | all selected providers ready to execute |

关键 metric：

```text
requester_critical_path_ms = t5_all_ready - t0_start
all_providers_ready_ms = t5_all_ready - t0_start
provider_fetch_ms = provider_fetch_done - provider_fetch_start
```

如果加密开销不想纳入，可以同时报告：

```text
delivery_only_ms = t5_all_ready - t1_encrypt_done
```

但必须说明 paper 主结果使用哪个。

### 5.6 数据记录模板

生成 `results/delivery_runs.csv`：

```csv
run_id,network,mode,payload_mb,group_size,concurrency,provider_id,replicate_id,t0_start_ms,t1_encrypt_done_ms,t2_publish_done_ms,t3_access_sent_ms,t4_first_ready_ms,t5_all_ready_ms,requester_egress_mb,store_egress_mb,provider_fetch_ms,access_pkg_bytes,success,notes
lan_ppd_100_4_001,LAN,PPD,100,4,4,ALL,1,0,120,980,1010,1040,1300,101.2,400.0,260,2048,1,fresh_cid
lan_rpd_100_4_001,LAN,RPD,100,4,4,ALL,1,0,120,,1450,900,1450,400.0,0.0,,0,1,parallel_send
```

生成 summary：`results/delivery_summary.csv`

```csv
network,mode,payload_mb,group_size,n,median_ms,p95_ms,mean_ms,requester_egress_mb_mean,requester_egress_mb_p95,access_pkg_bytes_mean,reduction_vs_rpd_median,reduction_vs_rpd_p95,egress_reduction_vs_rpd
LAN,PPD,100,4,30,1300,1500,1320,101.2,102.0,2048,0.315,0.280,0.747
LAN,RPD,100,4,30,1898,2150,1920,400.0,400.0,0,0,0,0
```

Reduction 计算：

```text
reduction_vs_rpd_median = (median_RPD - median_PPD) / median_RPD
reduction_vs_rpd_p95 = (p95_RPD - p95_PPD) / p95_RPD
egress_reduction_vs_rpd = (egress_RPD - egress_PPD) / egress_RPD
```

### 5.7 图怎么画

#### Figure B1：Latency vs group size

- x 轴：group size \(k\)。
- y 轴：median all-providers-ready latency。
- lines：RPD, PPD。
- panels 或 separate plots：LAN, WAN。
- error bars：p95 或 IQR。

Python 模板：

```python
import pandas as pd
import matplotlib.pyplot as plt

summary = pd.read_csv("results/delivery_summary.csv")

for network in summary["network"].unique():
    df = summary[(summary["network"] == network) & (summary["payload_mb"] == 100)]
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for mode, g in df.groupby("mode"):
        g = g.sort_values("group_size")
        ax.plot(g["group_size"], g["median_ms"], marker="o", label=mode)
        ax.fill_between(g["group_size"], g["median_ms"], g["p95_ms"], alpha=0.15)
    ax.set_xlabel("Selected group size k")
    ax.set_ylabel("All-providers-ready latency (ms)")
    ax.set_title(f"Selective delivery latency ({network}, 100MB)")
    ax.legend(fontsize=8)
    ax.grid(True, linewidth=0.3)
    fig.tight_layout()
    fig.savefig(f"figures/fig_delivery_latency_{network.lower()}.pdf")
```

Caption 模板：

```text
Selective delivery latency as placement width grows. RPD sends a full encrypted payload to each selected provider, while PPD publishes one ciphertext and releases small per-provider access packages after placement commitment. As k increases, PPD keeps requester-side delivery closer to one-payload publication, whereas RPD scales with replicated payload transfers.
```

#### Figure B2：Requester egress vs group size

- x 轴：group size。
- y 轴：requester egress MB。
- lines：RPD, PPD。
- 这张图最容易让 reviewer 理解 \(O(kS)\) vs \(O(S+k\epsilon)\)。

Python 模板：

```python
import pandas as pd
import matplotlib.pyplot as plt

summary = pd.read_csv("results/delivery_summary.csv")
df = summary[(summary["network"] == "LAN") & (summary["payload_mb"] == 100)]

fig, ax = plt.subplots(figsize=(5.2, 3.2))
for mode, g in df.groupby("mode"):
    g = g.sort_values("group_size")
    ax.plot(g["group_size"], g["requester_egress_mb_mean"], marker="o", label=mode)

ax.set_xlabel("Selected group size k")
ax.set_ylabel("Requester egress (MB)")
ax.set_title("Requester egress under placement-defined disclosure")
ax.legend(fontsize=8)
ax.grid(True, linewidth=0.3)
fig.tight_layout()
fig.savefig("figures/fig_delivery_egress_group_size.pdf")
```

Caption 模板：

```text
Requester egress under placement-defined disclosure. RPD incurs approximately k payload-sized transfers, while PPD incurs one ciphertext publication plus small per-provider access packages. The result shows why the committed placement record is also the data boundary: only selected providers receive decryptable task access.
```

### 5.8 结果回填到论文的位置

| 论文位置 | 回填内容 |
|---|---|
| System / selective delivery | 加模型：RPD \(kS\)，PPD \(S+k\epsilon\) |
| Evaluation E3 | 加 group-size sweep 表和 latency/egress 图 |
| Abstract | 用最强但不夸张的结果，例如 “for k=8, PPD reduces median delivery latency by X% and requester egress by Y%” |
| Discussion | 强调 selective delivery 是 placement boundary，不只是 performance trick |

### 5.9 写作模板：实验 B 结果段

```text
Selective delivery scales with placement width because it decouples payload publication from per-provider access release. With a 100MB payload on [LAN/WAN], RPD's requester egress grows from ... MB at k=1 to ... MB at k=8, while PPD grows from ... MB to ... MB because only locator-and-key packages are replicated. The median all-providers-ready latency decreases by ...% at k=4 and ...% at k=8 relative to RPD. These results support the data-boundary role of placement: once the group is committed, VeriEdge releases decryptable task access only to selected providers while avoiding repeated payload-sized requester transfers.
```

### 5.10 Sanity checks

学生提交实验 B 前必须确认：

- [ ] RPD 和 PPD 使用相同 payload size、network condition、provider count。
- [ ] 每次 run 使用 fresh payload 或 unique object ID，避免缓存导致 PPD 被高估。
- [ ] WAN/emulated WAN 的 bandwidth/RTT/loss 参数记录在 metadata。
- [ ] RPD baseline 是否并行发送必须写清楚。
- [ ] 报告 median 和 p95，不只报 mean。
- [ ] requester egress 和 store/provider egress 分开记录。
- [ ] 图和表使用同一批 summary 数据。

---

# Part III. 实验结果交付模板

## 6. 学生最终交付目录结构

每个实验负责人提交一个目录：

```text
veriedge_revision_results/
  README.md
  metadata/
    environment.md
    network_config.md
    git_commit.txt
  data/
    profile_matrix.csv
    candidate_placements.csv
    workload.csv
  results/
    placement_runs.csv
    placement_summary.csv
    delivery_runs.csv
    delivery_summary.csv
  figures/
    fig_placement_frontier.pdf
    fig_risk_class_composition.pdf
    fig_alpha_sensitivity_infeasible.pdf
    fig_delivery_latency_lan.pdf
    fig_delivery_latency_wan.pdf
    fig_delivery_egress_group_size.pdf
  paper_snippets/
    placement_eval_subsection.tex
    delivery_eval_subsection.tex
    abstract_numbers.txt
    figure_captions.txt
```

## 7. `README.md` 模板

```markdown
# VeriEdge revision experiment results

## Summary
- Experiment A: Closed-loop verifiability-constrained placement
- Experiment B: Selective delivery group-size sweep

## Environment
- Git commit:
- Date:
- Machines:
- Network setup:
- Payload generation:
- Random seeds:

## Main results

### Placement
- Best baseline:
- Main constrained policy:
- Infeasible usage reduction:
- Challenge workload reduction:
- Goodput change:
- Alpha sensitivity summary:

### Delivery
- Payload size:
- Group sizes:
- LAN median reduction:
- WAN median reduction:
- Requester egress reduction at k=8:

## Known issues
- Any failed runs:
- Any outliers removed:
- Cache/network caveats:
- Deviations from protocol:
```

## 8. Paper snippet 模板

### 8.1 `placement_eval_subsection.tex`

```latex
\subsection{Closed-Loop Verifiability-Constrained Placement}
\label{subsec:eval-vc-placement}

We replay placement policies using the measured verifier profile from Section~\ref{...}. Each candidate placement is associated with a device/backend/sketch signature. A placement is admissible only if its conservative profile satisfies the task-level false-dispute target $\alpha$, detection target $\beta$, sketch budget, and challenge-cost budget before task disclosure.

Table~\ref{tab:vc-placement} reports the main replay results. [FILL IN 2--3 SENTENCES WITH NUMBERS.]

\begin{table}[t]
\centering
\caption{Closed-loop placement replay using measured verifier profiles.}
\label{tab:vc-placement}
\scriptsize
\begin{tabular}{llrrrrrr}
\toprule
Workload & Policy & Latency s & Goodput & Chal. ms/task & False risk & Infeas. & Low-risk \\
\midrule
% FILL FROM placement_summary.csv
\bottomrule
\end{tabular}
\end{table}

Figure~\ref{fig:placement-frontier} shows the resulting frontier. [FILL IN INTERPRETATION.]
```

### 8.2 `delivery_eval_subsection.tex`

```latex
\subsection{Selective Delivery Under Placement Width}
\label{subsec:eval-selective-delivery}

Placement also defines the data boundary: only selected providers receive decryptable task-access material. We compare replicated payload delivery (RPD), which sends a full encrypted payload to each selected provider, against privacy-preserving delivery (PPD), which publishes one ciphertext and sends small locator-and-key packages after placement commitment.

For a payload of size $S$ and selected group size $k$, RPD incurs requester egress proportional to $kS$, whereas PPD incurs one ciphertext publication plus $k$ small access packages. Figure~\ref{fig:delivery-latency} and Figure~\ref{fig:delivery-egress} show the measured effect. [FILL IN NUMBERS.]
```

### 8.3 `abstract_numbers.txt`

```text
Placement result sentence:
Under queued-8 replay, verifiability-constrained placement reduces infeasible usage from ___ to ___ and expected challenge workload from ___ to ___ ms/task while preserving goodput at ___ versus ___ for network-aware placement.

Selective delivery result sentence:
For 100MB payloads and k=___ selected providers, PPD reduces median all-providers-ready latency by ___% on LAN and ___% on WAN, and reduces requester egress by ___% relative to RPD.
```

## 9. Figure checklist

每张图提交前检查：

- [ ] 文件是 `.pdf`，适合 LaTeX。
- [ ] 字体大小在双栏图中可读。
- [ ] 轴标签包含单位。
- [ ] caption 能独立说明 baseline、ours、metric、结论。
- [ ] 图中 policy 名称与正文完全一致。
- [ ] 图使用的数据能从 `results/*.csv` 重现。
- [ ] 没有使用 preliminary / temp / placeholder 字样。

---

# Part IV. 最低成本执行计划

## 10. 三天冲刺版

### Day 1：Placement replay

负责人：placement 学生  
目标：跑完 policy ablation + alpha sweep。

交付：

- `profile_matrix.csv`
- `candidate_placements.csv`
- `workload.csv`
- `placement_runs.csv`
- `placement_summary.csv`
- `fig_placement_frontier.pdf`
- `fig_alpha_sensitivity_infeasible.pdf`

通过标准：

- verif_constrained 在所有 alpha 下 infeasible rate 为 0 或接近 0。
- 至少有一张图清晰显示 network-aware 与 constrained 的 frontier 差异。
- 如果 goodput 有下降，必须解释 tradeoff；如果没有下降，这是 abstract 级主结果。

### Day 2：Selective delivery sweep

负责人：delivery 学生  
目标：固定 100MB，跑 k=1/2/4/8，LAN+WAN，RPD vs PPD。

交付：

- `delivery_runs.csv`
- `delivery_summary.csv`
- `fig_delivery_latency_lan.pdf`
- `fig_delivery_latency_wan.pdf`
- `fig_delivery_egress_group_size.pdf`

通过标准：

- 每个 cell 至少 30 次 run，或明确说明 sample size。
- median/p95 和 requester egress 都有。
- WAN 配置记录完整。

### Day 3：回填论文

负责人：主笔  
目标：把新题目、placement-first narrative 和两个实验整合到稿子。

交付：

- 新 Abstract。
- 新 Contributions。
- 新 Placement formulation。
- 新 Evaluation order。
- 两个新 subsection。
- 删除过强 verifier claim 和临时占位语言。

---

# Part V. 最容易犯的错误

## 11. Narrative 错误

| 错误写法 | 为什么危险 | 正确写法 |
|---|---|---|
| “TSTC verifies LLM inference” | 会被安全 reviewer 按 proof 标准打 | “TSTC provides policy-scoped challenge-time arbitration evidence” |
| “Placement is verification-aware” | 与新题目 `constrained` 不够匹配 | “Placement admits only candidates satisfying measured verifiability targets” |
| “PPD is privacy-preserving” 不解释范围 | 容易被误解为 selected providers 也看不到 payload | “PPD protects against unselected providers and keeps orchestrator off the access-tuple path” |
| “Blockchain ensures trust” | 容易引起反感 | “Ledger stores compact commitments and settlement state; heavy work remains off-chain” |
| “Detects all tampers” | 与 scale / adaptive blind spot 冲突 | “Detects evaluated non-adaptive material tamper families under this sketch policy” |

## 12. 实验错误

| 错误 | 后果 | 避免方式 |
|---|---|---|
| 只报 100MB 单点 | reviewer 认为 selective delivery 证据薄 | 至少做 group-size sweep |
| 只给 placement table，不给 constraint 定义 | reviewer 认为不是 verifiability-constrained | 明确 \(\alpha,\beta,B,C\) feasibility |
| alpha 只用 0.10 | reviewer 怀疑 cherry-pick | 扫 0.05/0.10/0.20 |
| RPD baseline 串行但 PPD 并行 | baseline 不公平 | 记录并发度，并尽量给 RPD 合理并行 |
| PPD 使用缓存 | PPD 被高估 | fresh payload / unique CID / cache policy 说明 |
| 图和表来自不同数据 | rebuttal 灾难 | 所有图表从同一 summary CSV 生成 |

---

# Part VI. 最终投稿前检查清单

## 13. 内容闭环

- [ ] Title、Abstract、Intro、Contribution 都使用 `verifiability-constrained placement` 主线。
- [ ] System model 明确 placement 是 data/execution/evidence/settlement boundary。
- [ ] Placement section 有 hard feasibility constraints。
- [ ] Evaluation 第一项是 closed-loop placement，而不是 verifier sketch。
- [ ] Selective delivery sweep 支撑 data-boundary claim。
- [ ] Verifier 实验被表述为 profile construction，而不是论文唯一中心。
- [ ] Limitations 是 scoped claim，不是“还没做完”的占位。

## 14. 数据一致性

- [ ] Abstract 数字与 Evaluation 表格完全一致。
- [ ] Intro 中的 FPR/TPR 数字与 verifier tables 一致。
- [ ] `3KB sketch`、`24% FPR` 等旧表述若不准确，全部删除或重写。
- [ ] placement table 中 `goodput`、`infeasible`、`false risk` 定义在 text 中解释。
- [ ] delivery reduction 的 denominator 是 RPD，并在 caption/text 中说明。

## 15. LaTeX / submission hygiene

- [ ] 没有 `\color{blue}`。
- [ ] 没有 placeholder figure slot。
- [ ] 所有 `\includegraphics` 指向可编译 `.pdf` / `.png`。
- [ ] 所有 labels/ref 正常。
- [ ] anonymous submission 中没有泄露路径、机器名、个人名。
- [ ] conference metadata 已核对。
- [ ] Related Work 不再像临时短段落，至少有清晰差异表或分类段。

---

# 16. 最终应形成的论文形象

完成上述修订后，论文应该被 reviewer 读成：

> This is a systems paper about making heterogeneous edge LLM placement accountable. The novelty is not merely a checkpoint sketch, but a closed-loop design where measured verifier profiles constrain placement before task disclosure, and the committed placement record governs delivery, challenge evidence, settlement, and future placement.

不要让论文被读成：

> This is a verifier paper with a blockchain/orchestration wrapper.

本轮最重要的执行原则仍然是：

> **补系统闭环，不补 verifier 炫技。**
