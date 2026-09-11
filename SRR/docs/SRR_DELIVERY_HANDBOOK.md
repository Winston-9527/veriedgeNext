# SRR-64 快速裁决实验 — 交付手册

**实验日期**：2026-08-06
**实验目录**：`workspace/SRR/`
**裁决**：**NO-GO（SRR 未修复 projcos 的 scale 盲点，不建议替换 projcos）**

---

## 1. 结论（TL;DR）

**SRR（Sampled Relative Residual Energy）作为 projcos 的替代方案，在本实验的数据上不成立。**

核心事实：在 A/B、A/C、A/D 三个配对上，SRR-32/64/128 的 **scale-attack TPR = 0.000**（与 projcos 一样盲，完全没修复 projcos 的 scale 盲点）；只在 B/D（无 Metal-int8 量化 C1 的干净配对）上达到 1.000。而 **projscalar1_abs 在全部 4 对上都达到 scale TPR=1.000 且 honest FPR ≤ 0.005**——它才是真正"同时捕获方向和尺度、且低误报"的轻量方案。

**根因（fundamental，非实现 bug）**：SRR 重新引入 norm/尺度信息，但 honest 异构漂移（尤其 A/B、A/C、A/D 的 C1 是 Metal-int8 量化路径）本身就包含巨大的尺度/幅值漂移。实测 honest 漂移的 SRR 值高达 **2.0**，而 1.10× scale 攻击只有 **0.01**——两者在 SRR 数值上完全重叠。为了把 honest FPR 压到 ≤0.10，校准的 gamma 必然吞掉 scale 攻击信号。**这正是 projcos 丢弃 norm 信息的原因——norm 是 honest 漂移的载体。**

---

## 2. 数据源（全部真实 paired capture，非合成扰动）

| 对 | 来源 | calib | eval | 说明 |
|---|---|---|---|---|
| A/B | `sanity_20260728_m4_m4_rtx3090` | 40 | 200 | **真实 M4**，C1=Metal-int8/FP16，C2=BF16，C3=RTX FP32 |
| A/C | `sanity_20260727` prime | 40 | 200 | M5 Pro 替代 C1（非原 M4），见 §8 边界 |
| A/D | `sanity_20260727` prime | 40 | 200 | 同上 |
| B/D | `sanity_20260727` prime | 40 | 200 | 同上 |

**诚实完整性校验**：A/B 的 `stack_b_eval` vs `stack_b_eval_rerun` **200/200 条 prompt 逐 bit 一致**（honest-homo 控制路径成立，验证了 capture 质量）。

---

## 3. 协议

- **基线实现**：直接复用论文 ground-truth 的 `frozen_snapshot/artifacts/thc/src/hash_chain.py`（`projection_seed=911`）。
- **操作点选择**：在 40 条 calib 上遍历 `percentile × mode(ckpt/global) × scale` 网格，选 honest FPR ≤ 0.10 优先、再最小 FPR；在 200 条 held-out 上评估。
- **基线复现 sanity**：A/B 上逐 cell 复现论文表 3/4 —— scalar16=0.15、scalar64=0.415、projscalar1_abs=0.00、projcos4=0.02、projcos8=0.08、projcos16=0.12。**协议可信**。
- **攻击族**（注入 C2，ref=同 prompt 干净右侧）：gaussian、stale、wrong_prompt、scale(1.10×)、layer_skip(用 C1 近似)、null_space。

---

## 4. 实验结果

### 4.1 完整表（held-out，200 prompts）

