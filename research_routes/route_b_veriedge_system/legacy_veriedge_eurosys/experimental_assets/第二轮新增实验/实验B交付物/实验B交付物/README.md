# 实验B交付物：Selective Delivery Group-Size Sweep

本目录汇总 `veriedge_revision_workbook.md` 中实验 B 的全部交付内容，包括主实验 LAN/WAN calibrated delivery sweep、live-store fresh-object 补充实验、图像、数据、表格、脚本、元数据和结果解读文档。

## 目录结构

| 子目录 | 内容 |
|---|---|
| `数据/` | 每次 run 的原始明细数据 |
| `表格/` | summary 表格，可直接用于论文/报告 |
| `图像/` | PNG/PDF 图，包括 latency、egress、live-store supplement |
| `文档/` | 实验报告、交付手册、论文片段、图注和结果解读 |
| `脚本与元数据/` | 复现实验脚本、网络配置、运行环境、git commit 信息 |

## 核心结论

Experiment B 已达到手册要求。主实验完成了 `100MB × k={1,2,4,8} × LAN/WAN × RPD/PPD × 30 runs`，证明 RPD requester egress 近似 `O(kS)`，PPD requester egress 近似 `O(S + kε)`。在 `k=8` 时，PPD 相比 RPD 将 requester egress 降低 87.5%；在 calibrated LAN profile 下 median all-providers-ready latency 降低 74.8%，在 calibrated WAN profile 下降低 81.1%。

live-store 补充实验完成了 `100MB × k={1,2,4,8} × RPD/PPD × 30 runs`，用于严格补齐 fresh payload / unique object ID / provider fetch verification 要求。该实验中 240 个 run 全部成功，240 个 SHA-256 content hash 全部唯一，object key 均为真实 ciphertext 的 content hash。

## 推荐阅读顺序

1. `文档/ExperimentB_selective_delivery_交付手册.md`：完整交付说明和结果解读。
2. `文档/ExperimentB_delivery_sweep_report.md`：主实验 LAN/WAN calibrated sweep 报告。
3. `文档/ExperimentB_live_store_supplement_report.md`：fresh object / content-hash 补充实验报告。
4. `表格/主实验_delivery_summary.csv`：论文主结果表。
5. `图像/fig_delivery_egress_group_size.png`：最核心的 `O(kS)` vs `O(S+kε)` 证据图。

## 关键文件

| 类型 | 文件 |
|---|---|
| 主实验原始数据 | `数据/主实验_delivery_runs.csv` |
| 补充实验原始数据 | `数据/补充实验_live_store_runs.csv` |
| 主实验汇总表 | `表格/主实验_delivery_summary.csv` |
| 补充实验汇总表 | `表格/补充实验_live_store_summary.csv` |
| LAN latency 图 | `图像/fig_delivery_latency_lan.png`, `图像/fig_delivery_latency_lan.pdf` |
| WAN latency 图 | `图像/fig_delivery_latency_wan.png`, `图像/fig_delivery_latency_wan.pdf` |
| requester egress 图 | `图像/fig_delivery_egress_group_size.png`, `图像/fig_delivery_egress_group_size.pdf` |
| live-store 补充图 | `图像/fig_delivery_live_store_latency_egress.png`, `图像/fig_delivery_live_store_latency_egress.pdf` |
| 主实验脚本 | `脚本与元数据/run_experiment_b_delivery_sweep.py` |
| 补充实验脚本 | `脚本与元数据/run_experiment_b_delivery_sweep_live_store.py` |

## 写作边界

实验 B 支持的论文 claim 是：placement commitment 定义 task-access material 的 disclosure boundary；当 selected group size 增大时，PPD 将 requester-side repeated full-payload transfers 替换为 one ciphertext publication + small per-provider access packages。

不要把结果表述为“PPD 在所有环境下总是 latency 最低”或“PPD 总网络流量总是最低”。更严谨的表达是：PPD 降低 requester-side disclosure cost，并在 LAN/WAN calibrated delivery profile 中随 placement width 增大表现出更好的 latency scalability。
