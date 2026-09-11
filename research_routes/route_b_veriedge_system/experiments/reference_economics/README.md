# reference_economics — G0 E09 risk-cost scan

Route B 参考执行经济性（G0 手册 E00–E10）的实现与交付目录。承接已完成的 E01/E02，补齐 **E09 风险—成本联合扫描**（= 原 WP0 核心）。

## 结构

```
reference_economics/
  README.md
  configs/                       # 预注册
    preregistration.json           run_id / seed / 扫描网格
    reference_modes.csv            四模式 × 固定/参考/检查/升级成本
    risk_targets.json              单次/持续风险目标、成本上限、披露约束
  adapters/                      # 模型分片 + snapshot/restore 接口（仅接口，无实现）
  experiments/                   # E01–E10 入口/指针
  simulate_reference_economics.py  # E09 核心（配置驱动、固定种子）
  tests/                         # 公式边界 + 自检
  results/<run_id>/              # environment/input_manifest/risk_curves/cost_grid/
                                 # feasible_regions/sensitivity/protocol_checks/go_nogo_summary
  REFERENCE_MODE_FEASIBILITY.md  # 四模式 × 状态/信任/成本矩阵
  WP0_REFERENCE_ECONOMICS_MEMO.md
```

## 运行

```bash
cd experiments/reference_economics
python3 simulate_reference_economics.py            # → results/<run_id>/
python3 -m pytest tests/ -q                        # 公式边界 + 自检
```

## 风险模型（G0 §14.1）

```
D_single = p_a * d
D_m      = 1 - (1 - p_a*d)^m
p_a ≥ r/d                    （单次目标 r，仅当 r ≤ d）
p_a ≥ (1-(1-r)^(1/m))/d      （持续目标 r，仅当可达）
```

## 成本模型（G0 §3.3，归一化 C_duplicate_extra = 1.0）

```
E[C_verify] = c_always + p_a*(c_ref + c_check) + p_a*u*c_upgrade_extra
```

## 最低自检（G0 §14.4，由 `simulate_reference_economics.py` 强制）

`p_a=0`→主动检测=0 且参考=0 但 `C_always≠0`；`p_a=1,d=1`→单次检测=1；`d/m/p_a` 增大→累计发现概率不降；u 条件/总体记法同价；`p_a=0`→无审计内升级；V0 不提供主动保证；missing 记 NaN 不记 0。**任一失败即非零退出**，不写 summary。

## 证据纪律

- 成本输入标 `source_type`：`measured`/`derived`/`assumed`/`legacy_measured`。当前为 `assumed`，**须由 E01/E02 实测值替换**。
- `d` 是条件检测率，**不是语义检测保证**。
- 远端传输只作 `modeled` 参数，不用 loopback 当 WAN。
