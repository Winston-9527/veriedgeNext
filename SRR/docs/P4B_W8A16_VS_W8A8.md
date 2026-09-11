# P4b: W8A16 vs W8A8 Precision Cheating（RTX3090）

**实验日期**：2026-08-07
**执行环境**：RTX3090（172.31.100.17），CUDA，Qwen3-0.6B
**前置**：P1b（MPS 上的 FP8/INT8/INT4）、P2a/P2b/P3b/P5a

---

## 1. 威胁区分（两种不同的低精度作弊）

| 配置 | 量化范围 | 实现 | 威胁本质 |
|---|---|---|---|
| **W8A16** | 仅权重 int8，activation 保持 fp16 | bitsandbytes `load_in_8bit`（真实 int8 内核） | weight-only quantization |
| **W8A8** | 权重 + activation 都 int8 | 逐层 int8 量化 + fp32 matmul（操作数是量化值） | 全低精度计算 |

**关键差异**：W8A16 只量化权重，activation 仍高精度；W8A8 权重和 activation 都低精度，误差逐层传播到激活。

---

## 2. 结果（SignRadial, layer 16, 10 prompts）

| prompt | honest | W8A16 | W8A8 |
|---|---:|---:|---:|
| France | 0.0000 | 0.0019 | 0.0458 |
| relativity | 0.0000 | 0.0059 | 0.1311 |
| Python fib | 0.0000 | 0.0092 | 0.0680 |
| TCP/UDP | 0.0000 | 0.0015 | 0.0810 |
| Hamlet | 0.0000 | 0.0082 | 0.1190 |
| sky | 0.0000 | 0.0019 | 0.0744 |
| translate | 0.0000 | 0.0050 | 0.0438 |
| sqrt144 | 0.0000 | 0.0014 | 0.0849 |
| water cycle | 0.0000 | 0.0094 | 0.1018 |
| cookies | 0.0000 | 0.0071 | 0.0796 |

**汇总：**

| 配置 | mean | min | max |
|---|---:|---:|---:|
| honest~honest | 0.0000 | 0.0000 | 0.0000 |
| **W8A16** | **0.0051** | 0.0014 | 0.0094 |
| **W8A8** | **0.0830** | 0.0438 | 0.1311 |

---

## 3. 检测判定（对比部署 honest p99）

| 阈值 | W8A16 检出率 | W8A8 检出率 |
|---|---:|---:|
| C1 p99=0.060 | **0%** | 80% |
| C2 p99=0.032 | **0%** | **100%** |
| C3 p99=0.012 | **0%** | **100%** |

---

## 4. 结论（决定性差异）

1. **W8A16 无法被 SignRadial 检测**：SignRadial 值 0.001~0.009，**远低于所有层级的 honest p99（0.012~0.06）**，任意阈值下 0% 检出。原因：weight-only 量化不改变 activation 的值（只是权重变化被后续层部分吸收），边界激活的相干漂移极小。
2. **W8A8 可被 SignRadial 检测**：SignRadial 值 0.044~0.131，在 C2/C3 边界 **100% 检出**（0.032/0.012），在 C1 边界 80%（0.060）。原因：activation 也量化，误差逐层传播到边界激活。
3. **这是两种本质不同的威胁**：
   - **W8A16**（weight-only）→ 对 SignRadial（以及任何 activation-based 检测器）**不可见**，需要输出级检测（judge/KL）或 replay。
   - **W8A8**（full low-precision）→ SignRadial 可检测（多边界 C2/C3 全覆盖）。
4. **对 threat model 的启示**：W8A16 的攻击者"偷用 8-bit 权重算力"在 activation 上几乎无迹可寻——这是 SignRadial 的**已知盲区**，必须诚实披露。若要覆盖，需输出级检测或对权重做 commitment。

---

## 5. 产物

```
workspace/SRR/
├── p4b_w8a16_vs_w8a8.py         # RTX3090 脚本
└── docs/P4B_W8A16_VS_W8A8.md    # 本文件
```

**复现**：`scp p4b_w8a16_vs_w8a8.py 3090:~/VeriEdge-repro/ && ssh 3090 'cd ~/VeriEdge-repro && ./.venv/bin/python3 p4b_w8a16_vs_w8a8.py'`
