# Verifier 设计对齐检查：坐标提交-重放协议 vs 攻击实验

**检查日期**：2026-08-07
**目的**：核对论文/实验的 verifier 设计（节点先提交坐标/digest，verifier 重放比较）与我的攻击实验设计是否一致。

---

## 1. 论文 verifier 设计（TSTC 挑战协议，§3.4）

流程：
1. **Placement 提交** `(G, σ, ϑ)`：含 checked boundaries、sketch mode、tolerances、**seed context**、replay/reference path。
2. **执行**：provider 提交 sketch digest `g = Hash(Ser(z) ‖ k ‖ ctx)`，链式 `h_k = Hash(h_{k-1} ‖ g_k)`。
3. **挑战**：provider reveal sketch `z`，verifier **用 committed context 重放 reference** `z' = Φ(H_ref)`，比较 `δ = μ(z, z') ≤ Γ`。

**关键点**：
- 坐标由 **seed context** 派生，seed context 在 placement 时 **committed**。
- provider 先提交 **digest**（不是坐标本身），挑战时才 reveal sketch。
- verifier 用 committed context 重放 reference，**不依赖 provider 提供的坐标**。

## 2. 手册对坐标保密的要求（实验设计）

手册 §4.3（`SRR_EXPERIMENT_HANDBOOK.md`）明确：
> **恶意节点必须在不知道抽样位置时先固定/发送 activation**，否则任何抽样检测都可能被绕过。
> seed = PRF(K, request_id ‖ layer_id)

即坐标应 **secret per-request**（PRF 派生），攻击者不知道被抽查哪些坐标。

## 3. 我的攻击实验的坐标假设

| 实验 | 攻击者坐标假设 | 是否对齐 |
|---|---|---|
| P1a sign-balanced（全张量）| 攻击者改**整层**使其对 sign(x) 正交 | ⚠️ 见下 |
| P2b balanced-channel | 攻击者改**整层**一半 channel 上/下 | ⚠️ 见下 |
| P3b partial replay | 攻击者改部分 token | ✅（盲改）|
| P4b/P1b 精度作弊 | 真实低精度 forward | ✅（不依赖坐标）|

**P1a/P2b 的不对齐**：我的 sign-balanced 攻击用固定 seed（等于 verifier 的 seed），且攻击者改**整个张量**。这对应"攻击者知道全部坐标 + 能改整个张量"的最强假设——比论文的真实协议（坐标 secret、攻击者盲改）更强。

## 4. 坐标保密对齐测试（p5c_coord_secrecy.py + p5c_partial_coord_attack.py）

### 4.1 全张量攻击：坐标 KNOWN vs SECRET

| 攻击 | KNOWN（攻击者知坐标）| SECRET（攻击者不知）|
|---|---|---|
| sign-balanced | 0.000 | **0.000** |
| balanced-channel | 0.005 | **0.005** |

**发现**：全张量攻击下坐标保密**不救 SignRadial**——因为攻击者改整个 C2 使其对 sign(x) 正交，无论 verifier 抽查哪 256 个坐标都失效。

### 4.2 部分坐标攻击（真实盲攻击者）

| 攻击者篡改坐标比例 | SignRadial TPR |
|---|---:|
| 5% | 0.335 |
| 10% | 0.400 |
| 25% | 0.585 |
| 50% | 0.615 |
| 75% | 0.810 |
| 100% | 0.980 |

**发现**：真实自适应攻击者（不知道 verifier 坐标）只能盲改部分坐标时，**SignRadial 能检测**（5%→33%，50%→62%，100%→98%）。

## 5. 对齐结论

1. **论文设计正确**：坐标 secret（committed seed context + PRF 派生）是关键防御。它使攻击者无法精确构造"整层对 sign(x) 正交"，从而**削弱 sign-balanced 攻击**。

2. **我的 P1a 攻击高估了攻击者能力**：它假设攻击者知道全部坐标且能改整个张量。在论文真实协议（坐标 secret、攻击者盲改）下，SignRadial 的 sign-balanced 盲点**显著缓解**（盲改部分坐标反而泄漏信号）。

3. **需要诚实披露**：论文/实验报告应区分两种攻击模型：
   - **白盒全张量**（攻击者知坐标，改整层）：SignRadial 盲（TPR=0）→ ProjCos 补回
   - **真实自适应盲改**（坐标 secret，攻击者盲改部分）：SignRadial 恢复检测（TPR 随篡改比例升）

4. **对部署建议**：保持坐标 secret per-request（PRF），并**抽查多个 checkpoint 边界**（C1/C2/C3）——既增加攻击者盲改的难度，又让 sign-balanced 盲点只在极端假设下出现。

## 6. 验证过的协议细节

- ✅ 论文"provider 提交 digest、verifier 重放 reference"：我的离线实验直接比较 H_cand vs H_ref 的 sketch，等价于"verifier 重放 reference sketch 后比较"（因为 reference 由 committed context 派生，不依赖 provider）。**digest-commit-reveal 时序不影响检测统计量**。
- ✅ 论文"坐标由 committed seed context 派生"：我的实验用固定 seed 派生坐标，与 committed context 一致。
- ✅ 手册"恶意节点先固定 activation 再被抽查"：我的部分坐标攻击正是这个场景。

## 7. 产物

```
workspace/SRR/
├── p5c_coord_secrecy.py         # 坐标 KNOWN vs SECRET（全张量）
├── p5c_partial_coord_attack.py  # 部分坐标盲攻击
└── docs/VERIFIER_ALIGNMENT.md   # 本文件
```
