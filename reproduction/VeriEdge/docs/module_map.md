# Module Map

## 视图约定

- 实验协作入口在 `paper1_veriedge/E1~E5/`
- 共享代码入口在 `artifacts/`
- 重型运行产物优先留在 `workspace/`

## E1

主用模块：

- `artifacts/thc/scripts/t3_hetero_cli.py`
- `artifacts/thc/scripts/run_t3_hetero_capture.sh`
- `artifacts/thc/src/hetero_qwen_capture.py`
- `artifacts/thc/src/checkpoint_qwen.py`
- `artifacts/thc/src/calibrate_delta.py`
- `artifacts/thc/src/e1_pairwise_report.py`

实验入口：

- `paper1_veriedge/E1/README.md`
- `paper1_veriedge/E1/run_capture.sh`
- `paper1_veriedge/E1/export_pairwise.sh`

正式交付位置：

- `paper1_veriedge/E1/logs/`
- `paper1_veriedge/E1/tables/`
- `paper1_veriedge/E1/figures/`
- `paper1_veriedge/E1/notes/`

## E2

主用模块：

- `artifacts/thc/src/run.py`
- `artifacts/thc/src/pipeline_qwen.py`
- `artifacts/TSTC/run_noise_sweep.py`
- `artifacts/TSTC/make_publication_figures.py`

实验入口：

- `paper1_veriedge/E2/README.md`
- `paper1_veriedge/E2/run_ablation.sh`
- `paper1_veriedge/E2/run_noise_sweep.sh`

正式交付位置：

- `paper1_veriedge/E2/logs/`
- `paper1_veriedge/E2/tables/`
- `paper1_veriedge/E2/figures/`
- `paper1_veriedge/E2/notes/`

## E4

主用模块：

- `artifacts/thc/src/overhead_report.py`
- `artifacts/thc/src/hash_chain.py`
- `artifacts/thc/src/checkpoint_qwen.py`

实验入口：

- `paper1_veriedge/E4/README.md`
- `paper1_veriedge/E4/run_overhead.sh`

正式交付位置：

- `paper1_veriedge/E4/logs/`
- `paper1_veriedge/E4/tables/`
- `paper1_veriedge/E4/figures/`
- `paper1_veriedge/E4/notes/`

## E5

主用模块：

- `artifacts/inference-E2E/requester/runner.py`
- `artifacts/inference-E2E/requester/matrix_control.py`
- `artifacts/inference-E2E/requester/make_comparison_table.py`
- `artifacts/inference-E2E/requester/make_order_robust_summary.py`
- `artifacts/equivalence/`

实验入口：

- `paper1_veriedge/E5/README.md`
- `paper1_veriedge/E5/run_matrix.sh`
- `paper1_veriedge/E5/build_policy_table.sh`

正式交付位置：

- `paper1_veriedge/E5/logs/`
- `paper1_veriedge/E5/tables/`
- `paper1_veriedge/E5/figures/`
- `paper1_veriedge/E5/notes/`

## E2-R（检测器层扩展，论文 §6.6）

> 自适应对手 × 三检测器（SignRadial / ProjCos4 / Combined）的检测器层实验，独立于本实验库（自成 720 池协议）。代码不在本仓库，位于论文工作区 `workspace/SRR/`。

主用模块（外部）：

- `workspace/SRR/lib/{e2r_common,e2r_attacks}.py`（E2-R 核心）
- `workspace/SRR/{main,validation,figures}/`（主实验 / 验证臂 / 论文图）
- `workspace/SRR/support/`（§6.4/§6.5/§6.6 检测器层支撑：p0 主表 / fixed-FPR / 机制 / scale）

论文产出：§6.6 新增（盲点表 + 强度谱 + harm + fresh 图）。与 E2 的分工见论文工作区 `docs/PAPER_EXPERIMENTS_CODE_ORGANIZATION.md` §1。
