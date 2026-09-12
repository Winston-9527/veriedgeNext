# Route B · G1 技术附录：统计、攻击与实现检查

日期：2026-09-07  
配套入口：[新生实验手册](ROUTE_B_G1_EXPERIMENT_HANDBOOK_2026-09-07.md)。模型统一为 `Qwen/Qwen3-0.6B`；本附录供指导者核对技术细节。  
状态：实验设计与执行规范；不是已完成结果。新增采集器、攻击器和正式统计流水线均须实现后才能运行。  
适用范围：G1 = WP1 honest calibration + WP2 semantic attacks；以最小实验筛选可行机制，再决定是否进入 G2。  
依据：[研究总账](VERIEDGE_ROUTE_B_RESEARCH_HANDBOOK_2026-08-24.md)、[学生手册 §10–11](ROUTE_B_STUDENT_RESEARCH_HANDBOOK_2026-09-03.md)、[PACT spec](ROUTE_B_REDESIGN_PACT_2026-08-24.md)。

## 0. 本手册要交付的结论

G1 要回答：在预先固定的模型、执行配置、边界、误报预算与危害定义下，多数诚实任务能否正常 PASS，而不知道最终挑战 seed 的有害攻击能否被 FAIL 或显式升级？

必须分开报告三个事实：

1. 能否可靠估计数值残差；
2. 数值残差是否能区分诚实执行和实际危害；
3. 升级频率及成本是否使 G0 的经济可行区间仍存在。

G1 的 FAIL 是统计上超过声明的差异边界，不自动证明恶意意图；PASS 是声明范围内的激活一致性判断，不是文本语义正确性证明。INCONCLUSIVE 不是检测成功或攻击被阻止；应报告是否启动升级以及升级最终结果。

本手册不执行 G2 的跨主机吞吐、网络尾延迟、公网随机信标或真实多方非串谋验证。单机中的多进程角色只验证协议逻辑。

## 1. 已核查的资产与现实缺口

| 资产 | 可复用内容 | 不可直接用于什么 |
|---|---|---|
| `experiments/pact_offline/pact_projection.py` | 六 prompt 校准子集上的几何 smoke、Gaussian/Rademacher 对照 | 正式 1% 任务级 FPR、真实语义危害 |
| `calibration_audit.py` | 样本量与校准风险审计 | 新独立语料采集 |
| `adaptive_gaussian_policy.py` / `conditional_power.py` | 理想 Gaussian 的投影不确定性和 K 需求分析 | G16 精确覆盖定理、真实运行时延迟 |
| `known_seed_nullspace.py` | 已知 seed 的几何负对照 | 真实下游语义攻击；脚本中的 residual 正交条件不等于语义危害保持 |
| `pact_g16_protocol.py` / `pact_g16_state_machine.py` | 上下文绑定、回执、状态机与重放控制 | 生产级签名、分布式随机源及可用性保证 |
| `raw_captures/e2_live_subset/` | 已采集的异构张量对子集、prefill C1/C2/C3 | 完整独立校准集；原始 prompt 未随子集提供，不能仅凭张量重现文本攻击 |
| `data_collection/collect_hf_verifier_profiles.py` | 模型加载、checkpoint 选择等参考代码 | 正式 G1 采集和校准，原因见下 |

上述路径分别相对于 Route B 根目录，或其 `shared/accountedge_runtime_and_captures/` 根目录。

### 1.1 现有 HF 采集脚本的四个问题

代码检查确认：

- HF 模式只真实推理一次，`honest_b = honest_a + noise`；第二份张量并非另一个诚实执行。
- 用同一组 honest scores 选阈值并计算 FPR，没有独立 held-out honest 评估。
- 对不同长度 prompt 的张量直接 `np.stack`，没有处理 ragged shape；实际长度不同可能失败。
- 默认只有八条内置 prompt，即使提高 `--max-prompts` 也不会自动产生新语料。

因此不能直接增大该脚本的样本参数来完成 G1。保留旧文件作为 smoke 资产，在新目录实现逐 prompt 的双执行采集器；不要将加噪声标签改成真实异构漂移。

### 1.2 本次单机确认的边界

当前工具环境仅确认 `arm64`，内存查询未获许可，未确认 GPU、可用显存、模型缓存或 PyTorch 后端。因此本手册确认的是每项实验的架构可行性与资源前提，不声称当前这台机器已满足全部条件。硬件 PDF 只能提供历史配置，开跑前仍需实际探测。

