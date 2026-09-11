# VeriEdge Paper1 脱离 EXO 的实验执行手册

## 1. 为什么需要这份手册

`eurosys_draft_v13.pdf` 和 `实验手册.pdf` 已经很明确地说明，当前论文还缺四组关键实验：

- `E1`：真实异构 honest-honest paired capture
- `E2`：TSTC ablation
- `E4`：verifier operational overhead
- `E5`：verification-aware placement comparison

虽然当前草稿仍然把原型描述为“implemented on top of EXO”，但从现有仓库状态来看，`EXO` 已经不适合作为这四组缺失实验的主路径，尤其是在需要 Linux GPU 参与、以及需要稳定采集 checkpoint 的情况下。

因此，这份手册采用如下总原则：

- `E1/E2/E4` 统一走现有的 `strict T3/T5` Torch 异构分片路径，不依赖 EXO。
- `E5` 视为基于测量 traces 的 orchestration 策略对比，不再把 EXO 当成关键阻塞依赖。

一句话概括：

- 论文正文仍然可以保留 EXO 作为原始 prototype substrate；
- 但当前缺失的证据链，应该建立在仓库已经具备的 capture-and-verifier 工具链之上。

## 2. 全局决策

### 2.1 主实验路线

统一采用仓库现有的异构执行路径：

- `artifacts/thc/scripts/t3_hetero_cli.py`
- `artifacts/thc/T3_hetero_runbook.md`
- `artifacts/thc/src/run.py`
- `artifacts/thc/src/overhead_report.py`

这条路径已经支持：

- 固定 3-shard 执行
- 显式采集 `C1/C2/C3` checkpoint
- Mac 上的 `torch+mps`
- Linux 上的 `torch+cuda`
- 基于 capture bundle 的可复现 `THC/TSTC` replay

### 2.2 EXO 还可以做什么

从现在开始，EXO 是次要角色，不再是主路径。

允许保留的作用：

- 保持论文 prototype 叙事的一致性
- 继续引用已有的 deployment-path reference numbers
- 在 `E5` 中作为可选的 Mac-only control-plane side experiment

不允许再作为以下实验的阻塞依赖：

- `E1` 真实 paired capture
- `E2` ablation
- `E4` overhead
- 包含 Linux 的 `E5`

## 3. 共享实验基线

### 3.1 硬件基线

建议采用与当前仓库一致的默认配置：

- `jlmini_3`：Mac mini M4，`torch+mps`，first shard，`C1`
- `linux124`：Linux + RTX3090，`torch+cuda`，middle shard，`C2`
- `jlmini_2`：Mac mini M4，`torch+mps`，last shard，`C3`

默认 cluster 文件：

- `artifacts/thc/config/hetero_qwen_cluster.json`

### 3.2 统一模型与 shard plan

除非某次运行明确是在研究 placement variation，否则四组实验都默认使用同一个固定执行计划：

- model family：`Qwen/Qwen3-0.6B`
- shard 1：layers `0-7`，checkpoint `C1`
- shard 2：layers `8-15`，checkpoint `C2`
- shard 3：layers `16-23`，checkpoint `C3`

如果 shard 边界发生变化，以下内容必须同步更新：

- cluster JSON
- notes
- pairwise comparison table 标签
- overhead table 标签
- 论文正文

### 3.3 split 纪律

整个项目必须严格区分 calibration 和 evaluation：

- `calibration` 只用于估计 `delta_map`
- `evaluation` 只用于最终报告 verifier 结果

禁止复用同一批 prompts 或同一批 capture roots 来同时承担这两个角色。

### 3.4 统一输出布局

建议目录布局如下：

- `paper1_veriedge/E1/logs/`
- `paper1_veriedge/E1/tables/`
- `paper1_veriedge/E1/notes/`
- `paper1_veriedge/E2/logs/`
- `paper1_veriedge/E4/logs/`
- `paper1_veriedge/E5/logs/`
- 原始 capture roots 放在 git 外部，例如 `workspace/captures/E1/` 或 `/tmp/thc_t3/...`

不要把大型 `.npz` capture bundle 直接提交到 paper workspace。

## 4. 四组缺失实验的脱离 EXO 路线

## 4.1 E1：真实异构 honest-honest paired capture

### 目标

证明 `TSTC` 在真实异构诚实执行上也能降低误报，而不是只在 synthetic heterogeneity 上有效。

### 脱离 EXO 的路线

不使用 EXO distributed runtime。

直接使用：

