# Security Boundary: Exact-Replay and Freshness

**结论（P0，无实验）**：SignRadial（以及任何基于 activation-equality 的检测器）**不能**检测"exact replay"——即恶意节点重放一个**之前已正确计算、数值完全正确**的 activation。

---

## 1. 为什么检测不出来

假设恶意节点重放的是：

- 同一个 input、同一个 prefix、同一个模型、同一个 precision 下，**以前已经计算过的完全正确的 activation**。

则：

```
H_replay = H_ref
```

于是：

```
SignRadial = 0        （分子 Σ sign(x)(y-x) = 0）
ProjCos    = 0        （cosine gap = 0）
SRR        = 0        （Σ(y-x)² = 0）
```

**因为从数值上看它就是正确答案**，任何基于数值比较的验证器都会把它当作"诚实执行"。

## 2. 这为什么不是一个漏洞

这恰好是正确的安全边界：

- 验证器（以及 SignRadial）证明的是 **"这个 activation 与当前计算兼容"**，而不是 **"这次真的重新执行了计算"**。
- 如果安全目标要求节点证明"本次真实重新计算，不得使用以前正确缓存的结果"，那是 **cryptographic freshness** 问题，不是数值验证问题。

## 3. 需要 freshness 机制的情形

若威胁模型包含"恶意节点偷懒复用正确缓存"：

- 需要 **nonce / canary / commitment** 等 freshness 机制，让每次计算的输入不同，从而正确缓存的 activation 与本次计算不兼容。
- 例如：在输入中注入一个请求特定的扰动（canary），则"正确的旧激活"不再匹配"带 canary 的当前激活"，SignRadial 就能检测到差异。
- 或者：对每次请求生成不同的 seed/上下文，使诚实节点必须真实执行。

## 4. SignRadial 能检测什么 / 不能检测什么

| 攻击 | SignRadial | 说明 |
|---|---|---|
| stale（其他请求的激活） | ✅ ~0.995 | 与当前计算不兼容 |
| wrong-prompt（不同 prompt） | ✅ ~0.995 | 同上 |
| 低精度作弊（BF16→INT8） | ✅ 待 P1b 验证 | 数值漂移，方向可能相干 |
| **exact replay（正确缓存）** | ❌ **0** | 数值上就是正确答案，非数值问题 |

**结论**：SignRadial 检测的是 **stale activation incompatible with the current computation**，不是 **cryptographic freshness**。后者需要 nonce/canary/commitment 等独立机制。这一边界必须在论文威胁模型中写清楚，避免被审稿人当作"验证器缺陷"。