## 2. “单机完成”分成三种证据等级

| 等级 | 定义 | 能支持的结论 |
|---|---|---|
| S0：CPU 离线 | 单机读取已有张量，无须模型 | 统计校准、投影几何、协议逻辑；结论限于输入数据来源 |
| S1：单机模型执行 | 同一机器顺序运行两个配置，可使用一个加速器；攻击需可微模型 | 本机实际配置对上的 honest drift 和语义攻击；不代表跨机器泛化 |
| SX：外部数据依赖 | 单机分析异构设备真实采集的数据 | 可评价那些实际设备组合，但从零采集需要对应设备；不可用模拟噪声替代 |

结论：G1 的核心小实验都可在满足内存与模型条件的单机完成逻辑验证和首个配置对的实测；跨硬件推广不能保证仅靠一台普通单加速器机器完成。多张 GPU 不是核心方法要求，跨厂商设备覆盖则是外部证据要求。

参考与实际执行可以顺序加载，不必同时驻留两个模型。角色的独立性在单机实验中是模拟假设，不是物理隔离证据。CPU-only 可完成统计和协议实验；模型推理及 EOT 理论可在 CPU 上执行，但必须经过 pilot 估时，不能承诺实际可承受。

## 3. 总体顺序与小实验清单

所有正式指标与门槛必须在查看正式测试结果之前冻结。本手册给出的 pilot 数量和预算是建议起点，非已批准论文阈值。

| ID | 小实验 | 单机 | 现有能力 / 新工作 | 依赖 |
|---|---|---|---|---|
| E00 | 资产、资源和预注册审计 | S0；设备扩展 SX | 资产清单需新建 | 无 |
| E01 | 既有 smoke 与协议回归 | S0 | 现有脚本可复用 | E00 |
| E02 | 双执行、边界注入与零扰动等价性 | S1 | 采集器和注入器需实现 | E00 |
| E03 | 小样本漂移与 full-energy 筛选 | S1 采集、S0 分析 | 新采集与统计 | E02 |
| E04 | 独立语料与正式 honest envelope | S1；跨硬件 SX | 新语料与双执行采集 | E03 |
| E05 | 顺序 PACT、G16 和三态校准 | S0，使用 E04 数据 | 现有数学/系数实现 + 新评估 | E04 |
| E06 | 配置／语料变化与 profile 失效 | S1；部分配置 SX | 新受控 shift 采集 | E04–05 |
| E07 | 普通篡改与真实输出影响 | S1 | 注入与攻击代码需实现 | E02；正式评估用 E05 |
| E08 | 固定检查攻击与 known-seed 负对照 | S0 几何、S1 语义 | 部分现有；A 攻击环境需恢复 | E02、E05 |
| E09 | unknown-seed EOT、低能量高危害攻击 | S1 | 攻击优化器需实现 | E07–08 |
| E10 | seed、承诺、回执与策略绕过 | S0；真实信标不在范围 | 扩展现有状态机测试 | E01、E05 |
| E11 | 冻结测试、统计汇总与 G0 回填 | S0；补模型运行 S1 | 新汇总流水线 | E04–10 |

先完成 E00–03 与 E07 的小 pilot，再决定是否大规模采集。WP1 数据准备与 WP2 攻击开发可以交错进行；最终评估不得反复利用 held-out 数据调参。

## 4. 统一配置、统计口径与输出

### 4.1 实验单位与模型范围

第一轮固定使用 `Qwen/Qwen3-0.6B` 和短序列 prefill 起步；准确模型哈希、层号与软件版本由 E00 固定。模型名相同但 snapshot 不同不能合并为同一配置。

- C1/C2/C3 写出精确 module path、层索引、张量在 norm/residual 前后的语义。
- 主实验使用实际张量全部声明坐标，`N=T×D`（有 batch 时也明确纳入方式）。
- 不继承旧 T=16 token 抽样作为 PACT 的默认全覆盖定义。若只保护选定 token，必须声明未保护坐标，并增加对这些坐标的攻击测试。
- 主路线先做 prefill 边界扰动并继续生成；decode/KV 攻击单列扩展，未做不能声称覆盖。
- 模型 eval 模式；精度／量化模式须属于部署允许的诚实配置。未批准的精度降级是攻击，不得同时纳入 honest 数据。

### 4.2 预注册文件最低字段

