# E2 Workspace

## 作用

这里是 `E2` 的协作入口，用于组织 ablation 结果，不复制 `THC/TSTC` 共享实现。

## 共享代码入口

- `artifacts/thc/src/run.py`
- `artifacts/TSTC/run_noise_sweep.py`

## 目录职责

- `logs/`：ablation 原始结果、noise sweep 输出
- `tables/`：样本数 / tolerance / runtime 候选表
- `figures/`：候选图
- `notes/`：一页说明、运行记录

## 常用入口

```bash
bash paper1_veriedge/E2/run_ablation.sh
bash paper1_veriedge/E2/run_noise_sweep.sh
```

## 正式文件命名

- `exp_e2_<date>_<owner>_samplesweep.csv`
- `exp_e2_<date>_<owner>_tolerancesweep.csv`
- `exp_e2_<date>_<owner>_runtime.csv`

## 不要做什么

- 不要只跑单个 sweep
- 不要只报 FPR，不报 TPR / runtime
- 不要把运行目录和最终候选表混成一层
