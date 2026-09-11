# support/ — 论文其他章节的支撑实验

E2-R（`../lib`, `../main`, `../validation`, `../figures`）之外的**检测器层支撑实验**，对应论文 §6.4 / §6.5 / §6.6 的扩展与机制部分。

> 与 E2-R 的分工：**support/ = 非自适应 material tamper + fixed-FPR 口径 + 机制分解 + scale**；**E2-R = 自适应对手 × 三检测器 + fresh 协议 + harm 验证**。

---

## 脚本

| 脚本 | 论文对应 | 结果 |
|---|---|---|
| `run_p0_main_table_720.py` | §6.6 material-tamper 扩展（**720 池**，A=MPS bf16 / B=CUDA fp32）| `results/p0_main_table_720.csv` |
| `run_p0_main_table.py` | §6.4/§6.6 早期版（40/200）| `results/p0_main_table.csv` |
| `run_fixed_fpr_comparison.py` | §6.5 **fixed-FPR 公平比较**（统一 1% FPR 的 TPR + AUROC）| `results/fixed_fpr_comparison.csv`, `results/fixed_fpr_auroc.csv` |
| `run_p1_radial_angular.py` / `_v2.py` / `_v3.py` | §6.6 机制分解（radial/angular，支撑 SignRadial vs ProjCos 理论）| `results/p1_radial_angular*.csv/.png` |
| `run_p2_scale_sweep.py` | §6.6 scale perturbation 盲点 | `results/p2_scale_sweep.csv/.png` |
| `srr.py` / `radial.py` / `attacks.py` | 共享核心库（SRR 配置 / SignRadial / 攻击注入）| — |

## 说明

- **自洽依赖簇**：脚本互相 `flat import`（如 `run_p1_radial_angular_v3` → `run_p0_main_table_720`，`attacks` → `srr`），故**整体同目录**，运行时 `sys.path[0]=support/` 自动解析，无需额外 `sys.path`。
- **结果路径**：脚本用 `Path(__file__).parent / "results"`，故结果落在 `support/results/`。
- **数据依赖**：`run_p0_main_table_720.py` 等读 `workspace/captures_720/` + prompt split（与 E2-R 同一 720 池）。

## 运行

```bash
cd support
python3 run_p0_main_table_720.py     # → results/p0_main_table_720.csv
python3 run_fixed_fpr_comparison.py  # → results/fixed_fpr_comparison.csv, fixed_fpr_auroc.csv
python3 run_p1_radial_angular_v3.py  # → results/p1_radial_angular_v3.csv/.png
python3 run_p2_scale_sweep.py        # → results/p2_scale_sweep.csv/.png
```

## docs/

| 文件 | 内容 |
|---|---|
| `P0_MAIN_TABLE_720_MEMO.md` | 720 池主表结论（Combined FPR~1% & TPR=1.0）|
| `P0_MAIN_TABLE_MEMO.md` | 早期 40/200 主表 |
| `FIXED_FPR_COMPARISON_MEMO.md` | fixed-FPR 公平比较（v2，含"假盲点"证伪）|
| `P1_RADIAL_ANGULAR_MEMO.md` / `_V3_MEMO.md` | radial/angular 机制 |
| `P2_SCALE_SWEEP_MEMO.md` | scale sweep |
