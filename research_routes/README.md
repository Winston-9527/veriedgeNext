# VeriEdge 三条研究路线资产总览

整理日期：2026-08-24

本目录把当前项目拆成三个互相独立的研究资产包。整理采用**非破坏性复制**：原始
`ndss2027/`、`artifact_*` 和 `paper1_veriedge/` 均保持原位，现有论文编译与脚本
路径不会因此失效。

## 路线目录

| 路线 | 目录 | 当前研究目标 |
|---|---|---|
| A | `route_a_detection_ceiling/` | 当前 NDSS 稿及其 top-4 强化：低秩 verifier 的 harm-aware detection ceiling 与外部系统攻击 |
| B | `route_b_veriedge_system/` | *VeriEdge: Risk-Adaptive Verification for Cross-Provider LLM Inference at the Edge*；PACT 是核心协议 |
| C | `route_c_minimax_theory/` | commit-before-draw 条件下的检测—带宽极小极大前沿 |

## GitHub 层级与当前上传范围

A、B、C 始终保持为 `research_routes/` 下的同级目录，不把任何一条路线提升为整个
GitHub 仓库的根目录。当前私有仓库只上传路线总览和 Route B：

```text
research_routes/
├── README.md
├── route_a_detection_ceiling/    # 后续上传
├── route_b_veriedge_system/      # 本次上传
└── route_c_minimax_theory/       # 后续上传
```

首次提交应显式添加 `research_routes/README.md` 和
`research_routes/route_b_veriedge_system/`，不要直接添加整个
`research_routes/`，以免把本地 Route A/C 资产提前提交。

## 共享资产规则

同一原始捕获、相关工作 PDF、旧系统实现或对照实验若服务于多个路线，已分别复制
到各路线的 `shared/` 或相应 artifact 快照中。三条路线可以独立移动、交给不同成员
或在不同实验机上运行，不依赖跨路线相对路径。

每个路线根目录的 `FILE_MANIFEST_SHA256.csv` 是整理完成后的文件完整性清单。

## 维护规则

1. 新工作只在对应路线目录中继续；不要把 A/B/C 新结果重新混回同一个实验目录。
2. `retired`、`legacy` 和 `shared` 目录中的内容默认只读；要改造时先复制到路线自己的
   活跃 `experiments/` 或 `docs/`。
3. 同一结果被多个工作使用时，在各路线 README 中记录来源、版本和是否可形成论文
   claim，避免双重计入贡献。
4. 当前 NDSS 投稿的冻结版本仍以原 `ndss2027/` 为准；本目录是后续研究工作区快照。
