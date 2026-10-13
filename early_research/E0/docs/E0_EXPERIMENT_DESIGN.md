# E0：被动 canary 基线与"不确定性升级"攻击

- **日期**：2026-10-09
- **上游**：[QFC_METHOD_DERIVATION.md §2 / §8](../../docs/QFC_METHOD_DERIVATION.md)
- **要回答的问题**：不往模型里植入任何东西，只靠"自然 prompt + 预存全精度 top-1"的被动 canary，能不能检出 4-bit（或 8-bit）精度降级？如果攻击者在自己不确定时切回全精度（升级攻击），这种检测还剩多少？
- **为什么要做**：E0 决定 QFC 的动机是否成立。
  - 如果被动 canary 在升级攻击下仍然便宜好用，QFC 的卖点就只剩"更省 canary"。
  - 如果被动 canary 被升级攻击打穿，"植入后量化模型完全看不出自己在被测"这一点就是核心贡献。

## 1. 设计

**contexts（canary 单元）**
- 来源：`qwen_prompt_splits_stratified_v2_200_500.jsonl`，用 evaluation split 的 520 条。
- 由 fp32 参考模型贪心续写 64 个 token。
- 每个续写位置都是一个"下一 token 预测"context，约 3.3 万个。
- 所有执行栈都在**同一串 token id**上做 teacher-forced 前向，逐 context 对齐，不重新分词。
- calibration split 的 200 条只给 GPTQ 做校准，不参与评估。

**执行栈**

| 栈 | 框架 / kernel | 说明 | spec_bf16 下的角色 | spec_8bit 下的角色 |
|---|---|---|---|---|
| `torch_fp32` | torch CUDA | **参考** | ref | ref |
| `torch_fp32_eager` | torch CUDA，eager 注意力 | 换注意力实现带来的漂移 | 诚实 | 诚实 |
| `torch_bf16` / `torch_fp16` | torch CUDA | 计算精度漂移 | 诚实 | 诚实 |
| `mlx_bf16` | mlx CUDA（EXO 的 kernel 路径） | 跨框架漂移 | 诚实 | 诚实 |
| `apple_mps_{fp32,bf16,fp16}` | torch MPS（Apple M4 节点） | 跨硬件漂移 | 诚实 | 诚实 |
| `apple_mlx_bf16` | mlx Metal（Apple M4 节点） | EXO 在 Apple 上的 kernel 路径 | 诚实 | 诚实 |
| `torch_rtn_w8g128` | 权重 RTN fake-quant | 8-bit 权重 | 作弊 | 诚实 |
| `torch_bnb_int8` | bitsandbytes LLM.int8 | 真实 8-bit kernel | 作弊 | 诚实 |
| `mlx_8bit` / `apple_mlx_8bit` | mlx-community 8-bit（EXO 默认），CUDA / Metal | 真实 8-bit kernel | 作弊 | 诚实 |
| `torch_rtn_w4g128` | 权重 RTN fake-quant | 4-bit，最朴素 | 作弊 | 作弊 |
| `torch_gptq_w4g128` | 紧凑 GPTQ（无 act-order，非逐层顺序） | 4-bit，带误差补偿 | 作弊 | 作弊 |
| `torch_bnb_nf4` | bitsandbytes NF4 | 真实 4-bit kernel | 作弊 | 作弊 |
| `mlx_q4` / `apple_mlx_q4` | mlx 4-bit，group 64，CUDA / Metal | 真实 4-bit kernel | 作弊 | 作弊 |
| `apple_mps_rtn_w4g128` | torch MPS + RTN 4-bit | Apple 上的作弊者 | 作弊 | 作弊 |

说明：
- fake-quant 栈只降低**权重**精度，计算仍在 bf16 下进行，用来隔离"权重精度"这一个变量。真实低比特 kernel 的效果由 bnb 和 mlx 栈覆盖。
- embedding 和 lm_head 都不量化（Qwen3-0.6B 的两者是共享权重的）。

**指标**

- **失配**：某栈的 top-1 ≠ 参考栈的 top-1。
  - 诚实栈的失配率记为 `p_h`，取诚实栈中最差的一个，并用 Wilson 95% 上界。
  - 作弊栈的失配率记为 `p_q`。
