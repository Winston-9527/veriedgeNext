# E5 Workspace

## 作用

这里是 `E5` 的协作入口，用于把 orchestration 运行结果整理成正式 policy compare 表。

当前只建议保留 **measured-profile 20260511** 这轮结果：

- verification profile matrix：
  - `paper1_veriedge/E5/tables/exp_e5_20260511_verification_profile_matrix.csv`
- policy replay：
  - `paper1_veriedge/E5/logs/exp_e5_20260511_measured_profile_replay/exp_e5_20260511_measured_profile_mainline_policy_compare.csv`

旧的 `strict policy replay` 和 `semi-strict Section 6.1 replay` 现在应视为 **stale exploratory runs**：

- 可以保留作历史参考
- 不应继续作为最终论文主结果
- 原因是它们吃的是旧版 `E2/E4` verifier profile

## 共享代码入口

- `artifacts/inference-E2E/requester/matrix_control.py`
- `artifacts/inference-E2E/requester/make_comparison_table.py`
- `artifacts/equivalence/`

## 目录职责

- `logs/`：结构化原始结果、导出的 cell summary
- `tables/`：policy compare 正式表
- `figures/`：候选图
- `notes/`：一页说明、运行记录

批量运行目录默认放在：

- `workspace/runs/E5/`

## 常用入口

```bash
bash paper1_veriedge/E5/run_matrix.sh
bash paper1_veriedge/E5/build_policy_table.sh /path/to/summary_by_cell.csv
bash paper1_veriedge/E5/run_e5_policy_replay.sh
```

当前论文主线推荐优先使用：

- `run_e5_policy_replay.sh`

这条路径不依赖 `EXO` 在线调度，而是复用：

- `E1` 的真实 heterogeneity risk
- `E4` 的 verifier operational overhead
- requester 配置里的 network / node-count 基础路径信号

然后做 trace-driven policy replay / simulator。

严格版主线现在推荐使用：

- `run_e5_strict.sh`

这条路径显式复用：

- strict `E1` 的 global heterogeneity-risk proxy
- strict `E4` 的 global verifier overhead
- requester 配置里的 WAN/LAN 路径信号

并统一产出：

- `policy_compare.csv`
- `policy_config.json`

当前最终推荐主线改为：

- `build_verification_profile_matrix.py`
- `build_e5_measured_profile_inputs.py`
- `run_e5_measured_profile_replay.py`
- `plot_e5_measured_profile_results.py`

这条 measured-profile 主线会自动读取最新一轮：

- `E2 material tamper full matrix`
- `E4 equal-budget overhead`
- `E5 verification profile matrix`

并产出最新 `measured-profile` policy compare。
- workload-specific figures

## 正式文件命名

- `exp_e5_<date>_<owner>_policy_compare.csv`
- `exp_e5_<date>_<owner>_policy_config.json`

## 不要做什么

- 不要只报 latency，不报 success / challenge / verifier workload
- 不要把 welfare / pricing 结果当作 E5 主结果
- 不要把整个 batch run 目录直接当正式交付物
- 不要再把 `20260504` 的 strict / semistrict `E5` 当最终主结果