```yaml
study_id: g1_main_v1
status: draft_until_E00_freeze
model_hash: REQUIRED
actual_signature: REQUIRED
reference_signature: REQUIRED
boundaries: REQUIRED_EXACT_MODULE_PATHS
scope: prefill_boundary_then_continuation
split_manifest_hash: REQUIRED
alpha_task: 0.01
min_honest_pass_rate: REQUIRED_BEFORE_FORMAL_TEST
harm_metric: REQUIRED_TASK_BASED_METRIC
harm_floor: REQUIRED_BEFORE_ATTACK_TEST
min_harm_detection_lcb: REQUIRED_BEFORE_FORMAL_TEST
max_inconclusive_rate: REQUIRED_BEFORE_FORMAL_TEST
K_schedule: [8, 16, 32, 64, 128, 256, 512, 1024]
projection_family: REQUIRED_GAUSSIAN_OR_G16
sequential_risk_method: REQUIRED
attack_compute_budget: REQUIRED
attack_prompt_manifest: REQUIRED
seed_domain_policy: optimization_selection_final_disjoint
upgrade_mechanism: REQUIRED_OR_NOT_IMPLEMENTED
```

K=1024 是便于扫描的候选上限，不是新的成功门槛；达到该预算仍低能量逃逸，应结合原总账“约 1000”停止条件判断。alpha=1% 是文档方向，不能覆盖所有其他未定阈值。任何 REQUIRED 未填写时只能跑 pilot，不能宣布正式 GO。

### 4.3 三态与风险组合

定义实际完整残差能量 `F2=||h-h_ref||²/N`；如采用尺度归一化，额外保存原始 F2，归一化分母必须固定且可复现。

- honest envelope 与 material discrepancy threshold 分别预提交，并检查二者顺序与间隔是否合理。
- 上置信界位于 honest envelope 内才 PASS；下置信界超过 material boundary 才 FAIL；其余 INCONCLUSIVE。
- 对多个 K 反复使用同一个固定时刻置信区间会破坏覆盖。使用预先分配每轮风险的 simultaneous bounds，或有依据的 confidence sequence。
- 扩展 K 使用同一承诺和预定随机行前缀。若每行随 K 用 `1/sqrt(K)` 归一化，必须正确重标度已有行，不能直接拼接不同尺度的摘要。
- 理想 Gaussian 的 chi-square 区间不能直接当成 G16 的精确定理。G16 用独立开发数据验证的保守方法，或校准整个冻结策略；声明经验覆盖与适用范围。
- 最终任务 FPR 按“至少一个边界错误 FAIL”计；不把每个边界或每个 seed 当成独立任务。

### 4.4 文件结构（待实现，不代表已有命令）

```text
experiments/g1_validation/
  README.md
  configs/{pilot,main,shift}.yaml
  manifests/{environment,prompts,splits,assets}.json
  collect_dual_execution.py
  validate_boundary_injection.py
  calibrate_task_policy.py
  attacks/
  evaluate_frozen_attacks.py
  aggregate_g1.py
  results/<experiment_id>/<run_id>/
    config_frozen.yaml
    manifest.csv
    per_task.csv
    checks.json
    RESULT_MEMO.md
```

每个 run 保存代码版本、输入哈希、模型／配置、运行时间、峰值内存、随机域和失败记录。上述脚本名是开发合同，不要直接执行尚未存在的文件。

逐任务结果至少含：`prompt_id, split, signature_pair, boundary, attack_id, actual_root, reference_root, seed_domain, policy_hash, full_F2, harm, verdict, stopping_K, upgrade_requested, upgrade_result, elapsed_ms, evidence_bytes`。原始 prompt 如需受控存储，保留可追溯 ID 与 hash。

## 5. E00：资产与资源审计

**问题：** 是否能获得真实双执行、可恢复下游生成和足够独立样本？

**步骤：**

1. 清点 NPZ 文件数、唯一 prompt ID、split、shape、dtype、NaN/Inf；确认 C1/C2/C3 是否成对。区分文件数与独立任务数。
2. 查找完整原始语料及模型/tokenizer 哈希；没有 prompt 的历史张量仅进入离线 smoke。
3. 检查 Python、NumPy/SciPy、torch/transformers、模型路径、设备与可用内存；不自动下载大模型。
4. 列出本机支持的两个真实配置。优先同权重不同受支持执行精度／后端；相同配置真实 rerun 仅作为非确定性对照。
5. 用 2 个 prompt、短序列测前向、后向和峰值资源。估算总 GPU/CPU 小时与存储，不根据模型参数量单独断言显存够用。
6. 冻结 pilot/main/shift split，以及 holdout 的访问规则。

