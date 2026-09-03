# 三种 T 说明：抓取 T 随 prompt 变 / 检测采样 T=16 / 攻击构造 T=12

> 简短备忘｜2026-08-11｜目的：消除对 checkpoint 层数 T 的混淆。模型固定 hidden_size D=1024（Qwen3-0.6B-8bit），**T（token 数）在三个语境里各不相同**。

---

## 一句话

**D=1024 固定；抓取保留完整 seq_len（T=10–23 随 prompt 变），检测采样 T=16，攻击构造 T=12**——三个数字各属一层，互不冲突。

---

## 1. 抓取层：T = 实际 prompt 的 seq_len（随 prompt 变化）

- checkpoint 激活 shape `(1, seq_len, 1024)`，**T = seq_len = 该 prompt 的 token 数**；
- 实测 720/720 与 prompt `token_count` 精确匹配（10–23 分布）；
- **为什么不固定**：抓取要完整保留整条序列的中间表示，不能裁剪——截断会丢信息。所以 T 是**变量**，随 prompt 长度线性变化。

## 2. 检测层：采样固定 T=16（为什么）

- 主稿与 P0-E2 handbook 的 `T=16` 是**检测器的采样参数**，不是抓取保留数：
  - **prefill**：激活 `H ∈ R^{16×d}`，采 16 个 token 算 sketch（projcos4 → T·d=64 floats=256 bytes）；
  - **decode**：单步只有 1 token，不存在"每 step 选 16 token"，改用**窗口 W=16 个连续 step**；
- **为什么固定 16**：检测需在**不同长度 prompt 间公平比较**——若 T 随 prompt 变，短 prompt 和长 prompt 的 sketch 没有可比性。固定 T=16 给检测一个统一口径（payload 大小、检测成本都可预期）。

## 3. 攻击层：构造 T=12（为什么）

- E2R joint_null 攻击的 `T=12` 是**具体攻击样本的激活 token 数**；
- 用在 nullspace 维度：`dim_null = T·D − rank(C)`，12×1024−49=12239 精确对上；
- **为什么是 12 不是别的**：这是该攻击所选验证样本的实际 seq_len（token_count=12），不是全局固定值——换一个 13/14 token 的样本，dim_null 会相应变成 13×1024−49 等。

---

## 小结（对照表）

| 层 | T 值 | 固定? | 语义 | 对应实验/文档 |
|---|---|---|---|---|
| 抓取（checkpoint） | = seq_len（10–23） | 否，随 prompt 变 | 完整保留中间表示 | **P0-E3 抓取**：`workspace/inversion/results/formal_capture/manifest.json`（`seq_len` 字段，720/720 与 prompt `token_count` 匹配） |
| 检测（sketch） | = 16 | 是 | 跨长度公平比较 + 成本可预期 | **P0-E2 主实验（E2-R）**：P0_E2_DETECTOR_EVALUATION_HANDBOOK_V3.md §2.1（"固定 T=16"）、§9（prefill T=16 / decode W=16 窗口）；主稿 main_ndss.tex:1023（"with T=16, projcos4 reveals T·d=64 floats"） |
| 攻击（nullspace） | = 样本 seq_len（如 12） | 否，随样本变 | 算 dim_null = T·D − rank(C) | **P0-E2 E2R 盲点审计**：`workspace/AdversarialEvaluation/results/e2r/E2R_RESULT_MEMO.md:144`（joint_null 构造，dim=12239=T·1024−49） |

> 关键区分：**抓取层是"保留多少"（越多越好），检测层是"采样多少"（固定才好比），攻击层是"构造时用哪个样本"（随样本变）**。
>
> 对应实验一句话：**E2-R 主实验**跑在检测 T=16 上（projcos4/scalar16 对 prefill 16-token sketch 打分）；**E3-T 三节点 trace**的 checkpoint 激活就是抓取层 T=seq_len 的真实中间表示（P1-E4 哈希链绑定的也是它）；**E2R 盲点审计**的 joint_null 攻击在 T=12 样本上构造 nullspace。
