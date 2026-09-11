# P1b: Real BF16 → Low-Precision Precision Cheating

**实验日期**：2026-08-06
**执行环境**：Mac mini M4（100.80.96.92），PyTorch 2.10 + MPS，Qwen3-0.6B
**前置**：P0（exact-replay 边界）、P1a（sign-balanced 攻击）

---

## 1. 实验设计（关键：真实低精度 forward，非人为 quantize 输出）

恶意节点**整个 forward 使用低精度算术**：
- 每个 `nn.Linear`：权重量化到目标精度（per-output-channel scale），输入 activation 量化到目标精度，用**量化后的值**做 matmul（fp32 累积，MPS 无原生低精度 mm），误差逐层传播。
- 边界 activation 在交给验证器前 cast 回 BF16。
- 诚实对照：同设备、同模型、同输入，BF16 重跑（控制组）。

**诚实性说明**：MPS 无 int8/fp8 原生 matmul kernel，matmul 在 fp32 上执行，但**操作数是真实量化后的值**（round 到 int8/int4/fp8 grid），因此每层量化误差的传播与真实低精度 forward 等价。累积精度是硬件限制，已在方法中披露。FP8 用真实 E4M3 grid（3-bit mantissa）round。

---

## 2. 结果（SignRadial，layer 16，10 prompts）

| prompt | honest | INT8 | FP8 | INT4 |
|---|---:|---:|---:|---:|
| France | 0.0000 | 0.049 | 0.989 | 0.952 |
| relativity | 0.0000 | 0.122 | 0.991 | 0.936 |
| Python fib | 0.0000 | 0.071 | 0.961 | 0.911 |
| TCP/UDP | 0.0000 | 0.067 | 0.967 | 0.943 |
| Hamlet | 0.0000 | 0.128 | 0.962 | 0.943 |
| sky | 0.0000 | 0.059 | 0.998 | 0.954 |
| translate | 0.0000 | 0.041 | 0.970 | 0.940 |
| sqrt144 | 0.0000 | 0.104 | 0.975 | 0.973 |
| water cycle | 0.0000 | 0.110 | 0.982 | 0.944 |
| cookies | 0.0000 | 0.080 | 0.984 | 0.940 |

**汇总：**

| 精度 | SignRadial mean | min | max |
|---|---:|---:|---:|
| honest~honest | 0.0000 | 0.0000 | 0.0000 |
| **INT8** | 0.083 | 0.041 | 0.128 |
| **FP8** | **0.978** | 0.961 | 0.998 |
| **INT4** | **0.943** | 0.911 | 0.973 |

---

## 3. 检测判定（对比部署 honest 噪声阈值）

部署 honest 异构噪声的 SignRadial p99（A/B, q=256，来自 capture 研究）：

| checkpoint | honest p99 | INT8 检出率 | FP8/INT4 |
|---|---:|---:|---|
| C1 | 0.060 | 70% | 100% |
| C2 | 0.032 | **100%** | 100% |
| C3 | 0.012 | **100%** | 100% |

**结论：**
- **FP8 / INT4 精度作弊：SignRadial 秒抓**（0.91~0.99，是 honest p99 的 15~80 倍，全部 prompt 检出）。
- **INT8 精度作弊：边界情况**。若验证器检查 C2/C3 边界（p99 0.032/0.012），**100% 检出**；若只检查 C1（p99 0.06），70% 检出。**多边界检查（C1+C2+C3）显著提高 INT8 检测**——这正好支持"逐层/多边界验证"的部署设计。
- **honest~honest=0**：同设备 BF16 逐 bit 一致，证明误差确实来自精度作弊，不是随机。

---

## 4. 意义

1. **回答了 threat model 核心问题**：恶意节点"偷用低精度算力"（FP8/INT4）会在边界激活上留下 SignRadial 可检测的相干漂移，**被稳定检测**。
2. **INT8 是攻击者的"甜点"**（可能躲过单边界检测），但**多边界检查**可覆盖。
3. **SignRadial 对真实精度作弊有效**——不是合成噪声，是真实逐层低精度 forward 产生的漂移。
4. **诚实边界**：
   - MPS 无原生低精度 mm，matmul 在 fp32 上（但操作数是量化值，误差传播真实）。
   - 未测 W8A16 vs W8A8（weight-only 需 RTX3090/bitsandbytes）。
   - 未测输出退化（token disagreement/KL）——需 decode 路径，列为 P4c。

---

## 5. 产物

```
workspace/SRR/
├── p1b_precision_cheating.py   # 单 prompt 快速版
├── p1b_full.py                 # 10 prompts 完整版（本结果）
└── docs/P1B_PRECISION_CHEATING.md  # 本文件
```

**复现**：`scp p1b_full.py mini:~/VeriEdge-repro/ && ssh mini 'cd ~/VeriEdge-repro && ./.venv/bin/python3 p1b_full.py'`
