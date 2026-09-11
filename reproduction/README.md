# reproduction/ — VeriEdge 实验库（EuroSys '27 论文）

> ⚠ **这是 EuroSys '27 论文的实验库，不是独立的一套 NDSS 实验。**
> 对应论文：*VeriEdge: Verifiability-Constrained Placement for Heterogeneous Edge LLM Inference*（EuroSys '27 投稿，`main_eurosys_ORIGINAL_REFERENCE.tex`）。
> 当前 NDSS 稿 `main_ndss.tex`（*Accountable LLM Inference across Untrusted Heterogeneous Edge Providers*）**是从 EuroSys '27 投稿逐字迁移而来**（正文第 3 行注明 "migrated verbatim from the EuroSys '27 submission; NOT yet rewritten"）。因此本库的 E1/E2/E4/E5 与 Q1-Q5 图表**原属 EuroSys '27 稿**；NDSS 稿目前复用同一批实验，尚未按 NDSS 重做或改名。

论文实验的**完整重跑代码库**（Experiment Library），非破坏性复制自工作区 `ndss2027/reproduction/VeriEdge/`。

## 内容

```
VeriEdge/
├── artifacts/            共享实验代码（"怎么跑"）
│   ├── thc/              E1/E2/E4: verifier / capture / calibration / overhead
│   ├── TSTC/             E2: noise sweep + 出图
│   ├── inference-E2E/    E5: orchestration / requester / provider
│   └── equivalence/      E5: 环境 sanity
├── paper1_veriedge/      正式交付物（"交什么"）
│   ├── E1/ E2/ E4/ E5/   各含 logs/ tables/ figures/ notes/ README.md
│   └── 实验交付手册_统一目录/
├── docs/                 模块映射（module_map.md）、论文目标手册
├── requirements/         分实验依赖（e1/e2/e4/e5.txt）
└── README.md             仓库架构说明
```

## 与论文编号的对照

> 下表章节号（§6.x / Q1-Q5）取自 **EuroSys '27 稿**——本库实验的原属论文。NDSS 稿沿用相同的 §6 Evaluation 结构（逐字迁移），故章节号一致。

| 论文章节（EuroSys '27）| 实验库 | 目录 |
|---|---|---|
| §6.2 Placement replay (Q1) | E5 | `paper1_veriedge/E5/` |
| §6.3 Delivery (Q2) | Experiment B | （在 ndss2027 工作区 workspace/，未随本库复制）|
| §6.4 Verifier profiles (Q3) | E1 | `paper1_veriedge/E1/` |
| §6.5 Sketch vs budget (Q4) | E2 | `paper1_veriedge/E2/` |
| §6.6 Material-tamper (Q4) | E2 + E2-R | `paper1_veriedge/E2/`（+ ndss2027 `workspace/SRR/`）|
| §6.7 Payload/runtime (Q5) | E4 | `paper1_veriedge/E4/` |

## 未包含

- `workspace/`（重型运行产物，268M）——按"只代码"约定排除
- `.git/`（本目录是文件副本，不含原仓库历史；原仓库：`Winston-9527/VeriEdge`）
