# WP0 reference-economics memo (E09 单机风险—成本扫描)

> Route B G0 总 memo。回答：**是否存在 `p_a` 区间，使抽样参考的成本明显低于 always-on duplicate，同时满足预声明单次风险目标？**
> run_id：`e09_20260911`；结果目录：`results/e09_20260911/`。

## 1. 预注册目标

- 单次检测目标（primary）：**0.99**（design scan：0.90/0.95/0.99，见 `configs/risk_targets.json`）。
- 持续检测目标（primary）：**0.99**，`m ∈ {1,5,10,50,100}`。
- 新增成本相对复制上限：**`C_verify / C_duplicate_extra ≤ 0.5`**。
- 披露约束：参考不得把受限 prompt/激活/KV 交给承诺披露集合之外的主体。

## 2. 输入与证据来源

| 输入 | 值 | source_type |
|---|---|---|
| `C_duplicate_extra`（归一化锚点） | 1.0 | assumed |
| V0/L1/L2 的 `c_always/c_ref/c_check/c_upgrade` | 见 `configs/reference_modes.csv` | **assumed**（待 E01/E02 实测替换） |
| 扫描网格 | `p_a`/`m`/`d`/`u` 见 `configs/preregistration.json` | G0 §14.2 |
| `d` 语义 | 条件检测率，非语义保证 | G0 §14.1 |

## 3. 步骤与命令

```bash
cd experiments/reference_economics
python3 simulate_reference_economics.py     # 自检 + 扫描 → results/e09_20260911/
python3 -m pytest tests/ -q                 # 8 passed
```

## 4. 完整结果（单机可证明范围）

**决策（`go_nogo_summary.json`）**：

| mode | 决策 | 依据 |
|---|---|---|
| V0_passive | **NO_GO** | 无主动检测（不得标成主动保证） |
| L1_prefill_local | **GO** | 存在 `p_a` 使风险达标且成本 ≤ 0.5 |
| L2_decode_local | **NO_GO** | `p_a=1` 时成本 0.57 > 0.5；无可行区间（且 E03 状态来源未决） |
| D0_duplicate | **BASELINE** | 成本比分母 |

**风险—成本交集**：`feasible_regions.csv`，逐 `(mode, d, u)` 给可行 `p_a` 集合与 `n_feasible`。`p_a_min_for_risk = r/d`（r=0.99）；`r > d` 时 `infeasible`。
**成本网格**：`cost_grid.csv`（`E[C_verify]` 随 `p_a/u`）。
**敏感性**：`sensitivity.csv`（target∈{0.90,0.95,0.99} × d）。
**自检**：`protocol_checks.json` — 9 项全过（见 §6）。

## 5. 固定/条件成本分解

- **固定（所有任务必付）**：`c_always`（绑定输出/输入/状态 + 回执 + 审计决定前保留）。
- **条件（被审计才付）**：`p_a·(c_ref + c_check)`；升级 `p_a·u·c_upgrade`（只在已付参考成本后的增量，避免与完整重放重复计账）。
- **复制基线**：`c_duplicate_extra = 1.0`（完整副本）。

## 6. 最低自检（G0 §14.4，全过）

`p_a=0`→主动检测=0 且参考=0 但 `C_always≠0`；`p_a=1,d=1`→单次检测=1；`d/m/p_a` 增大→累计发现概率不降；抽样参考需求随 `p_a` 不降；u 条件/总体记法同价；`p_a=0`→无审计内升级；V0 无主动保证；missing 记 NaN 不记 0。

## 7. 未知项与远端待测（上限需由 G1 回填）

- **E01/E02 实测成本**：替换 `assumed` 值后重跑（当前结论对成本输入敏感）。
- **E03 decode 状态来源**：决定 L2 是否可能可行；恶意 KV 负例必须做。
- **E04 保留/搬运**：远端传输 `modeled`；给出"状态搬运 < X ms 才可行"的 X 上限。
- **E05 承诺+PACT 时序**：审计随机量与投影 seed 分域；超时须 ABORT/升级。
- **G1 需替换的 d/u**：`d` 用条件检测下界、`u` 用诚实/攻击分开的升级率。

## 8. 结论与允许的论文表述

- **允许**：在 `assumed` 成本与给定 `d` 下，**L1 prefill 局部参考存在 `p_a` 区间使成本 ≤ 0.5×复制且满足单次 0.99 目标**（单机数学结论）。
- **不允许**：宣称 decode（L2）可行；宣称 V0 提供主动正确性保证；把 `assumed` 成本当作实测；把 `d` 当作语义检测保证；用异步发现宣称为"阻断单次有害输出"。

## 9. 下一项最小实验

接入 **E01/E02 的 `measured` 成本**（替换 `configs/reference_modes.csv` 的 `assumed` 值）→ 重跑 E09；并行推进 **E03**（decode 状态来源）以判定 L2 的 Go/No-Go。
