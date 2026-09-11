# Reference-mode feasibility matrix

> Route B G0。四模式 × 状态来源 / 信任边界 / 成本 / 保证。每格事实或 `UNKNOWN`——不猜。
> 生成依据：`docs/ROUTE_B_G0_EXPERIMENT_HANDBOOK_2026-09-07.md` §3/§14；成本见 `configs/reference_modes.csv`（当前 `assumed`，待 E01/E02 实测回填）。

| mode | 状态来源 | 信任边界 | 固定成本 shape | 参考成本 | 主动保证 | E09 决策 |
|---|---|---|---|---|---|---|
| **V0_passive** | 无（只绑定输出/状态 + 回执） | 不引入参考方 | `c_always=0.03` | `c_ref=0`（无参考） | **无主动检测**（不得标成主动保证） | **NO_GO** |
| **L1_prefill_local** | prefill 分片本地重放参考 | 参考方在承诺披露集合内 | `c_always=0.05` | `c_ref=0.30`+`c_check=0.04` | 被审计时单次检测（受 `d` 限制） | **GO**（有可行 `p_a` 区间） |
| **L2_decode_local** | decode 本地重放参考（需可信 cache/KV） | 依赖可信 decode 状态（E03 未决） | `c_always=0.08` | `c_ref=0.45`+`c_check=0.04` | 被审计时单次检测 | **NO_GO**（成本 0.57 > cap 0.5，无可行区间） |
| **D0_duplicate** | always-on 完整复制（基线） | 复制方 = 执行方 | `c_duplicate_extra=1.0` | — | 完整复制的保证范围（与局部参考不同，不可混报） | **BASELINE** |

## 单位与保证对照（不可互换）

| 维度 | always-on duplicate | sampled local reference |
|---|---|---|
| 保证范围 | 全覆盖 | 仅被审计样本；`D_single=p_a·d`、`D_m=1-(1-p_a·d)^m` |
| 单次阻断 | 同步裁决可阻断 | 同步模式裁决后交付；**异步发现不能撤销已产生的损害** |
| 成本 | `C_base + C_duplicate_extra` | `E[C_verify]`（§成本公式） |
| 资源 | 峰值内存高（完整副本） | 峰值内存降（局部）；保留 byte-seconds 需单列 |

## UNKNOWN / BLOCKED 项（本环境无法测）

- **decode 状态充分性与来源**（E03）：`UNKNOWN`——需可运行模型 + decode-state 接口。这是 L2 是否可行的前置。
- **快照/保留/搬运实测**（E04）：`UNKNOWN`——本机测拷贝/存储；远端传输只作 `modeled`。
- **承诺+PACT 时序**（E05）：`UNKNOWN`——需公共信标/协议组件。
- **E01/E02 实测成本**：本文件成本为 `assumed`；**须用已完成 E01/E02 的 `measured` 值替换**后重跑 `simulate_reference_economics.py`。

## 披露约束（G0 §15 尾）

若参考计算需要把受限 prompt、激活或 KV 交给承诺披露集合之外的主体，即使成本低也**不是该部署的可行模式**。L1/L2 的参考方必须属于 `G^acc_j`。