| pair | variant | honestFPR | gauss | stale | wrong | **scale** | layerskip | null |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A/B | scalar16 | 0.150 | 1.0 | 0.76 | 0.76 | 0.425 | 0.83 | 0.0 |
| A/B | scalar64 | 0.415 | 1.0 | 0.86 | 0.86 | 0.805 | 0.98 | 0.0 |
| A/B | projcos4 | 0.020 | 1.0 | 1.0 | 1.0 | **0.0** | 1.0 | 0.0 |
| A/B | projcos8 | 0.080 | 1.0 | 1.0 | 1.0 | **0.0** | 1.0 | 0.0 |
| A/B | projcos16 | 0.120 | 1.0 | 1.0 | 1.0 | **0.0** | 1.0 | 0.0 |
| A/B | **projscalar1_abs** | **0.000** | 1.0 | 1.0 | 1.0 | **1.0** | 1.0 | 0.0 |
| A/B | SRR-32 | 0.000 | 1.0 | 0.98 | 0.98 | **0.0** | 1.0 | 1.0 |
| A/B | SRR-64 | 0.000 | 1.0 | 0.98 | 0.98 | **0.0** | 1.0 | 1.0 |
| A/B | SRR-128 | 0.010 | 1.0 | 1.0 | 1.0 | **0.0** | 1.0 | 1.0 |
| A/C | projscalar1_abs | 0.005 | 1.0 | 1.0 | 1.0 | **1.0** | 1.0 | 0.0 |
| A/C | SRR-64 | 0.000 | 1.0 | 0.98 | 0.98 | **0.0** | 1.0 | 1.0 |
| A/D | projscalar1_abs | 0.000 | 1.0 | 1.0 | 1.0 | **1.0** | 1.0 | 0.0 |
| A/D | SRR-64 | 0.000 | 1.0 | 0.98 | 0.98 | **0.0** | 1.0 | 1.0 |
| B/D | projscalar1_abs | 0.000 | 1.0 | 1.0 | 1.0 | **1.0** | 1.0 | 0.0 |
| B/D | SRR-64 | 0.015 | 1.0 | 1.0 | 1.0 | **1.0** | 1.0 | 1.0 |

（完整 36 行见 `results/srr_vs_baseline.csv`）

### 4.2 scale TPR 一览（本实验的核心指标）

| pair | scalar16 | projcos4 | projscalar1_abs | SRR-32 | SRR-64 | SRR-128 |
|---|---:|---:|---:|---:|---:|---:|
| A/B | 0.425 | 0.0 | **1.0** | 0.0 | 0.0 | 0.0 |
| A/C | 0.335 | 0.0 | **1.0** | 0.0 | 0.0 | 0.0 |
| A/D | 0.155 | 0.0 | **1.0** | 0.0 | 0.0 | 0.0 |
| B/D | 0.555 | 0.0 | **1.0** | 1.0 | 1.0 | 1.0 |

### 4.3 关键定量证据（为什么 SRR 失效）

honest 异构漂移的 SRR 值（`max-group E/B`）分布 vs 1.10× scale 攻击的 SRR 值（= 0.01）：

| pair | C1 p50 | C1 p99 | C1 max | 1.10× scale 的 SRR |
|---|---:|---:|---:|---:|
| A/B | 0.0158 | 0.434 | **2.010** | 0.01 |
| A/C | 0.0205 | 0.440 | **1.967** | 0.01 |
| A/D | 0.0169 | 0.438 | **2.031** | 0.01 |
| B/D | 0.0003 | 0.003 | **0.011** | 0.01 |

**解读**：在 A 参与的配对（C1=Metal-int8 量化），honest 漂移的 SRR 中位数是 scale 攻击信号的 1.5~2×，99 分位是其 **40 倍**，最大值是其 **200 倍**。SRR 无法把二者分开。B/D 无量化 C1，honest 漂移小（~0.01），SRR 才勉强可用——但那是唯一没有量化路径的配对，且 projscalar1_abs 在那里的表现同样好。

---

## 5. 图（`results/figures/`）

- **fig1_scale_tpr_bar.png**：各变体在各配对上的 scale TPR 柱状图。清晰显示 projscalar1_abs 全绿（1.0），SRR 在 A 配对全红（0.0）。
- **fig2_fpr_vs_scale_tpr.png**：go/no-go 平面（x=honest FPR, y=scale TPR，目标 FPR≤0.10 且 scale TPR≥0.9）。projscalar1_abs 全部落在左下目标区；SRR 在 A 配对落在右下（FPR 低但 scale TPR 0）。
- **fig3_cost.png**：结构成本（ops/reads/ref-bytes，log 尺度）。SRR 的算术成本确实比 projcos 低（~64 vs ~65K ops），但这是唯一优势，不足以弥补检测失败。

---

## 6. 裁决（对照手册 §5）

