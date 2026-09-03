# Figure Index

## 主图

| Figure | 文件 | 论文用途 |
|---|---|---|
| Figure A1a | `fig_placement_frontier_a1.png` / `.pdf` | A1 controlled replay frontier，展示 placement-time verifiability constraint 的主效果 |
| Figure A1b | `fig_placement_frontier_a3_queue.png` / `.pdf` | A3 queue-aware frontier，展示 busy queue scoring 后仍需要 verifier constraint |
| Figure A2 | `fig_risk_class_composition.png` / `.pdf` | 展示各 policy 选中 placement 的 low-risk / infeasible 组成 |
| Figure A3 | `fig_alpha_sensitivity_infeasible.png` / `.pdf` | 展示 alpha sweep 下 infeasible rate 是否稳定 |

## 读图顺序

1. 先看 Figure A1a：回答 A1 主问题，即 measured verifier profile 是否能改变 placement frontier。
2. 再看 Figure A2：解释为什么 frontier 改变，核心是 infeasible signature 被过滤或升级。
3. 再看 Figure A3：说明结论不只依赖 `alpha=0.10` 单点。
4. 最后看 Figure A1b：说明 queue-aware scoring 能改善 latency/goodput，但不能替代 verifier constraint。

## 图片版本

- `.png` 用于 Markdown 阅读和展示。
- `.pdf` 用于论文排版和矢量图引用。