- **A. 总体失配率**：按 prompt 做 cluster bootstrap 求 95% CI。另外报告"翻转处作弊栈自身 margin"的中位数，它直接反映升级攻击有多便宜：翻转处的 margin 越小，越容易被攻击者自己察觉。
- **B. 按参考 margin 分箱**：用 10 个分位箱。验证方从所有连续区间（覆盖 ≥5% 的 context）里挑所需 canary 数最少的一个作为 canary 来源。**区间在偶数 prompt 上挑、在奇数 prompt 上报告**，避免在同一份数据上挑最优带来的乐观偏差。
- **C. 升级攻击**：攻击者把自身 margin 最小的 r 比例 context（r ∈ {0, 1, 2, 5, 10, 20, 30, 50}%）改用全精度栈重算，平局随机打破，保证成本恰好为 r。
  - spec_bf16 下全精度栈用 `torch_bf16`，spec_8bit 下用 `mlx_8bit`。
  - 每个 r 下验证方重新挑最佳区间，再求精确二项设计 `(N, k)`，使 FPR ≤ α 且 FNR ≤ β，α = β = 10⁻³。
- **D. 量化器感知的 canary 池**：这是最强的被动基线。验证方自己模拟一个作弊量化器（selector），挑出"selector 会翻转、且 selector 最自信"的 K 个 context（K ∈ {50, 200, 1000}）组成 canary 池。
  - selector 和攻击者相同时称为 oracle，是上界；不同时测的是迁移性。
  - 这类 canary 天然抗升级攻击（因为翻转处攻击者的 margin 大），所以它是 QFC 必须打败的对手。

## 2. 预注册判据

对每个 4-bit 作弊栈（spec_8bit 设定），记 `N(r)` 为升级成本为 r 时的最小精确 canary 数。

- **QFC 动机成立**（`motivation_holds = True`）：`max_{r≤10%} N(r) ≥ max(10·N(0), 1000)`。含义是：攻击者只要花不到 10% 的全精度重算，就能让被动 canary 的成本放大一个数量级，或者超过 1000。
- **D 部分是补充判据**：如果迁移设定下（selector ≠ 攻击者）的池子在 10% 升级下仍然有 N ≤ 50，就说明被动方法里存在抗升级的天然 canary。这时 QFC 的贡献要改写为"不需要知道攻击者用哪种量化器"和"canary 池的规模"，而不是"被动方法完全不行"。
- **报告纪律**：两个判据如实报告，不调参数去凑结果。区间挑选规则、α、β、升级比例网格都已在脚本里固定。

## 3. 复现

脚本在 `early_research/E0/scripts/`。CUDA 栈在 CUDA 服务器上跑，Apple 栈在 Apple M4 节点上跑（节点地址不写进文档，下面用 `<cuda-host>` 代替）：

```bash
rsync -a early_research/E0/scripts/ <cuda-host>:qfc_e0/<run>/scripts/
rsync -a <main>/workspace/AdversarialEvaluation/data/qwen_prompt_splits_stratified_v2_200_500.jsonl <cuda-host>:qfc_e0/<run>/data/   # 该文件在 ndss2027 主仓库，不在本仓库
ssh <cuda-host> 'cd ~/qfc_e0/<run> && nohup bash scripts/run_e0.sh . 0 > run.log 2>&1 &'
```

- **Apple 侧**：把 CUDA 服务器产出的 `contexts_eval.jsonl` 原样拷到 Apple M4 节点的 run 目录（sha256 必须一致），运行 `bash scripts/run_e0_apple.sh .`；再把 `captures/apple_*.npz` 拷回 CUDA 服务器的 `captures/`，运行 `bash scripts/analyze_e0.sh .`。分析会自动纳入所有已存在的栈。
- 第二个参数 `limit > 0` 表示冒烟测试，只取前 limit 条 prompt。
- 可用环境变量：`SKIP_MLX=1`、`SKIP_BNB=1`、`GPU=<idx>`。
- **环境**：
  - torch 栈用 `/usr/bin/python3`（torch 2.13 + cu130、transformers 5.7、bitsandbytes 0.50）；
  - mlx 栈用 `~/verifiable-exo-smoke/.venv`（mlx_lm 0.31.3，已装 NVRTC 头文件修复）；
  - 全程 `HF_HUB_OFFLINE=1`，只用本地缓存的 `Qwen/Qwen3-0.6B`（snapshot c1899de）和 `mlx-community/Qwen3-0.6B-8bit`。
