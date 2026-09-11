# experiments/ — E01–E10 入口索引

G0 手册的实验入口。**这里只做索引/指针**；实际脚本在各自目录，或标记为未完成/UNKNOWN。

| E | 内容 | 状态 | 入口 / 位置 |
|---|---|---|---|
| E00 | 环境、资产与目标冻结 | 部分（720 池已核实）| `../../shared/accountedge_runtime_and_captures/scripts/validate_raw_captures_720.py` |
| E01 | 完整执行与完整重放基线 | **已完成**（学生）| `../pact_offline/`（成本数字待回填本目录） |
| E02 | prefill 局部分片重放 | **已完成**（学生）| `../pact_offline/` |
| E03 | decode 状态充分性/来源 | **UNKNOWN**（无运行模型/状态接口）| 需 `../reference_economics/adapters/` 实现 |
| E04 | 快照/保留/搬运 | **UNKNOWN** | 同上 |
| E05 | 承诺 + PACT 组件成本与时序 | **UNKNOWN** | 同上 |
| E06 | 冗余分片对照 | 未开始 | — |
| E07 | 可信服务与 TEE 路线 | 未开始（无硬件填 UNKNOWN）| — |
| E08 | 抽样参考排队/批处理 | 未开始 | — |
| **E09** | **风险—成本联合扫描** | **本次完成** | `../simulate_reference_economics.py` → `../results/e09_20260911/` |
| E10 | 最终压力场景与决定 | 部分（见 WP0 memo §7）| 依赖 E03/E04 |

## E09 交付（本次）

`../simulate_reference_economics.py` + `../configs/` + `../results/e09_20260911/` + `../WP0_REFERENCE_ECONOMICS_MEMO.md`。

## 纪律（学生手册 §16 红线，适用全部 E）

1. calibration / attack optimization / final test 三个 seed domain 隔离。
2. 每个数字标 `source_type`；缺值不填 0。
3. 只回答可证伪问题；负结果保留。
4. `INCONCLUSIVE` 不进/不丢分母、不静默记 PASS。
5. 图可由同目录 CSV 一键重建。
6. 卡点写合格 blocker 报告。
