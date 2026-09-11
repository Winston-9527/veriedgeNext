# VeriEdge Paper1 Collaborative Repo

## What This Repo Is

这个仓库只解决一件事：让论文 1 的协作代码、正式交付物和本地运行产物各归其位，方便两个人并行推进而不复制共享代码。

它不是论文手册的替身。这里解释的是仓库架构、入口、归档规则和协作动线；论文目标、实验要求和 claim 仍以 `PAPER1_KICKOFF_MANUAL.docx` 为准。

## Design Principles

- 共享代码只保留一份，不按实验复制
- 正式交付物按实验聚合，便于多人协作和老师验收
- 重型运行产物留在 `workspace/`，不混进正式交付目录

## Repo Layers

### `artifacts/`

`artifacts/` 负责“怎么跑”。

这里放共享实验代码，不放论文正式交付物：

- `artifacts/thc/`：`E1 / E2 / E4` 共用 verifier、capture、calibration、overhead 代码
- `artifacts/TSTC/`：`E2` 补充 sweep 和出图脚本
- `artifacts/inference-E2E/`：`E5` orchestration / requester / provider / matrix control
- `artifacts/equivalence/`：`E5` 的环境与路径 sanity check

### `paper1_veriedge/`

`paper1_veriedge/` 负责“交什么”。

这里放按实验整理后的正式交付物，是日常协作的主要入口：

- `paper1_veriedge/E1/`
- `paper1_veriedge/E2/`
- `paper1_veriedge/E4/`
- `paper1_veriedge/E5/`

每个实验目录都保持同一结构：

- `logs/`：结构化原始结果
- `tables/`：清洗后的候选表
- `figures/`：候选图
- `notes/`：一页说明、运行记录、周报
- `README.md`：该实验的协作入口

共享周报模板在：

- `paper1_veriedge/weekly_report_template.md`

### `workspace/`

`workspace/` 负责“运行时临时放哪里”。

这里放本地重型运行产物、capture root、临时 batch run，不作为正式交付目录：

- `workspace/captures/`
- `workspace/runs/`

如果一个运行目录里主要是 `.npz`、中间 JSON、任务级明细和临时日志，它优先属于 `workspace/`，而不是 `paper1_veriedge/`。

## Canonical Tree

```text
veriedge-paper1-collab/
├── AGENTS.md
├── README.md
├── artifacts/
│   ├── thc/
│   ├── TSTC/
│   ├── inference-E2E/
│   └── equivalence/
├── docs/
│   ├── collaboration_rules.md
│   └── module_map.md
├── paper1_veriedge/
│   ├── E1/
│   │   ├── README.md
│   │   ├── run_capture.sh
│   │   ├── logs/
│   │   ├── tables/
│   │   ├── figures/
│   │   └── notes/
│   ├── E2/
│   │   ├── README.md
│   │   ├── run_ablation.sh
│   │   ├── run_noise_sweep.sh
│   │   ├── logs/
│   │   ├── tables/
│   │   ├── figures/
│   │   └── notes/
│   ├── E4/
│   │   ├── README.md
│   │   ├── run_overhead.sh
│   │   ├── logs/
│   │   ├── tables/
│   │   ├── figures/
│   │   └── notes/
│   ├── E5/
│   │   ├── README.md
│   │   ├── run_matrix.sh
│   │   ├── build_policy_table.sh
│   │   ├── logs/
│   │   ├── tables/
│   │   ├── figures/
│   │   └── notes/
│   └── weekly_report_template.md
├── requirements/
│   ├── e1.txt
│   ├── e2.txt
│   ├── e4.txt
│   └── e5.txt
└── workspace/
    ├── captures/
    └── runs/
```

## Where To Start By Experiment

### E1

- 协作入口：`paper1_veriedge/E1/README.md`
- 共享代码入口：`artifacts/thc/scripts/t3_hetero_cli.py`
- 默认运行层：`workspace/captures/E1/`
- 正式交付层：`paper1_veriedge/E1/`

### E2

- 协作入口：`paper1_veriedge/E2/README.md`
- 共享代码入口：`artifacts/thc/src/run.py`
- 补充 sweep：`artifacts/TSTC/run_noise_sweep.py`
- 默认正式输出层：`paper1_veriedge/E2/logs/` 与 `paper1_veriedge/E2/figures/`

### E4

- 协作入口：`paper1_veriedge/E4/README.md`
- 共享代码入口：`artifacts/thc/src/overhead_report.py`
- 默认正式输出层：`paper1_veriedge/E4/logs/`

### E5

- 协作入口：`paper1_veriedge/E5/README.md`
- 共享代码入口：`artifacts/inference-E2E/requester/matrix_control.py`
- 汇总入口：`artifacts/inference-E2E/requester/make_comparison_table.py`
- 默认运行层：`workspace/runs/E5/`
- 正式交付层：`paper1_veriedge/E5/`

## Where Files Should Go

- 新的共享脚本、公共配置、测试：放 `artifacts/`
- 运行产生的 capture root、batch run、任务级中间文件：放 `workspace/`
- 结构化原始结果：放 `paper1_veriedge/Ex/logs/`
- 清洗后的主稿候选表：放 `paper1_veriedge/Ex/tables/`
- 候选图：放 `paper1_veriedge/Ex/figures/`
- 一页说明、周报、实验记录：放 `paper1_veriedge/Ex/notes/`