**产物：** `ASSET_AUDIT.md`、环境 JSON、资源 pilot、缺失资产列表、预注册草案。

**结果：** READY；或 BLOCKED_MODEL / BLOCKED_PROMPTS / BLOCKED_BACKEND。若只有一个可执行配置，可继续 S0 和同配置实验，但跨配置 G1 为条件通过，不能靠加噪声补齐。

**单机确认：** 审计 S0 可完成；创建本机不存在的设备组合不可能。无需多机通信。

## 6. E01：已有实现回归

**问题：** 现有张量 schema、投影和状态机是否能在目标实验机复现？

在仓库根目录、已有所需依赖的环境中运行；输出新目录，不覆盖归档结果：

```bash
python research_routes/route_b_veriedge_system/shared/accountedge_runtime_and_captures/scripts/validate_raw_captures.py
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_projection.py --smoke --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/g1_entry_smoke
python research_routes/route_b_veriedge_system/experiments/pact_offline/calibration_audit.py --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/g1_entry_calibration_audit
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_protocol.py --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/g1_entry_protocol
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_state_machine.py --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/g1_entry_state
```

同名输出存在时换新的 run 名。`known_seed_nullspace.py` 还依赖 Gaussian 阈值文件，先检查其 `--thresholds` 输入，不能拿刚生成的 Rademacher 阈值替代。

**检查：** 输入验证通过；合法记录可重放；冲突和超时不变为 PASS；结果与既有 memo 的性质一致。出现数值差异记录平台与容差，先诊断再进入正式采集。

**结果：** 技术入口 READY 或实现 BLOCKED；没有论文级 FPR 或语义结果。

**单机确认：** S0，可用 CPU，无模型或远程节点要求。

## 7. E02：真实双执行与注入器等价性

**问题：** 攻击和诚实差异是否来自真实执行，而非 hook、缓存或层位错误？

**pilot：** 8–16 个开发 prompt；短/中两档长度；三个边界分别运行。建议先关闭采样，固定贪心解码，减少输出随机性混淆。

**步骤：**

1. 同一 tokenization 分别在 actual/reference 配置真实前向，逐 prompt 保存所有目标张量，不通过加噪声生成 reference。
2. 实现对单个声明边界的替换，继续真实下游计算；严格保留 mask、position、residual 及需要的 cache。
3. 做原始无 hook、hook 但 delta=0、保存后原样回注三种路径。
4. 对照 logits、目标 checkpoint 和 continuation；容差在看攻击前冻结，逐 bit 不同可接受但必须落在可解释 rerun 容差内。
5. 做小非零扰动，确认下游实际使用了新张量；确认其他层没有被同时意外改写。
6. 若扩展 decode，单独验证每 step 的 cache/position 与零扰动轨迹；否则明确标记 decode 未覆盖。

**指标：** 最大/均方 logit 差、token agreement、checkpoint root、内存、运行时间、零扰动失败数。

**可能结果：** 全部基线等价可继续；个别后端 hook 不兼容则换受支持实现并重做 pilot；零扰动已改变输出则修实现，不能解释为攻击有效。

**单机确认：** S1，可顺序加载两配置。现有 NPZ 无 prompt 不足以替代此实验。量化后端不支持梯度时，采集仍可用；后续攻击需可微实现或显式迁移攻击验证。

## 8. E03：小样本漂移与全能量筛选

**问题：** 是否已经出现明显的正常漂移崩溃或危害与能量重叠，值得提前改变路线？

**pilot：** 建议 30–50 个开发 prompt，其中 10–15 个真实重跑 3–5 次。这里只筛选，不支持 1% 结论。

**步骤：** 分别绘制同配置 rerun、双配置 honest 的 F2 分布；C1/C2/C3 分开。记录长度和任务类别。加入 E07 的小批普通篡改与下游危害。

增加“全能量 oracle”对照：离线直接用完整 F2 判断，不经过随机投影。在同一个能量阈值框架下，这可判断问题是否来自投影噪声。它不是所有可能验证器的最优下界，也不能用来宣称任意 detector 不可能成功。

**结果解释：**

