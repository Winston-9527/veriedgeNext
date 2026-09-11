# VeriEdge Paper1 Repo Protocol

本仓库只服务论文 1（`VeriEdge`）当前四组核心实验：`E1`、`E2`、`E4`、`E5`。

默认规则：

1. 任何改动都要回到系统稿主张：`verification-aware orchestration`，不要把方向带回“市场机制/平台大拼盘”。
2. 原始结果优先：先交 `csv/json/jsonl/md` 等结构化产物，再谈截图和排版图。
3. 不要混用 `calibration` 与 `evaluation` 数据；目录、文件名、说明都要写清。
4. 本仓库只提交可协作资产：脚本、配置、原始结果表、清洗表、图、说明；大模型权重、私钥、超大 capture 二进制不要入库。
5. 本地重型运行产物统一放在 `workspace/`，正式交付物统一整理到 `paper1_veriedge/E1|E2|E4|E5/`。
6. 修改共享配置或公共脚本时，必须同步更新对应文档。
7. 如需扩展 E5，只优先沿用 `artifacts/inference-E2E/` 这条 orchestration 路线；没有明确要求，不引入定价/福利导向的新实验。
