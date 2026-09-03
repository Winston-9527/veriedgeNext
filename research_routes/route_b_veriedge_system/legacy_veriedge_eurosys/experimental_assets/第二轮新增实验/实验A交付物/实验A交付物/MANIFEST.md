# 实验A交付物 Manifest

## 主阅读文件

| 文件 | 说明 |
|---|---|
| `README.md` | 交付包入口与快速结论 |
| `ExperimentA_A1_A3_results.md` | 主结果记录与解读，推荐打开 |
| `docs/实验A_A1_A3结果记录与解读.md` | 中文文件名副本，内容与主文档一致 |

## 输入数据

| 文件 | 说明 |
|---|---|
| `data/profile_matrix.csv` | measured verifier profile matrix |
| `data/candidate_placements.csv` | replay candidate placement 列表 |
| `data/workload.csv` | single / queued-8 workload |
| `data/DATA_INDEX.md` | 输入数据索引 |

## 实验结果

| 文件 | 说明 |
|---|---|
| `results/placement_runs.csv` | per-task replay 明细 |
| `results/placement_summary.csv` | 主汇总表 |
| `results/placement_summary_by_seed.csv` | seed-level 汇总 |
| `results/RESULT_INDEX.md` | 结果表索引 |

## 图像

| 文件 | 说明 |
|---|---|
| `figures/fig_placement_frontier_a1.png` / `.pdf` | Figure A1a：A1 controlled replay frontier |
| `figures/fig_placement_frontier_a3_queue.png` / `.pdf` | Figure A1b：A3 queue-aware frontier |
| `figures/fig_risk_class_composition.png` / `.pdf` | Figure A2：risk-class composition |
| `figures/fig_alpha_sensitivity_infeasible.png` / `.pdf` | Figure A3：alpha sensitivity |
| `figures/FIGURE_INDEX.md` | 图像索引与用途说明 |

## 复现脚本

| 文件 | 说明 |
|---|---|
| `scripts/run_experiment_a_full.py` | 全量 A1/A3 replay 脚本 |
| `scripts/redraw_experiment_a_figures.py` | 只重画交付版图像 |

## 论文回填材料

| 文件 | 说明 |
|---|---|
| `paper_snippets/abstract_numbers.txt` | abstract / intro 可用数字 |
| `paper_snippets/figure_captions.txt` | figure captions |
| `paper_snippets/placement_eval_subsection.tex` | 论文 subsection 草稿 |
| `paper_snippets/PAPER_SNIPPETS_INDEX.md` | 论文片段索引 |

## 元数据

| 文件 | 说明 |
|---|---|
| `metadata/environment.md` | 运行环境 |
| `metadata/git_commit.txt` | git commit 信息 |
| `metadata/network_config.md` | 网络配置说明 |