- full F2 分离清楚、PACT 暂时不分离：优化 K/区间/系数实现，值得继续。
- full F2 中 harmful 与 honest 已大量重叠：增加 K 很可能无济于事，优先 E09 检验低能量攻击。
- honest 存在异常长尾：查配置、mask、shape、执行非确定性，再决定分层校准。
- 只有某边界困难：保留该结果，可提出分边界升级，不删掉困难边界后泛化。

**单机确认：** 采集 S1、分析 S0。已有异构张量也可离线分析但只是历史配置子集。

## 9. E04：正式独立语料与任务级校准

**问题：** 在冻结配置下，诚实任务 FPR 是否达到目标且多数可以 PASS？

**样本：** 一个主 signature pair；建议 200–500 calibration prompt，至少 300 独立 held-out tasks；另选至少 30 prompt 真实重跑 5 次。开发集独立，不计入正式校准或测试。任务长度／类别先分层抽样，近重复同组不得跨 split。

**步骤：**

1. 冻结 split manifest；逐 prompt 真实双执行，保留变长张量与元数据；失败/超长/缺失样本记录原因，不能按检测结果删除。
2. 从开发集固定归一化、边界集合、材料差异门槛、策略候选。
3. 在 calibration 集校准；预注册两种比较：边界 alpha 分配加 union bound；固定边界集合的 task-max 分数。若比较多个方案，全部报告，不能根据 held-out 挑优后只报一个。
4. 在独立 held-out 上评估最终 task verdict；同时给边界诊断。
5. 汇报 false FAIL、PASS、INCONCLUSIVE、缺 profile 和升级比例；保留逐任务长表。

**样本量注意：** 单侧 conformal 最细非零分辨率 `1/(n+1)`；99 是单个 1% score 的最低门槛，不是任意多边界/多轮组合的保证。若三个边界各分配 alpha=0.01/3，仅分辨率就至少需要 299 calibration 分数；若还拆分风险预算则可能更多。具体预算必须重算。

独立 held-out 有 0 次 false FAIL 时，单侧 95% 二项上界为 `1-0.05^(1/n)`；n=299 才约不超过 1%。若出现 false FAIL，应报告真实上界，不事后增加样本直到恰好过线，除非预注册了有效顺序方案。

**结果：** FPR 上界和 PASS 比例同时满足才通过。FPR 低而多数 abstain 是失败/改设计信号。重复 projection seeds 不增加独立任务数；重复执行是 prompt 内相关数据。

**单机确认：** S1 从零采集本机配置对，S0 校准；不同厂商硬件推广为 SX。采集可以串行或断点续跑，不需要两个实时节点。

## 10. E05：K、顺序裁决与 G16 有效性

**问题：** 误报是否因多轮停止或系数量化失控？更大的 K 是否真的有收益？

**步骤：**

1. 固定 K 网格 `[8,16,32,64,128,256,512,1024]`，比较 full F2、理想 Gaussian 与实现 G16。
2. 对同一已固定残差计算多次随机投影；只把这些重复用于条件分布诊断。
3. 固定每轮覆盖预算或合法顺序区间，评估完整停止策略，不只验证每个 K 的边际 FPR。
4. 检查前缀扩展、系数 digest、张量规范序列化、累加顺序；区分直接物化计算与分布采样模拟。
5. G16 另行验证整个冻结策略在独立任务上的 FPR。理想 Gaussian 公式只能标 theoretical，不充当 G16 有限表证明。
6. 输出 K 分布、interval coverage、各轮停止数、证据字节与投影 CPU 时间。参考推理时间不在本实验中凭空置零。

**结果：** 小 K 足够则支持廉价检查；某边界需要大 K 则反馈 G0 成本；full F2 已重叠而 K 无帮助则转 E09；G16 偏离则改保守区间/实现或保留 Gaussian 分析，不能套精确公式。

**单机确认：** S0。大矩阵用逐行/分块生成，避免物化 K×N；CPU 即可，显式测运行时间。

## 11. E06：受控 shift 与 profile 有效期

**问题：** 冻结校准在变化后会怎样失效？系统是否识别适用范围？

**设计：** 一次只改变一个因素。首选本机能执行的精度/后端，或长度/任务类别变化；设备变化仅有实际设备时做。pilot 每条件 30–50 个新任务；正式 shift 误报主张按 E04 单独计算样本量。

**步骤：**

