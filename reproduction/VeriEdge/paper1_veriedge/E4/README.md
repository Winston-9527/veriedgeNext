# E4 Workspace

## 作用

这里是 `E4` 的正式交付入口，默认直接产出结构化 overhead 表。

当前 `E4` 主线不依赖 `EXO`，而是直接复用 `E1` 已完成的真实 heterogeneous paired captures，离线统计 verifier 的 operational overhead。

当前推荐保留两条结果线：

- `strict_ab_mainline`
  - 文件前缀：`exp_e4_20260511_strict_ab_mainline_*`
  - 用于 strict `E1 A/B` 的 `honest_trace / challenged_trace / tamper_trace`
- `equal_budget_live_ab`
  - 文件前缀：`exp_e4_20260511_equal_budget_live_ab_*`
  - 用于 `E5 measured-profile` 的 variant-overhead 输入

旧的 `20260504/20260506` 结果现在应视为 **stale reference**：

- 它们仍可参考大小和延迟量级
- 但 `tamper detection` 行为已不再匹配当前 `relative-std + per-prompt seed` 口径

## 共享代码入口

- `artifacts/thc/src/overhead_report.py`

## 目录职责

- `logs/`：脚本直接生成的结构化 CSV
- `tables/`：主稿候选表
- `figures/`：如需补图，放这里
- `notes/`：一页说明、运行记录

## 常用入口

```bash
bash paper1_veriedge/E4/run_overhead.sh --capture-root /path/to/capture_root --owner johnlee
bash paper1_veriedge/E4/run_e4_current_mixed.sh
bash paper1_veriedge/E4/run_e4_strict.sh
bash -lc 'python3 paper1_veriedge/E4/build_e4_equal_budget_overhead.py'
```

说明：

- `run_overhead.sh` 是薄封装，支持通过 `CONFIG_PATH=/abs/path/to/config.json` 覆盖默认配置
- `run_e4_current_mixed.sh` 是论文当前主线入口，固定复用 `E1 Current mixed stack 40/200`
- 当前主线默认先产出 `baseline/checkpoint-specific` 结果，并额外补一份 `global shared tolerance` 对照
- `run_e4_strict.sh` 是基于 strict `E1 A/B` traces 的严格版主线，覆盖 `honest trace / challenged trace / tamper trace`
- `build_e4_equal_budget_overhead.py` 产出 `scalar16 / scalar64 / projcos4 / projcos16` 的 equal-budget overhead 主表，供 `E5 measured-profile` 使用

## 正式文件命名

- `exp_e4_<date>_<owner>_size_breakdown.csv`
- `exp_e4_<date>_<owner>_latency_breakdown.csv`
- `exp_e4_<date>_<owner>_storage_breakdown.csv`
- `exp_e4_<date>_<owner>_summary.csv`

## 不要做什么

- 不要只写“大概多少”
- 不要不带单位
- 不要把估算值写成实测值
- 不要把 `EXO` control-plane 开销和 verifier overhead 混成一个口径
