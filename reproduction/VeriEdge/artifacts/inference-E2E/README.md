# inference-E2E 目录说明

该目录用于承载 `BC-RA + EXO` 的端到端可行性实验代码与说明。

当前默认边界是 `黑盒 EXO`：

- 三台 Mac mini 上的 EXO 由外部预先启动并保持运行。
- 本目录中的实验代码不负责创建、删除、升级或修复 EXO instance。
- requester 侧只做黑盒校验、任务构造、IPFS 分发、first-shard 下发、callback 聚合与结果导出。

目录结构：

- `artifacts/inference-E2E/requester/`：requester 侧实验编排、Kubo 管理、freeze 采集与校验
- `artifacts/inference-E2E/provider/`：provider 侧 launcher、健康检查与辅助脚本
- `artifacts/inference-E2E/lib/`：共享工具函数
- `artifacts/inference-E2E/freeze/`：外部 EXO 与 Nix/Python 版本快照清单
- `artifacts/inference-E2E/exp_exo.md`：当前实验方案说明

快速入口：

1. 先阅读 `artifacts/inference-E2E/exp_exo.md`
2. provider 侧准备见 `artifacts/inference-E2E/provider/README.md`
3. requester 侧运行见 `artifacts/inference-E2E/requester/README.md`
