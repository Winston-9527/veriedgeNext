# early_research：降档检测方向的早期探索

整理日期：2026-10-13

本目录收录 2026-10 关于"去中心化流水线推理中检测节点降精度（降档）"的早期探索：
相关工作调研、主动信号（QFC / 公开放大器）的推导、被动 canary 基线实验 E0
（Qwen3-0.6B 与 Qwen3-4B，CUDA 与 Apple 跨硬件），以及给新同学的排雷任务清单。
这些是**研究过程记录，不是论文 claim**；数字的口径和局限见各自的 memo。

## 从哪里读起

| 想了解 | 读这个 |
|---|---|
| 新同学的任务安排 | [`UNDERGRAD_TASKLIST_2026-10-13.md`](UNDERGRAD_TASKLIST_2026-10-13.md) |
| 相关工作与"主动信号"的空白 | [`docs/ACTIVE_SIGNAL_SURVEY.md`](docs/ACTIVE_SIGNAL_SURVEY.md) |
| QFC（量化脆弱 canary）推导，以及 E0 之后的修正 | [`docs/QFC_METHOD_DERIVATION.md`](docs/QFC_METHOD_DERIVATION.md) |
| E0 实验设计（被动 canary + 升级攻击） | [`E0/docs/E0_EXPERIMENT_DESIGN.md`](E0/docs/E0_EXPERIMENT_DESIGN.md) |
| E0 结果：Qwen3-0.6B | [`E0/results/full_20261009/E0_RESULTS_MEMO.md`](E0/results/full_20261009/E0_RESULTS_MEMO.md) |
| E0 结果：Qwen3-4B 与单分片降档 | [`E0/results/qwen3_4b_20261009/E0_4B_RESULTS_MEMO.md`](E0/results/qwen3_4b_20261009/E0_4B_RESULTS_MEMO.md) |
| 公开放大器能省多少请求 | [`E0/results/qwen3_4b_20261009/AMPLIFIER_DERIVATION.md`](E0/results/qwen3_4b_20261009/AMPLIFIER_DERIVATION.md) |
| 按档重算（同档诚实栈） | [`E0/results/qwen3_4b_20261009/analysis/same_tier.txt`](E0/results/qwen3_4b_20261009/analysis/same_tier.txt) 与 `analysis/tier_*/` |

## 目录

```text
early_research/
├── README.md
├── UNDERGRAD_TASKLIST_2026-10-13.md   # 新同学任务清单（笔记本 RTX 5060 + RTX3090）
├── docs/                              # 调研与方法推导
└── E0/
    ├── docs/                          # 实验设计
    ├── scripts/                       # 采集与分析脚本（torch / mlx / 统计）
    └── results/                       # 两次运行的报告、CSV、摘要清单
        ├── full_20261009/             # Qwen3-0.6B，19 个执行栈
        └── qwen3_4b_20261009/         # Qwen3-4B，30 个执行栈（含单分片降档）
```

## 截至目前的主要结论

1. **诚实漂移集中在平局附近。** 同档、跨硬件的诚实执行几乎只在 top-1/top-2 接近平局处失配；
   计算精度为 fp16 时，CUDA 与 Apple 的输出几乎完全一致。
2. **0.6B 高估了降档信号。** 换成 4B 后，4-bit 造成的失配下降 40–50%；
   最难的是"单分片 + GPTQ"，误差只有诚实噪声的 2–4 倍。
3. **诚实栈应按档定义。** 诚实节点使用同一份权重、同一种计算精度，只有硬件和后端不同。
   早期把不同精度都算作诚实（包括 Route B 720 池的 MPS bf16 对 CUDA fp32）会高估诚实噪声。
4. **设计取向。** 在节点有义务提交证据的流水线协议里，PACT 式的边界证据
   （先承诺、后抽取随机投影）优于在模型里植入信号：能定位、证据更省、不影响输出质量，
   开源模型的 diff 攻击也无效。输出端的公开放大器只适合作为黑盒兜底。

## 复现说明

- 脚本按当时的 CUDA 服务器与 Apple M4 节点的环境编写，路径和 Python 环境可用环境变量覆盖，见各脚本开头说明。
- 原始 captures（每个执行栈的 top-5 logits npz）没有放进本仓库。
  `E0/results/*/MANIFEST.sha256` 记录了它们的摘要；学生交接包 `e0_captures_for_student.tar.gz` 由导师单独提供。
- prompt 数据 `qwen_prompt_splits_stratified_v2_200_500.jsonl`（sha256 前缀 `5f1be1ee`）在 ndss2027 主仓库，也包含在交接包里。
