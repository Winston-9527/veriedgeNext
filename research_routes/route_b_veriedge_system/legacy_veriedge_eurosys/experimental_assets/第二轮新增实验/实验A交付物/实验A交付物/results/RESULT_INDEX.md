# Result Table Index

## 主表

| 文件 | 用途 |
|---|---|
| `placement_summary.csv` | 主汇总表。按 `workload + alpha + policy` 聚合 latency、goodput、false risk、infeasible rate、admission rate。论文主数字优先从这里引用。 |

## 辅助表

| 文件 | 用途 |
|---|---|
| `placement_runs.csv` | per-task 明细。用于审计每个 seed、task、policy 的 placement 选择与风险判断。 |
| `placement_summary_by_seed.csv` | seed-level 汇总。用于检查 random / replay seed 是否影响结论。 |

## 主结果切片

论文主结果建议使用：

- `workload = queued-8`
- `alpha = 0.10`
- `beta = 0.90`

关键对照：

- `network_aware_projcos4` vs `verif_constrained_projcos4`
- `queue_aware_network` vs `queue_aware_verif_constrained`
- `network_aware_adaptive` / `queue_aware_adaptive` 作为 adaptive sketch selection 对照
