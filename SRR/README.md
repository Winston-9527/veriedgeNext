# E2-R 实验代码

**统一协议下的自适应对手 × 三检测器**（SignRadial / ProjCos4 / Combined）。
支撑论文贡献点 3 “bounded arbitration”；结果与结论见 `docs/E2R_RESULT_MEMO.md`，审计见 `docs/E2R_AUDIT.md`。

---

## 目录结构

```
lib/                 共享协议定义（被所有实验复用）
  e2r_common.py        数据加载 / per-boundary & trace-max score / 阈值校准 / ECDF fusion
  e2r_attacks.py       6 族攻击构造（sign_balanced / null_space / joint_null / tol_hug×3）
main/                主实验（需 CUDA）
  run_e2r_main.py      216 条件 × 520 eval → per-prompt detail
  run_e2r_assemble.py  聚合 → 主矩阵 CSV / 盲点表 / manifest
validation/          验证臂
  run_e2r_harm_decode.py        32-token 解码验证（fixed 协议，梯度 g）
  run_e2r_fresh.py              fresh 协议 vs fixed（TPR/FPR，纯 numpy）
  run_e2r_fresh_harm_decode.py  fresh 协议 + 梯度 g + 输出验证（需 CUDA）
figures/
  run_e2r_figs.py      论文图：盲点热图 / 强度谱 / harm 证据 / fresh-vs-fixed
support/             论文其他章节支撑（§6.4/§6.5/§6.6 的非自适应 + 机制 + scale）
  srr.py, radial.py, attacks.py   支撑实验核心库
  run_p0_main_table_720.py        §6.6 material-tamper 扩展（720 池）
  run_fixed_fpr_comparison.py     §6.5 fixed-FPR 公平比较
  run_p1_radial_angular*.py       §6.6 radial/angular 机制
  run_p2_scale_sweep.py           §6.6 scale 盲点
  results/  docs/                 支撑结果与 memo
results/             实验结果（按实验分子目录，见下）
docs/                设计 / memo / 审计 / 相关手册
archive/             剩余历史探索脚本（P4/P5 等，保留归档）
```

---

## 环境

| 依赖 | 用途 |
|---|---|
| `numpy` | 全部脚本 |
| `torch` + `transformers` | `main/` 与 `validation/*harm_decode*`（模型 replay / 梯度 / 生成）|
| `matplotlib` | `figures/` |

- 纯 numpy 脚本（`assemble` / `fresh` / `figs`）可在任意机器跑。
- CUDA 脚本需 GPU（本项目用 RTX 6000D，fp32）。

## 数据

| 数据 | 路径（示例）|
|---|---|
| 720 池激活捕获 | `workspace/captures_720/{stack_a_720, stack_b_720}/captures/*.npz` |
| prompt split | `workspace/AdversarialEvaluation/data/qwen_prompt_splits_stratified_v2_200_500.jsonl`（sha256 见 manifest）|
| 模型 | `Qwen/Qwen3-0.6B`（HF cache）|

数据指纹（池大小、prompt sha256、token 统计）记录在 `results/e2r/e2r_manifest.json`。

---

## 复现流程

> **路径约定**：所有命令**从本目录（`SRR/`）运行**；`--out` 指向 `results/` 下的目录
> （脚本用 `OUT.parent` 定位并列的兄弟目录，如 `results/e2r_harm_decode/`）。

```bash
# ── 1. 主实验（CUDA）────────────────────────────────
python3 main/run_e2r_main.py \
    --root  <captures_720> --prompts <prompts.jsonl> \
    --out   results/e2r --harm-dir gradient
python3 main/run_e2r_assemble.py --out results/e2r
#   → results/e2r/{e2r_main_matrix.csv, e2r_blindspot_table.md, e2r_manifest.json}

# ── 2. 验证臂 ───────────────────────────────────────
# 2a. fixed 协议解码验证（CUDA）
python3 validation/run_e2r_harm_decode.py \
    --root <captures_720> --prompts <prompts.jsonl> --out results/e2r_harm_decode --rho 0.01
# 2b. fresh 协议 TPR/FPR（纯 numpy）
python3 validation/run_e2r_fresh.py \
    --root <captures_720> --prompts <prompts.jsonl> --out results/e2r_fresh
# 2c. fresh 协议 harm 验证（CUDA）
python3 validation/run_e2r_fresh_harm_decode.py \
    --root <captures_720> --prompts <prompts.jsonl> --out results/e2r_fresh_harm --rho 0.01

# ── 3. 论文图（纯 numpy）────────────────────────────
python3 figures/run_e2r_figs.py --out results/e2r
```

### 验收

- `assemble` 输出的实测 FPR 与 manifest 一致（SR/PC 1.15%、Combined 1.35%）；
- `e2r_manifest.json` 的 `script_hashes` 与磁盘脚本 SHA256[:12] 逐一匹配。

---

## results/ 布局

| 目录 | 内容 |
|---|---|
| `e2r/` | 主实验：主矩阵、per-prompt detail、manifest、盲点表、4 张论文图 |
| `e2r_knownP/` | TM1b 臂（P 公开、Ω 猜测）|
| `e2r_robust_gs12345/` `e2r_robust_gs777/` | TM-1 多猜测 seed 稳健臂（TM-1 only）|
| `e2r_fresh/` | fresh 协议 vs fixed（TPR/FPR）|
| `e2r_harm_decode/` | fixed 协议 32-token 解码验证 |
| `e2r_fresh_harm/` | fresh 协议 + 梯度 g 输出验证 |

> 兄弟目录（`e2r_harm_decode/`、`e2r_fresh/` 等）与 `e2r/` **并列**于 `results/` 下——脚本按此约定用 `OUT.parent` 查找。

---

## 文档

| 文件 | 内容 |
|---|---|
| `docs/E2R_EXPERIMENT_DESIGN.md` | 实验设计（协议、攻击族数学、指标、决策点）|
| `docs/E2R_RESULT_MEMO.md` | 结果 memo（三问 Q1/Q2/Q3 + fresh 协议 + harm 验证）|
| `docs/E2R_AUDIT.md` | 六轮审计（含威胁模型拍板、FPR 修复、fresh 协议验证）|

---

## archive/

早期探索脚本（`p1a/p1b/p2a/p2b/p4b/p4c/p5c` 系列、`srr.py`/`radial.py`/`baselines.py`/`attacks.py` 等）。
它们**互相之间**用同目录 flat import；整体归档保持可运行，但不属于论文 E2-R 交付。若论文其他章节（如 verifier profiles）需要，再单独映射。