| 标准 | SRR-64 结果 | 判定 |
|---|---|---|
| ① honest FPR ≤ 0.10（≥3/4 对） | A/B/C/D 全 0.00-0.015 ✅ | 通过 |
| ② scale TPR ≥ 0.9（修复 projcos 盲点） | **仅 B/D 通过，A/B/C/D 三对 = 0.0** ❌ | **失败** |
| ③ 方向性攻击 TPR ≥ 0.9 不倒退 | stale/wrong ~0.98、layer-skip 1.0 ✅ | 通过 |
| ④ 成本证据 | ops 更低 ✅ | 通过 |

**②失败，整体 NO-GO。** SRR 未达到"修复 scale 盲点"的核心目标。

---

## 7. 结论与建议

1. **不建议用 SRR 替换 projcos**。SRR 在含量化路径的配对（A 参与的 3 对）上完全无法检测 scale 攻击——这是本实验要解决的核心问题，SRR 没解决。
2. **真正的答案是已有的 projscalar1_abs**：它用 **1 维投影 + 绝对 gap**（保留 norm 但投影到 1 维），在全部 4 对上 scale TPR=1.0、honest FPR≤0.005，同时保持方向性攻击 TPR=1.0。它才是"同时捕获方向和尺度"的轻量方案，论文里已存在（表 4 的 projscalar1_abs 行）。
3. **SRR 数学正确的部分仍然成立**：`D = 1+ρ²-2ρc` 对纯缩放/纯方向/低精度的推导没错，成本分析也对。但**问题不在数学，而在数据**——honest 异构漂移与 scale 攻击在 norm 轴上不可分。这是为什么 projcos 故意丢弃 norm。
4. **对论文的建议**：projcos 的 scale 盲点是真实且已披露的（论文表 6 scale TPR 0.0107）。如果 NDSS 想补这个盲点，**用 projscalar1_abs 作为 hybrid 组件**（论文 §5.5 已经这么定位），而不是发明新统计量。本实验为这一结论提供了 4 对真实 capture 的定量背书。

---

## 8. 已知边界（诚实披露）

1. **A/C、A/D、B/D 用 M5-Pro-替代-C1 的 capture**（`sanity_20260727`），非原 M4。projcos16 有 ±0.05 复现偏差（原 sanity 报告已判 FAIL）。本实验的定性结论（SRR 盲于 scale）不依赖具体 C1 硬件，但在进正式论文前应重采真实 M4。
2. **layer_skip 攻击用 C1 替代 C2 近似**（无逐层激活）。结果标注为"近似替代"。
3. **null_space 攻击构造不理想**：SRR 的 null TPR=1.0 说明我的"正交扰动"没有真正落在 SRR 的盲区（实际是 C1 的激活和 C2 的激活差异足够大，SRR 能感知）。这本身也说明 SRR 对"内容替换类"攻击不设防——但这不是本实验的主结论，未深挖。
4. **E/F 对无 capture**，本实验不覆盖。
5. **SRR 使用固定 seed=2026（与基线一致）**，未测试 secret 每-请求抽样。手册 §4.3 的 secret 抽样是安全设计，但不影响本 FPR/TPR 结论（固定 seed 下 SRR 已失败）。

---

## 9. 产物清单

```
workspace/SRR/
├── srr.py                    # SRR 核心（E/B、分组 vote、抽样）
├── baselines.py              # 基线（复用 frozen hash_chain，projection_seed=911）
├── attacks.py                # 攻击族（gaussian/scale/stale/layer_skip/null_space）
├── run_srr_offline.py        # 离线 runner（单次 load + 全表）
├── plot_srr_results.py       # 出图
├── results/
│   ├── srr_vs_baseline.csv   # 完整 36 行结果表
│   └── figures/
│       ├── fig1_scale_tpr_bar.png
│       ├── fig2_fpr_vs_scale_tpr.png
│       └── fig3_cost.png
└── docs/
    ├── SRR_EXPERIMENT_HANDBOOK.md   # 实验手册（go/no-go 设计）
    └── SRR_DELIVERY_HANDBOOK.md     # 本交付手册
```

**复现命令**：
```bash
cd workspace/SRR
python3 run_srr_offline.py     # 全 4 对，~40s
python3 plot_srr_results.py    # 出图
```
