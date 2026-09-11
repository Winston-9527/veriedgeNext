# E1 Workspace

## 作用

这里是 `E1` 的协作入口，不复制共享 verifier 代码。

## 共享代码入口

- `artifacts/thc/scripts/t3_hetero_cli.py`
- `artifacts/thc/T3_hetero_runbook.md`
- `artifacts/thc/src/e1_pairwise_report.py`

## 目录职责

- `logs/`：pairwise 结果表、结构化原始结果
- `tables/`：可直接进主稿的汇总表
- `figures/`：候选图
- `notes/`：一页说明、运行记录

真实 capture root 默认放在：

- `workspace/captures/E1/`

## 常用入口

默认使用仓库级虚拟环境：

- 优先走 `./.venv/bin/python3`
- 如 `.venv` 不存在，入口脚本会通过 `artifacts/thc/scripts/common.sh` 自动自举
- 不建议直接使用全局 `python3`
- 如已安装 `uv`，优先执行 `uv sync --group e1`

```bash
bash paper1_veriedge/E1/run_capture.sh --split calibration
bash paper1_veriedge/E1/export_pairwise.sh --pair "pair_label::/path/to/left_root::/path/to/right_root" --delta-map-file /path/to/delta_map.json
```

如果要按锁文件重建 `E1` 环境：

```bash
uv sync --group e1
```

Linux `C2` 若启用 `bitsandbytes_8bit`，额外执行：

```bash
uv sync --group e1 --group e1-linux-cuda
```

## 本地 MPS Smoke

本地 `M5 Pro/MPS` smoke 已验证可行，推荐直接复用这两份配置：

- `workspace/local_smoke_cluster_mps.json`
- `workspace/local_smoke_qwen_mps.json`

当前经过实机验证的关键约束：

- `C1` 使用 `device=mps` + `quantization=metal_8bit`
- `C2/C3` 使用 `device=mps` + `quantization=none` + `torch_dtype=float16`
- 当前本地可用组合为 `torch==2.10.0`

典型结果产物：

- `workspace/captures/E1/local_mps_smoke_*`
- `paper1_veriedge/E1/logs/local_mps_smoke/`

## 真实 E1 模板

真实多机 `E1` 可以从这两份模板开始：

- `artifacts/thc/config/e1_real_cluster_template.json`
- `artifacts/thc/config/e1_real_pairs_template.json`

推荐把三台机器分别映射为：

- `C1`: Apple Silicon + `mps` + `metal_8bit`
- `C2`: Linux CUDA + `bitsandbytes_8bit`
- `C3`: Apple Silicon + `mps` + `float16`

仓库里也已经给出当前三机的直接执行入口：

- `artifacts/thc/config/hetero_qwen_cluster.json`
- `paper1_veriedge/E1/real_e1.sh`
- `paper1_veriedge/E1/start_server_jlmini_3.sh`
- `paper1_veriedge/E1/start_server_linux124.sh`
- `paper1_veriedge/E1/start_server_jlmini_2.sh`

## 正式文件命名

- `exp_e1_<date>_<owner>_summary.csv`
- `exp_e1_<date>_<owner>_pairwise_details.csv`

## 不要做什么

- 不要把 `.npz` capture bundle 直接提交到 `paper1_veriedge/E1/logs/`
- 不要混用 calibration 与 evaluation
- 不要修改 shard plan 却不写进 notes
