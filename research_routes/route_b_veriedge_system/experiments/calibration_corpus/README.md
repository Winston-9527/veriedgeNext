# calibration_corpus — 720 池 → PACT-offline 适配

把 720 池（200 calib / 520 eval）适配到 `pact_offline` 的 stack 加载器，并回答"C3 尾部需要多少校准样本"。

对应工单 `docs/2026-09-10_ROUTE_B_CODE_UPDATE_WORKTICKETS` / `..._CODE_UPDATE_WORKTICKET.md`。

## 脚本

### `build_pact_calibration_subset.py`（CU-2 数据重组）

把 `<captures_720>/{stack_a_720,stack_b_720}/captures/<prompt_id>.npz` 重组为加载器可读的布局（仅重命名，不改张量内容）：

```
<captures_720_pact>/
  stack_01_calib/captures/calib_001.npz … calib_200.npz   # ref  = stack_a_720
  stack_02_calib/captures/calib_001.npz … calib_200.npz   # cand = stack_b_720
  stack_01_eval/captures/eval_001.npz  … eval_520.npz
  stack_02_eval/captures/eval_001.npz  … eval_520.npz
  PROMPT_ID_MAP.csv       # split,seq,prompt_id
  manifest.json           # bytes,file,sha256,stack
  <each stack>/capture_summary.json + captures/checkpoint_metadata.jsonl
```

```bash
python3 build_pact_calibration_subset.py \
    --src <captures_720> \
    --prompts <qwen_prompt_splits_stratified_v2_200_500.jsonl> \
    --out <captures_720_pact>
```

可选 `--rerun <同一 cand 栈的重跑捕获目录>` 生成 `stack_02_rerun_eval/`（供 `calibration_audit.py` 的同栈自差比对）。

### `sample_size_vs_fpr.py`（CU-2 样本量分析）

在 `calibration_audit.py` 产出的 `energy_by_prompt.csv` 上，对每个 checkpoint 子采样校准集 n∈{30,…,200}，测评估集实测 FPR + 单侧 95% 上界，判定 C3 尾部是否随 n 收敛。

```bash
python3 ../pact_offline/calibration_audit.py \
    --data-root <captures_720_pact> --output <audit_out> --skip-rerun
python3 sample_size_vs_fpr.py \
    --energy-csv <audit_out>/energy_by_prompt.csv --out <out>
```

输出 `sample_size_vs_fpr.{csv,json,png}`，`verdict_by_checkpoint` ∈ {PASS, FAIL, INCONCLUSIVE}。

## 契约（加载器要求）

- 目录名 `stack_01_*` = ref（stack_a）、`stack_02_*` = cand（stack_b）。
- 文件名前缀 `calib_` / `eval_`，两侧**逐字相同**（否则 `load_pairs` 抛 Unmatched）。
- npz 键 = `prefill__C1/C2/C3`，`(1, T, 1024)`，float32。
- 目录名**不嵌样本数**（诚实命名）；加载器 `resolve_stack_dir` 仍兼容旧的 `_6`/`_12` 后缀（`e2_live_subset` 不受影响）。
