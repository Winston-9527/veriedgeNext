# 实验A交付物

本目录是对照 `veriedge_revision_workbook.md` 中 **Experiment A: Closed-loop Verifiability-Constrained Placement** 整理的最终交付包。

## 打开顺序

| 优先级 | 文件 | 用途 |
|---:|---|---|
| 1 | [ExperimentA_A1_A3_results.md](ExperimentA_A1_A3_results.md) | 主结果文档，推荐优先打开 |
| 2 | [MANIFEST.md](MANIFEST.md) | 完整文件清单与目录说明 |
| 3 | [docs/文件索引.md](docs/文件索引.md) | 中文索引，适合快速定位数据、图、脚本 |

根目录下保留了 4 张 `fig_*.png` 图片副本，这是为了让主 Markdown 使用最简单的相对路径直接显示图片；正式矢量版和高清版在 `figures/` 中。

## 交付范围

本包只纳入 workbook 当前硬要求相关实验：

- A1 Controlled Replay：closed-loop verifiability-constrained placement replay 主实验。
- A3 Queue-Aware Replay：queued workload 下加入 busy queue scoring 的补充消融。

不纳入主线的内容：

- A2 Trace-backed Replay：可以作为 robustness check，但不是 workbook 最低硬要求。
- A4 Hard-filter Stress Slice：可以作为 appendix/stress test，但不是 workbook 最低硬要求。

## 目录结构

| 目录 | 内容 | 是否主交付 |
|---|---|---|
| `data/` | workbook 要求的三个输入文件 | 主交付 |
| `results/` | per-task runs、summary、per-seed summary | 主交付 |
| `figures/` | PNG/PDF 图像文件与图表索引 | 主交付 |
| `docs/` | workbook 副本、中文解读、文件索引 | 主交付 |
| `scripts/` | 复现实验和重画图脚本 | 主交付 |
| `paper_snippets/` | 可回填论文的 caption / subsection / abstract numbers | 主交付 |
| `metadata/` | 环境、网络、git 信息 | 辅助交付 |

## 快速结论

在 `queued-8, alpha=0.10, beta=0.90` 下：

| Policy | Goodput | False risk | Infeasible |
|---|---:|---:|---:|
| `network_aware_projcos4` | 1.079 | 0.0105 | 1.000 |
| `verif_constrained_projcos4` | 1.060 | 0.0020 | 0.000 |
| `network_aware_adaptive` | 1.079 | 0.0005 | 0.000 |
| `queue_aware_network` | 12.266 | 0.0142 | 0.935 |
| `queue_aware_verif_constrained` | 10.392 | 0.0033 | 0.000 |
| `queue_aware_adaptive` | 12.251 | 0.0028 | 0.000 |

结论：measured verifier profile 可以在 placement 前作为 admission / verifier-selection constraint 使用；queue-aware 调度能显著改善 goodput，但不能替代 verifier constraints。

## 图像状态

- `fig_placement_frontier_a1`：A1 controlled replay frontier，单独展示主机制。
- `fig_placement_frontier_a3_queue`：A3 queue-aware frontier，单独展示 busy queue scoring。
- `fig_risk_class_composition`：policy 选择结果的 low-risk / infeasible 组成。
- `fig_alpha_sensitivity_infeasible`：alpha sensitivity；由于多条线在 0/1 处重合，使用面板下方图例避免标签堆叠。

## 复现方式

```bash
python3 scripts/run_experiment_a_full.py
python3 scripts/redraw_experiment_a_figures.py
```

复现实验会生成 `results/` 和 `figures/`；如果只需要更新图，用第二条命令即可。
