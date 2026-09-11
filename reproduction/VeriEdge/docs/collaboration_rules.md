# Collaboration Rules

## 边界

- 只围绕论文 1 当前四组实验：`E1 / E2 / E4 / E5`
- 所有结果都必须增强主稿的 claim，而不是扩成旧的“区块链资源市场”大稿

## 协作角色

- John：主责 `E4`，并维护 `artifacts/thc/` 这条共享 verifier 主线
- Wenxin：主责 `E1 / E2 / E5`，优先复用共享层，不复制逻辑
- 共享责任：谁改公共入口，谁同步更新实验层 README

## 文件归属

- `artifacts/`：共享代码
- `workspace/`：重型运行产物
- `paper1_veriedge/E1~E5/`：正式交付物

## 结果交付规则

- 每次实验至少交 3 类文件：原始结果表、清洗后的表、1 页以内结果说明 （提交的comment请用中文）
- 原始结果优先进 `paper1_veriedge/Ex/logs/`
- 主稿候选表进 `paper1_veriedge/Ex/tables/`
- 主稿候选图进 `paper1_veriedge/Ex/figures/`
- 说明和周报进 `paper1_veriedge/Ex/notes/`

## 命名规则

- 统一格式：`exp_<expid>_<yyyymmdd>_<owner>_<suffix>`
- 例子：
  - `exp_e1_20260425_wenxin_pairwise_details.csv`
  - `exp_e4_20260425_johnlee_latency_breakdown.csv`

## 协作禁忌

- 不要只提交截图，不提交结构化结果表
- 不要混用 calibration 与 evaluation prompts
- 不要静默修改共享 config、cluster file、prompt split
- 不要强推默认分支或直接覆盖对方同名结果文件
- 不要把模型权重、私钥、SSH 凭据、超大 `.npz` capture 直接提交
- 不要把 E5 做成 welfare / pricing 对比，而忽略 latency / challenge / goodput / verifier workload
- 不要只报平均值不报单位
- 不要把估算值写成实测值

## 建议工作流

1. 在 `workspace/` 运行重型 capture 或 batch run
2. 把结构化原始结果整理到 `paper1_veriedge/Ex/logs/`
3. 把主稿候选表整理到 `paper1_veriedge/Ex/tables/`
4. 把候选图整理到 `paper1_veriedge/Ex/figures/`
5. 在 `paper1_veriedge/Ex/notes/` 写一页说明：结果是什么、是否能进主稿、还缺什么

## 分支建议

- `feat/e1-*`
- `feat/e2-*`
- `feat/e4-*`
- `feat/e5-*`
- `docs/*`

## 周报模板

模板见：`paper1_veriedge/weekly_report_template.md`