- `artifacts/thc/scripts/run_t3_hetero_server.sh`
- `artifacts/thc/scripts/run_t3_hetero_capture.sh`
- `artifacts/thc/scripts/run_t3_delta_calibration.sh`
- `artifacts/thc/scripts/run_t5_from_capture.sh`

核心思路：

1. 用 HTTP-based Torch shard chain 跑真实 shard execution
2. 在所有 prompts 上采集 `C1/C2/C3`
3. 用 calibration roots 标定真实 `delta_map`
4. 在 held-out roots 上跑 evaluation
5. 对 matched honest traces 同时做 `THC` 和 `TSTC` 的 pairwise 比较

### 输入

- 真实 calibration capture roots
- 真实 evaluation capture roots
- 一个固定 shard plan
- 一个固定 prompt split 文件

### 输出

- `exp_e1_<date>_<owner>_summary.csv`
- `exp_e1_<date>_<owner>_pairwise_details.csv`
- `notes/e1_run_notes.md`

### 关键上报字段

- device/backend pair
- prompt id
- checkpoint
- THC 是否检测为 mismatch
- TSTC 是否检测为 mismatch
- mismatch stage/checkpoint
- honest-honest 条件下的 localization：`N/A`

## 4.2 E2：TSTC ablation

### 目标

说明 sampling 和 tolerance 是可解释的 operating-point 设计，而不是拍脑袋调参。

### 脱离 EXO 的路线

直接复用 `E1` 结果。

这一组实验不需要 EXO runtime，本质上是离线 verifier 实验。

推荐输入来源：

- 来自 `E1` 的真实 evaluation capture roots
- 来自 `T3` 的真实 `delta_map.json`
- 使用 `run.py` 生成的 synthetic tamper traces
- 使用 `artifacts/TSTC/run_noise_sweep.py` 做 controlled perturbation sweep

### 最小 sweep 集合

- sample size：`4, 8, 16, 32, 64`
- tolerance scale：`0.5x, 1x, 1.5x, 2x`
- checkpoint-specific tolerance 与 global tolerance 的对比

### 输出

- `exp_e2_<date>_<owner>_samplesweep.csv`
- `exp_e2_<date>_<owner>_tolerancesweep.csv`
- `exp_e2_<date>_<owner>_runtime.csv`
- `notes/e2_ablation_notes.md`

## 4.3 E4：verifier operational overhead

### 目标

把 verifier 从“能检测”推进到“系统上可讨论、可部署”。

### 脱离 EXO 的路线

直接复用 `E1` 的真实 capture roots。

运行：

- `artifacts/thc/src/overhead_report.py`

这个脚本已经能从 capture bundle 和 replay trace 中直接统计结构化的 size、runtime 和 storage rows。

### 最低 trace 类型

- honest trace
- challenged honest trace
- tamper trace 或 failed challenge trace

### 输出

- `exp_e4_<date>_<owner>_size_breakdown.csv`
- `exp_e4_<date>_<owner>_latency_breakdown.csv`
- `exp_e4_<date>_<owner>_storage_breakdown.csv`
- `exp_e4_<date>_<owner>_summary.csv`

## 4.4 E5：verification-aware placement comparison

### 目标

证明 VeriEdge 是 orchestration 系统稿，而不只是 verifier 论文。

### 脱离 EXO 的路线

把 `E5` 视为基于 measured traces 的 policy comparison，而不是继续依赖 live EXO scheduling。

推荐路线是：

1. 用 Section 6.1 已有 deployment-path observations 作为 base cost signals
2. 从 `E1` 引入 heterogeneity-risk signals
3. 从 `E4` 引入 verifier workload 与 challenge cost
4. 基于这些输入做 trace-driven policy replay 或 simulator

EXO 可以保留为：

- 一个可选的 Mac-only side experiment
- 一个已有 deployment reference number 的来源

但 `E5` 的主结论不应再依赖 EXO 在所有平台上都稳定可用。

### 最低 policy 集合

- `random`
- `cost_only`
- `reputation_aware`
- `network_aware`
- `verification_aware`

### 最低指标

- task latency
- success rate
- challenge rate
- verifier workload
- goodput

### 输出

- `exp_e5_<date>_<owner>_policy_compare.csv`
- `exp_e5_<date>_<owner>_policy_config.json`
- `notes/e5_policy_notes.md`

## 5. E1 的详细执行方法

这一节是整份手册里最重要的部分。

## 5.1 E1 的 claim 和 scope

`E1` 不是要证明所有输出在语义上完全一致。

它只需要支撑论文里关于 verification 的核心主张：

