# reproduction/ — VeriEdge 实验库

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

| 论文章节 | 实验库 | 目录 |
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
