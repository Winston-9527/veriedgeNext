# Data Index

## Workbook Required Inputs

| 文件 | 说明 |
|---|---|
| `profile_matrix.csv` | measured verifier profile matrix，包含 FPR/TPR、bytes、latency、risk class 等字段。 |
| `candidate_placements.csv` | replay candidate placement pool，包含 group size、pair ids、network/execution latency、availability/reputation 等字段。 |
| `workload.csv` | replay workload，包含 `single` 与 `queued-8` 两类任务流。 |

## 使用方式

- `scripts/run_experiment_a_full.py` 读取这三份输入生成 `results/`。
- `scripts/redraw_experiment_a_figures.py` 读取 `results/placement_summary.csv` 重画 `figures/`。

## 注意

`candidate_placements.csv` 中的 `E/F`、`A/B` 等是 pair/profile label，不表示只使用两台机器执行；controlled replay 中 heterogeneous candidates 仍按 `group_size=3` 组织。
