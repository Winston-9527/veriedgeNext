# W8A16 重做实验 memo（推翻旧结论）

> 日期：2026-08-08
> 目的：修正旧 `p4b_w8a16_vs_w8a8.py` 的方法问题，用统一协议重测 W8A16（weight-only int8）检测
> 数据：720 池（200 calib / 520 eval），A=MPS bf16 / B=CUDA fp32；W8A16 用 bitsandbytes 真实 int8 权重 kernel
> 脚本：`run_w8a16_redo.py`（RTX6000）

---

## 0. 结论（重大修正）

**旧结论"W8A16 是所有方法的共同漏检区（SignRadial=0.00）"是实验方法问题的假象。在正确协议下，W8A16（weight-only int8）可被 100% 检测。**

**主表（阈值 = calibration A/B honest 分布 Q_{0.99}，即 nominal 1% FPR）：**

| case | SignRadial | ProjCos4 | Combined |
|---|---|---|---|
| **honest（= FPR）** | 0.0096 | 0.0154 | 0.0096 |
| **W8A16（= TPR）** | **1.0000** | **1.0000** | **1.0000** |

> **读表说明**：阈值固定为 calibration 上 honest 的 Q_{0.99} 后：
> - **honest 行 = FPR**（honest 样本被误判为攻击的比例，实测 0.96%~1.54% ≈ nominal 1%）；
> - **W8A16 行 = TPR@1%FPR**（攻击被检出的比例，全 1.0）。
> 两行共用同一阈值，可直接比较。

**分离度**：mean SR honest=0.0038 vs W8A16=**0.279**（73×）；mean ProjCos honest=0.00014 vs W8A16=**0.105**（750×）。

---

## 1. 旧实验的问题（为什么旧结论是错的）

旧 `p4b_w8a16_vs_w8a8.py` 有 3 个方法缺陷：

| # | 缺陷 | 后果 |
|---|---|---|
| 1 | **honest 基线 = 同设备同输入重跑**（`hs_h = m_ref` 重跑）→ ≈0 | honest 噪声被完全抹掉，阈值失真 |
| 2 | **阈值用"部署 honest p99"（A/B 异构 0.066），但 honest 数据是零噪声** | 阈值来源与 honest 基线不匹配——W8A16 的 0.001-0.009 被误判为"远低于阈值" |
| 3 | **score 用全张量**（非 q=64 采样）| 口径与正式协议不一致 |

旧实验因此得出"W8A16 不可检测（0.00）"——**这是用了错误阈值（0.066 vs 真实 honest 0.009）导致的假象**。

---

## 2. 新实验协议（修正）

- **honest 阈值**：从 calibration 的 **A/B 异构 honest score 分布**（D(H_A, H_B)）取 Q_{0.99}。实测 SR p99=0.009、ProjCos p99=0.0006。
- **协议统一**：ref = H_A（stack_a，MPS），cand = honest H_B（stack_b，CUDA fp32）或 **W8A16(H_B)**（bnb int8 权重，同设备同输入）。检测器比较 D(H_A, cand)。
- **W8A16 用真实 kernel**：bitsandbytes `load_in_8bit`（`MatMul8bitLt` 真实 int8 权重 matmul）。
- **score**：q=64 采样 SignRadial + ProjCos4，trace max over C1/C2/C3。
- **Combined**：ECDF-normalized max-fusion，joint threshold。

---

## 3. 结果（详细）

### 3.1 主结果（eval 520）

| case | SignRadial | ProjCos4 | Combined |
|---|---|---|---|
| honest（FPR）| 0.0096 | 0.0154 | 0.0096 |
| **W8A16（TPR）** | **1.0000** | **1.0000** | **1.0000** |

> 同一阈值（calibration honest Q_{0.99}）下：honest 行是 FPR（≈1% nominal），W8A16 行是 TPR@1%FPR（100%）。

### 3.2 score 分布

| 指标 | honest | W8A16 | 倍数 |
|---|---|---|---|
| mean SignRadial | 0.0038 | 0.279 | 73× |
| mean ProjCos | 0.00014 | 0.105 | 750× |

---

## 4. 解读

1. **W8A16 可检测**：真实 int8 权重的量化误差逐层传播到边界 activation，产生显著的 activation 级漂移（即使 activation 本身保持 fp16）。SignRadial/ProjCos 在正确阈值下 100% 检出。
2. **旧结论推翻**：文档 §6.2 的"W8A16 共同漏检区（0.00/0.40/0.50）"作废——那是错误阈值（0.066 vs 真实 0.009）的产物。
3. **对新机制的意义**：weight-only int8 降精度**不再是 activation 级检测器的盲区**——在正确协议（A/B 异构 honest 阈值）下可检测。这削弱了"需输出级检测覆盖 W8A16"的旧担忧。
4. **诚实保留**：此结论依赖 W8A16 的量化误差确实传到边界 activation（Qwen3-0.6B 上成立）。不同模型/层深可能不同，应标注为"本模型实测"。

---

## 5. 与旧文档 §6.2 的关系

旧 §6.2 表（SignRadial64=0.00、ProjCos4=0.40、Scalar16=0.50）**作废**，由本实验结果替换：
- SignRadial=1.0、ProjCos4=1.0、Combined=1.0（W8A16）。

W8A8/FP8/INT4 的结论（全 1.0）不受影响，但旧表的 W8A16 列需更新。

---

## 6. 复现

```bash
# RTX6000（需 torch+transformers+bitsandbytes+accelerate+Qwen3-0.6B cache）
cd ~/Developer/ndss2027/workspace/inversion/scripts
python3 run_w8a16_redo.py
```