1. 原 signature + 原 profile，作为稳定对照。
2. 新 signature + 旧 profile：诊断性离线比较误报/漏检变化，不能部署为合法路径。
3. 新 signature + 版本检查：应拒绝旧 profile 或 INCONCLUSIVE。
4. 独立新 calibration 更新 profile，在新 held-out 上复核。
5. 对 signature 不变但 prompt 分布变化的情况单独记录。版本检查不会自动识别这种 shift；如果没有统计漂移监控，就明确写“未覆盖”，不能假装已能自动失效。

**结果：** 可检测配置变化并重校准，支持受控部署；重校准恢复但成本高，回填维护成本；扩充数据仍不稳定，限制范围或换验证粒度。

**单机确认：** 本机精度/软件/语料 shift 为 S1；指定 CUDA↔MPS 等机器不具备的组合为 SX，不能用容器名称冒充硬件差异。

## 12. E07：普通篡改与危害测量

**问题：** 检查是否检测实际执行异常，危害定义是否可操作？

**pilot：** 20 个开发 prompt，三个边界，每种攻击 3 个预定强度；失败配置也保留。正式攻击集独立，数量在 pilot 后按目标置信精度冻结，不自动沿用 honest 的 300 数字。

**攻击：** Gaussian/noise、scale、同 shape 旧任务激活替换、wrong-shard（只在 shape/语义可定义时）、layer skip、允许范围外的精度变化。每项记录可实现性，不能用随机噪声冒充真实跳层。

**步骤：** 在 E02 验证的边界注入，运行真实 continuation/任务评分；生成实际/reference commitment 后再揭示最终投影 seed。采样策略固定，推荐首轮 greedy；后续 stochastic 要给相同策略的 clean 基线。

**指标：** 目标任务正确率、目标攻击成功率、token agreement、ROUGE-L 等辅助相似度、logit surrogate、F2、三态、K、升级。文本不同不自动定义为 harmful。

**结果：** 能检测明显故障仅证明基本能力；变化大而任务仍正确不能计为有害成功；有害低能量实例进入 E09；全攻击被检测也不替代专门自适应攻击。

**单机确认：** S1，一次一个模型/边界即可。尚无可运行语义 harness，需实现后才能确认本机耗时。

## 13. E08：A 攻击复用与时序负对照

**问题：** 老的 fixed-check 逃逸是否因 post-commit timing 被打破？

**三组对照：**

1. 已知旧固定映射，优化其 nullspace/tolerance 攻击，在旧检查上验证逃逸；随后冻结张量，用新 PACT seed 评估。
2. 已知本次 PACT 矩阵后构造 kernel 扰动：预期保留投影证据，验证脆弱时序。
3. 相同级别攻击预算但先冻结张量再抽 PACT seed：真正威胁模型条件。

必须分开几何逃逸和语义逃逸。`known_seed_nullspace.py` 可复用第 2 组几何部分，但没有下游模型输出，不支持“保持语义危害”的结论。正式语义对照必须额外测任务结果；无法找到有害 kernel 向量时报告这一限制，不强行要求语义攻击成功。

**审计：** 计算 `||A delta||/||delta||`、承诺时间顺序、seed 来源、actual/ref 关系；已知 seed 对照意外被检测先查数值精度、归一化和攻击构造，不称为突破零空间。

**结果：** 老攻击失效支持时序设计但不是全攻击安全；unknown-seed 仍成功则定位是否 residual 太小、上下文错误或统计区间过宽。

**单机确认：** S0 几何；S1 实际危害。A 完整目录当前未随仓库提供，恢复其攻击环境是可选对照依赖；缺失不能阻止 E09 独立开发，但须标 baseline 缺口。

## 14. E09：unknown-seed EOT 与低能量高危害搜索

**问题：** 当前能量一致性检查的最危险失效路径是否真实存在？

**开发顺序：** 先 8 个开发 prompt、一个边界验证优化；再 20–30 个开发 prompt 覆盖三个边界；仅在优化和注入正确后冻结正式矩阵。

**至少三种优化目标：**

- Harm-only：预算内最大化任务危害，作为强攻击基础。
- Low-energy/high-harm：在满足预定义目标危害的条件下尽量降低 F2，或扫描危害与能量的权衡。
- EOT：最大化危害，同时惩罚未来 seed 分布下的检测 surrogate；最终仍以真实三态裁决评估。

攻击目标、残差约束、可见参考信息必须写清。允许攻击者利用精确 reference 时标注更强白盒假设；不给 reference 时使用它估计或可获得的信息。若只在可微 surrogate 模型上优化，必须转移到目标执行栈实测，不能混合为原生攻击结果。

**建议 pilot 预算（正式前可调整并冻结）：**