- **产物**：
  - `contexts_*.jsonl` 和对应的 `.meta.json`（含 sha256）；
  - `captures/<stack>.npz`：逐 context 的 top-5 ids 和 logits，meta 里有版本、设备、contexts 摘要；
  - `analysis/{spec_bf16,spec_8bit}/`：`E0_REPORT.md`、`e0_summary.json`、三个 CSV、升级曲线图。

## 4. 已知局限

- 跨硬件只覆盖 NVIDIA（CUDA 服务器）和 Apple M4 两种；RTX3090 当天连不上，没有纳入。
- GPTQ 是紧凑实现（无 act-order，各层用 fp32 模型的输入算 Hessian），比生产版 GPTQ 略弱。AWQ 没有覆盖。
- canary 用的是 teacher-forced 的续写位置。实际部署时要把"prompt + 参考续写前缀"作为原始文本补全请求发出去，等价于这里的设定。
- 模型只有 Qwen3-0.6B 一个。更大的模型量化损失更小，`p_q` 可能更低。

## 5. E0-scale：Qwen3-4B 与单分片降精度（2026-10-09 追加）

**动机**：0.6B 对量化异常敏感（整模型 4-bit 让 top-1 翻转约 20%），所以 E0 的结论只能算乐观上界。0.6B 上的实验只能否定想法，不能支持想法。另外，流水线里作弊者通常只控制一个分片，信号会被稀释。

**设计**（脚本 `run_e0_scale.sh` / `run_e0_scale_apple.sh`，分析沿用 `analyze_e0.sh`）：
- **模型**：Qwen3-4B，36 层，checkpoint 是 bf16；和 0.6B 共用 tokenizer，因此 prompt 的 token id 可以直接复用。
- **资源约束**：
  - CUDA 服务器是共享卡，空余约 11 GB，所以 fp32 参考放在 CPU 上算；contexts 用 bf16 在 GPU 上生成。contexts 只是 token 序列，不参与比较。
  - Apple M4 节点只有 16 GB，跑不了 fp32，Apple 侧只跑 bf16/fp16 和量化栈。
- **栈**：
  - 诚实栈：CPU fp32（参考）、CUDA bf16/fp16、mlx-CUDA bf16、Apple MPS bf16/fp16、mlx-Metal bf16；
  - 8-bit：RTN、bnb、mlx-CUDA、mlx-Metal；
  - 整模型 4-bit：RTN、GPTQ、NF4、mlx-CUDA、mlx-Metal、MPS-RTN；
  - **单分片 4-bit**：把层分成 0–11 / 12–23 / 24–35 三段，每段单独做 RTN、GPTQ、mlx 4-bit，栈名为 `*_L<a>-<b>`。
- **mlx 量化方式**：从原版权重加载后在内存中量化，参数和 `mlx_lm convert -q` 相同（affine，group 64）。整模型量化时 embedding 和 lm_head 也一起量化，与 mlx-community 发布的版本一致；单分片量化只动该段的 decoder 层。
- **GPTQ**：Hessian 改为在 CPU 上用 fp32 累积（4B 的 down_proj 单个 H 就有 9728² 个元素），用 bf16 模型做校准前向。

**解读时的注意点**：
- 升级攻击默认攻击者能看到最终 logits 的 margin，这只对**尾分片**成立。头分片和中间分片只能看到激活值，没有这个信号。所以对非尾分片的作弊者，"无升级"那一行才是现实的检测强度，升级曲线只是一个保守的上界攻击。
- 和 0.6B 的结论对照时，要看整模型 4-bit 的 `p_q`、诚实失配的平局结构、误差窗口（`e0_error_scale.py`），这三项在不同模型规模下各自怎么变化。