如果一个文件还不能直接交给老师或回写主稿，默认先放 `workspace/`。

## Common Workflows

### 跑一次 E1 capture

1. 从 `paper1_veriedge/E1/run_capture.sh` 启动 capture
2. capture root 默认落在 `workspace/captures/E1/`
3. 从 capture 结果导出 pairwise 表后，再整理进 `paper1_veriedge/E1/logs/` 和 `tables/`

### 跑一次 E2 ablation

1. 从 `paper1_veriedge/E2/run_ablation.sh` 启动主实验
2. 原始结果落在 `paper1_veriedge/E2/logs/`
3. 候选图同步写到 `paper1_veriedge/E2/figures/`

### 跑一次 E4 overhead

1. 从 `paper1_veriedge/E4/run_overhead.sh` 启动统计
2. 结构化 CSV 直接写入 `paper1_veriedge/E4/logs/`
3. 挑选可进主稿的表后，再整理到 `paper1_veriedge/E4/tables/`

### 跑一次 E5 matrix 并生成对照表

1. 从 `paper1_veriedge/E5/run_matrix.sh` 启动 batch run
2. 批运行目录默认落在 `workspace/runs/E5/`
3. 用 `paper1_veriedge/E5/build_policy_table.sh` 把 `summary_by_cell.csv` 整理成正式对照表
4. 正式表落在 `paper1_veriedge/E5/tables/`

## Collaboration Branch Workflow

这一节是给协作者和协作者的 AI 看的。目标很简单：拿到仓库后，先进入自己的实验分支，再运行对应实验入口，最后只提交必要改动。

### Read Order For A New Collaborator

Wenxin第一次拿到仓库后，按下面顺序读：

1. 根说明：`README.md`
2. 协作规则：`docs/collaboration_rules.md`
3. 自己负责实验的入口说明：
   - `paper1_veriedge/E1/README.md`
   - `paper1_veriedge/E2/README.md`
   - `paper1_veriedge/E5/README.md`
4. 共享代码映射：`docs/module_map.md`

### Branch Ownership

- John：优先使用 `feat/e4-*`
- Wenxin：优先使用 `feat/e1-*`、`feat/e2-*`、`feat/e5-*`
- 纯文档调整：`docs/*`

如果改动跨了两个实验，仍然用“主实验”命名分支，不额外发明新的分支体系。

### First-Time Setup

Wenxin第一次本地准备环境时，按自己实验安装依赖：

```bash
cd /Users/johnlee/repo/VeriEdge/veriedge-paper1-collab
python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements/e1.txt
./.venv/bin/pip install -r requirements/e2.txt
./.venv/bin/pip install -r requirements/e5.txt
```

如果只做其中一个实验，也可以只装对应那一份 `requirements/*.txt`。

### Daily Branch Flow

每次开始新任务时，统一按这个流程：

```bash
git checkout main
git pull
git checkout -b feat/e2-sample-sweep
```

然后进入对应实验入口：

- `E1`：`paper1_veriedge/E1/`
- `E2`：`paper1_veriedge/E2/`
- `E4`：`paper1_veriedge/E4/`
- `E5`：`paper1_veriedge/E5/`

运行时遵守三层归属：

- 共享代码改动进 `artifacts/`
- 重型运行产物进 `workspace/`
- 正式交付物进 `paper1_veriedge/Ex/`

### What To Commit

允许提交：

- `artifacts/` 下真正需要共享的脚本、配置、测试修正
- `paper1_veriedge/Ex/logs|tables|figures|notes/` 下的正式交付物
- 与改动同步的 README / docs 更新

不要提交：

- `workspace/` 下的大型临时运行目录
- 模型权重、私钥、SSH 凭据
- 只供本机调试的临时文件

### If Shared Code Changes

如果Wenxin修改了共享层，例如：

- `artifacts/thc/`
- `artifacts/TSTC/`
- `artifacts/inference-E2E/`
- `artifacts/equivalence/`

那一轮提交必须同时做两件事：

1. 更新对应实验入口 README
2. 在对应实验的 `notes/` 里写清这次共享改动影响了什么

这样他的 AI 在下一轮继续接手时，能直接从实验入口和 notes 恢复上下文。

### Before Opening A PR Or Merging

提交前至少检查：

1. 改动是否落在正确层级
2. 正式结果是否进了 `paper1_veriedge/Ex/`
3. `workspace/` 是否没有误提交的大文件
4. 如果动了共享代码，相关 README 是否同步更新
5. 文件名是否遵守 `exp_e<id>_<date>_<owner>_*`

### Minimal Commit Pattern

建议提交信息直接带实验编号：

```bash
git add artifacts/ paper1_veriedge/E2 docs/
git commit -m "e2: add sample sweep results and wrapper notes"
```

这样协作者的 AI 只看分支名和 commit message，就能快速知道当前上下文属于哪个实验。

## What README Does Not Repeat

这个 README 不重复下面这些内容：

- 论文主张
- 每个实验要证明什么
- 推荐分工
- 两周安排
- 主稿回写位置

这些信息请直接看：

- `PAPER1_KICKOFF_MANUAL.docx`

如果只想知道“代码在哪、结果放哪、我应该从哪个入口开始”，看这个 README 就够了。