- 梯度步数 50/200，2 个 restart，EOT 每步 8/32 个 optimization seeds；
- 使用 selection seeds 选择候选，不能读取 final seeds；
- 最终冻结 tensor 后用 256 个新 seed 估计条件检测，必要时增加精度但不增加 prompt 样本量；
- 强度先复用 rho=0.01/0.02/0.05 作为数值轴，另扫支持大小／稠密度；rho 不代替 harm floor；
- 每个 prompt 预算相同或按预注册规则分配，记录提前停止、失败和 OOM。

上述预算只是小实验起点。若增加步数仍持续改善攻击，应扩大开发预算或把攻击强度不足列为限制；未找到逃逸不是不存在逃逸的证明。

**步骤：**

1. 开发数据固定模型、任务评分、诚实阈值与危害门槛。
2. 三种目标分别搜索，记录所有候选能量/危害，不只保留最好 seed。
3. 使用 selection seeds 选最终攻击；序列化并 hash，保存不可变 attack manifest。
4. final-test evaluator 单独进程产生新 seed；攻击器不读取该域。单机进程隔离只服务实验纪律，不证明抗本机恶意管理员。
5. 真实下游生成并评分，分别报告全部尝试和达到 harm floor 的攻击子集。
6. 在同一冻结攻击上对比 full F2、Gaussian、G16、固定 K、预注册 adaptive K。

**核心输出：** 危害—F2 散点、harmful-PASS 比例、条件 FAIL 与升级比例、K 和成本分布、按 prompt 聚类的不确定性。

**可能结果及动作：**

| 观察 | 判断 | 下一步 |
|---|---|---|
| 满足 harm floor 的攻击稳定 FAIL | 支持声明范围内的检测能力 | 扩独立 prompt、第二配置复核 |
| 有害攻击主要 INCONCLUSIVE | 只有升级触发能力 | 测实际升级，回填 G0，不能报为直接检测 |
| full F2 也无法分离有害和诚实 | 能量统计的根本限制候选 | 验证优化与危害质量后收缩主张/改机制 |
| full F2 分离而低 K 不分离 | 投影预算问题 | 边界特定 K；核算成本 |
| 仅一个任务/边界逃逸 | 有效反例候选，泛化频率未知 | 保存实例，独立复核，不能按平均数掩盖 |
| 优化未产生危害 | 攻击尚不充分或模型较稳健 | 验证梯度与预算；不能因此宣布 detector 强 |

**单机确认：** S1，需可微模型及足够内存；可通过梯度检查点、逐 prompt、EOT 分批和投影流式降低占用。模型/后端不支持反向是明确 BLOCKED，不是“多开进程”能解决。没有必须跨机器的计算步骤。

## 15. E10：承诺、挑战和策略逻辑对抗

**问题：** 统计实验的承诺时序是否在代码中真实执行？

**测试矩阵：** root 替换、接收字节与 root 不符、reference 替换、重放 task/boundary、seed 复用、K 前缀切换、profile 版本替换、延迟/缺失回执、commit/reveal 后中止、重启后重复裁决。

对 audit prediction/root grinding：仅在实现了相应审计随机决策后执行。固定若干承诺前攻击策略，检查攻击者是否能利用暴露元数据显著提高逃避审计概率；如果还没有审计调度器，标 NOT_IMPLEMENTED，不能声称 PACT 状态机已覆盖。尝试多个 root 本身不等于 grinding 成功，需证明可以从中预测或选择有利的未知挑战。

**判定：** 冲突必须拒绝/冻结；超时应 ABORTED，不可 PASS。合法任务应能完成；记录错误接受率、错误拒绝率、每种 fault 的终态。协议中止率不计入统计 TPR。

**单机确认：** S0，多对象或多进程足够；真实非串谋、独立信标不可预测性、网络分区与跨主机可用性不由此确认。不能将统计随机性测试当成密码学不可预测性的证明。

## 16. E11：最终统计、G0 回填和决策

**统计输出：**

- honest task FPR 及单侧置信上界，PASS/INCONCLUSIVE 比例；
- 真实攻击成功率、harmful-PASS、harmful-FAIL、harmful-INCONCLUSIVE；
- 同时报告“全部攻击尝试”与“达到 harm floor 的攻击”的分母，避免只报条件成功；
- 对重复 seed 先计算 prompt 内比例，再按 prompt 聚类 bootstrap；样本太小时明确不足。单次任务终态的独立样本可用二项区间；
- C1/C2/C3、配置、攻击族分开，加预注册的任务级合并；多重结论使用预注册同时区间或标探索性；
- semantic examples 附 prompt/attack/commitment ID，不能用手挑例子替代统计；
- Gaussian theoretical、G16 empirical、synthetic、real execution 分栏。