- 在 matched honest executions、且设备和后端真实异构的条件下，
- `THC` 太脆弱，
- `TSTC` 能显著降低误报。

因此，`E1` 应该被组织成一组 checkpoint-trace comparison study，而不是 end-to-end product benchmark。

## 5.2 E1 必须形成的证据链

`E1` 最终要形成下面这条完整证据链：

1. 真实异构 shard execution 能在不依赖 EXO 的情况下稳定跑通
2. 同一批 prompts 能在多组真实 backend/device 组合下被重复执行
3. 产出的 checkpoint traces 可以按 prompt-by-prompt、checkpoint-by-checkpoint 对齐
4. `THC` 和 `TSTC` 都是在同一批 paired traces 上比较
5. 最终结果表能报告每组真实 pair 的 `THC FPR` 与 `TSTC FPR`

如果这五个环节缺任意一个，就不能算完整的 `E1`。

## 5.3 E1 推荐的 pair 设计

至少要报告三组真实 pair。

推荐沿用草稿当前表格里的几类标签：

- `M4/Metal-int8 vs M4/BF16`
- `M4/Metal-int8 vs RTX3090/BF16`
- `M4/BF16 vs RTX3090/FP32`

实践规则：

- shard plan 必须固定
- 只改变 backend/device realization
- prompt IDs、split、运行顺序必须保持对齐

如果实际机器上的 BF16 或 FP32 支持与预期不同，必须在 notes 里写清楚真实 backend，并且在表格里使用真实标签，而不是沿用不准确命名。

## 5.4 E1 Phase A：准备环境

在三台机器上都要完成：

1. 同步同一份仓库版本
2. 保持相同的相对目录结构
3. 确认 Python 环境
4. 确认模型已下载
5. 确认 shard servers 之间网络互通

使用现有环境检查脚本：

```bash
LOCAL_NODE=jlmini_2 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/check_t3_hetero_env.sh
```

分别对以下三台机器执行：

- `LOCAL_NODE=jlmini_2`
- `LOCAL_NODE=jlmini_3`
- `LOCAL_NODE=linux124`

通过标准：

- 所有节点 import checks 通过
- Mac 节点能正确暴露 `mps`
- Linux 节点能正确暴露 `cuda`

## 5.5 E1 Phase B：启动真实 shard chain

三台机器分别启动一个 shard server：

```bash
LOCAL_NODE=jlmini_2 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/run_t3_hetero_server.sh
```

```bash
LOCAL_NODE=jlmini_3 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/run_t3_hetero_server.sh
```

```bash
LOCAL_NODE=linux124 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/run_t3_hetero_server.sh
```

在 capture 完成前，不要关闭这三个终端。

同时在 notes 中记录：

- node name
- device
- dtype
- quantization
- host:port

## 5.6 E1 Phase C：生成 calibration roots

在协调机上执行：

```bash
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
OUTPUT_DIR=/tmp/thc_t3/e1_calib_run_a \
SPLIT=calibration \
LIMIT_PROMPTS=0 \
bash artifacts/thc/scripts/run_t3_hetero_capture.sh
```

至少重复三次：

- `/tmp/thc_t3/e1_calib_run_a`
- `/tmp/thc_t3/e1_calib_run_b`
- `/tmp/thc_t3/e1_calib_run_c`

每个 root 都应包含：

- `captures/<prompt_id>.npz`
- `checkpoint_metadata.jsonl`
- `capture_summary.json`

## 5.7 E1 Phase D：标定真实 delta map

只使用 calibration roots：

```bash
bash artifacts/thc/scripts/run_t3_delta_calibration.sh \
  /tmp/thc_t3/e1_delta_main \
  /tmp/thc_t3/e1_calib_run_a \
  /tmp/thc_t3/e1_calib_run_b \
  /tmp/thc_t3/e1_calib_run_c
```

核心输出：

- `/tmp/thc_t3/e1_delta_main/delta_map.json`

最终 `E1/E2/E4` 只允许使用这一份 delta 来源。

## 5.8 E1 Phase E：生成 evaluation roots

接下来切换到 held-out prompts。

对于每一组你想比较的真实 backend/device variant，分别生成一个或多个 evaluation capture roots：

```bash
CLUSTER_FILE=<variant_cluster_file.json> \
OUTPUT_DIR=/tmp/thc_t3/e1_eval_<variant_name>_run_a \
SPLIT=evaluation \
LIMIT_PROMPTS=0 \
bash artifacts/thc/scripts/run_t3_hetero_capture.sh
```

这里的关键约束是：