**回填 G0：** 每个配置/边界导出 `conditional_fail_rate, inconclusive_rate_clean, inconclusive_rate_attack, stopping_K_distribution, projection_cost, evidence_bytes, upgrade_result_or_unknown`。如果升级未实现，只能扫描其成本和效果，不能把所有升级当作检测成功。单机成本是 local_measured，不能填成三节点实测。

**决策表：**

| 决策 | 必要证据 | 动作 |
|---|---|---|
| GO_G1_LOCAL | 主配置 honest 受控且正常 PASS；未知 seed 有害攻击按预注册目标被检测/有效升级；无协议假通过 | 将实测参数交回 G0；两关同时可行再进入 G2 |
| CONDITIONAL_GO | 仅部分边界/配置通过，或依赖尚未实现的升级；跨硬件尚无证据 | 列出具体范围、待测组件和最小复核 |
| NO_GO_STRONG_CLAIM | 可靠复现低能量有害逃逸；校准长期不稳；多数任务依赖昂贵升级 | 收缩数值一致性主张、改机制或停止强系统路线 |
| BLOCKED | 无真实双执行、无语义路径、数据/模型缺失 | 明确资产与解锁实验，不将未知算负结果 |

K 接近 1000 仍不能分离危害与 honest envelope 是原总账的重要停止信号；单个 seed 或未经验证的注入错误不能触发科学结论。local GO 不等于部署级跨硬件 GO。

## 17. 单机资源预算与扩展边界

先测 2–8 prompt 的 pilot，再外推；不承诺固定 GPU 小时。记录每任务前向时间 `t_f`、每攻击步时间 `t_b`、投影次数、设备峰值内存。

- 采集大致计算量：两个 stack × 独立 prompt 数 × 一次前向，另加真实 repeats；按实际批处理策略估时。
- 攻击量：prompt × boundary × objective × restart × step × 每步 EOT 成本；不要第一轮同时铺满所有维度。
- FP32 保存三个边界的两份张量：约 `2×3×T×D×4` 字节/任务，不含 metadata。T=512、D=1024 时约 12 MiB；800 个任务约 9.4 GiB，另计 repeats 与攻击张量。压缩收益不能预先保证。
- K=1024、N=512×1024 的完整 FP32 投影矩阵约 2 GiB；逐行或分块生成，避免再叠加 EOT batch 造成峰值。
- 攻击梯度、KV/cache 和框架缓冲可能远大于权重，不能用“0.6B 权重装得下”推导 EOT 可运行。

**从零完成跨硬件 G1 的例外：** 如果目标主张指定 CUDA/MPS 或不同 GPU 架构，本机缺其中一种就必须外部采集。数据可顺序拷回单机分析，不要求同步三机，但确实需要那些设备。已有匿名捕获只支持其有限 prompt，不能扩展为新语料证据。

## 18. 推荐批次与交付清单

- 批次 A：E00–02。交付真实双执行与零扰动等价性，先确认实验平台有效。
- 批次 B：E03 + E07 pilot。快速检查漂移及真实危害，避免盲目大规模采集。
- 批次 C：E04–06 正式校准；同时在独立开发数据完成 E08–09 攻击开发。
- 批次 D：冻结攻击/阈值/策略后运行 E09 正式测试与 E10 协议审计。
- 批次 E：E11 汇总及 G0 重算，决定是否投入 G2。

最终交付：

1. 一份 `G1_DECISION_MEMO.md`：研究问题、冻结门槛、实际结论、适用范围与未决问题。
2. E00–11 每项状态：DONE / FAILED / BLOCKED / NOT_IMPLEMENTED；单机等级和实际设备。
3. 数据与配置 manifest、逐任务结果、所有负结果、复现环境。
4. honest/attack 分离图、K/升级分布、shift 对照、G0 参数接口表。
5. 列出尚未实现的升级、真实信标、跨硬件覆盖，禁止把模拟结果写成实测。

本手册完成的是实验设计。正式执行前应将全部 REQUIRED 门槛、资源 pilot 和样本划分补齐；实验结果无论正负都按同一冻结标准报告。