- 各 variant 必须使用相同 prompt IDs
- 各 variant 必须使用相同 shard boundaries
- 唯一变化的是 backend/device realization

建议目录命名直接体现 pair 结构，例如：

- `e1_eval_m4metal_vs_m4bf16_side_a_run_a`
- `e1_eval_m4metal_vs_m4bf16_side_b_run_a`
- `e1_eval_m4metal_vs_rtxbf16_side_a_run_a`
- `e1_eval_m4metal_vs_rtxbf16_side_b_run_a`

具体命名可以不同，但仅看目录名就应该能看出 pair 关系。

## 5.9 E1 Phase F：构造 pairwise 对比

这是整个 `E1` 最关键的分析步骤。

对于每一组 pair，都要做：

1. 按 `prompt_id` 对齐两侧 evaluation roots
2. 对每个相同 prompt 加载 paired bundles
3. 在这对 bundles 上运行 `THC`
4. 在同一对 bundles 上运行 `TSTC`，并显式接入 `e1_delta_main/delta_map.json`
5. 记录该 pair 是否被 verifier 判为 mismatch

什么算一条 trial：

- 一个 `prompt_id`
- 一个 pair label
- 一种 verifier mode

什么算一条 summary row：

- 一个 pair label
- 一种 verifier mode
- 在所有 matched prompts 上聚合后的 honest-honest FPR

如果当前仓库还没有专门生成 `E1` 最终表格的一键 pairwise driver，不要为了迁就 EXO 回退路线。更合理的做法是基于现有 bundle loader 和 hash-chain 工具，补一个小型离线 evaluator。

推荐直接复用的模块：

- `artifacts/thc/src/checkpoint_qwen.py`
- `artifacts/thc/src/hash_chain.py`
- `artifacts/thc/src/calibrate_delta.py`

## 5.10 E1 Phase G：产出两个正式交付物

### Summary table

`exp_e1_<date>_<owner>_summary.csv`

建议字段：

- `pair_label`
- `pair_side_a`
- `pair_side_b`
- `prompt_count`
- `thc_fpr`
- `tstc_fpr`
- `dominant_mismatch_checkpoint`
- `notes`

### Pairwise detail table

`exp_e1_<date>_<owner>_pairwise_details.csv`

建议字段：

- `pair_label`
- `prompt_id`
- `checkpoint_scope`
- `thc_detected`
- `tstc_detected`
- `thc_first_mismatch_checkpoint`
- `tstc_first_mismatch_checkpoint`
- `localization_label`
- `side_a_capture_root`
- `side_b_capture_root`

对于 honest-honest rows：

- `localization_label = N/A`

## 5.11 E1 Phase H：写回草稿

论文正文只需要保留紧凑结论：

- `THC` 在真实 heterogeneous honest-honest pairs 上会崩
- `TSTC` 仍能保留一个可用的 false-positive operating point
- 这个现象来自真实 backend/device 组合，而不是只来自 synthetic perturbation

不要把大量运行细节塞进主文。

这些细节应该放在：

- notes
- appendix
- artifact description

## 5.12 E1 失败检查表

如果出现下面任意一条，应立即停止并重跑：

- calibration 和 evaluation prompts 混用
- pair 两侧 shard plan 不一致
- capture roots 被覆盖或混写
- pair label 没有真实反映 backend 差异
- 只报 `TSTC`，没有 `THC` baseline
- 最终只有截图，没有原始 CSV

## 6. 各实验与现有仓库工具的快速映射

| 实验 | 主路线 | 现有代码 |
| --- | --- | --- |
| `E1` | 真实异构 capture + pairwise 离线比较 | `artifacts/thc/scripts/t3_hetero_cli.py`，`artifacts/thc/src/hash_chain.py` |
| `E2` | 基于真实 capture roots 的离线 ablation | `artifacts/thc/src/run.py`，`artifacts/TSTC/run_noise_sweep.py` |
| `E4` | 基于 capture roots 的离线 overhead 提取 | `artifacts/thc/src/overhead_report.py` |
| `E5` | trace-driven policy replay / simulator | 复用 `Section 6.1` 数据 + `E1/E4` 输出 |

## 7. 最终结论

结合当前仓库状态，最现实、也最稳的推进顺序是：

1. 先在非 EXO 的 Torch shard chain 上完成 `E1`
2. 让 `E2` 和 `E4` 直接复用 `E1` 产物
3. 让 `E5` 消费已有 measured traces，而不是继续等待 EXO 兼容性变好

这条路线比原始 prototype story 更窄，但对论文当前真正缺失的 claim 来说，反而更强。
