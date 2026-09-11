# VeriEdge Paper1 EXO-Free Experiment Runbook

## 1. Why This Runbook Exists

`eurosys_draft_v13.pdf` and `实验手册.pdf` make it clear that the current paper still lacks four key experiments:

- `E1`: real heterogeneous honest-honest paired capture
- `E2`: TSTC ablation
- `E4`: verifier operational overhead
- `E5`: verification-aware placement comparison

The original draft still presents the prototype as "implemented on top of EXO", but the current workspace already contains enough evidence that `EXO` is not a reliable primary path for these four missing experiments, especially when Linux GPU participation and stable checkpoint capture are required.

This runbook therefore adopts the following rule:

- `E1/E2/E4` use the existing `strict T3/T5` Torch-based heterogeneous shard path, not EXO.
- `E5` is treated as a trace-driven orchestration study. EXO can remain as an optional side reference, but not as the critical path.

In one sentence:

- the paper still mentions EXO as the original prototype substrate;
- the missing evidence chain should now be completed on top of the repository's own capture-and-verifier toolchain.

## 2. Global Decision

### 2.1 Main experimental route

Use the repository's native heterogeneous execution path:

- `artifacts/thc/scripts/t3_hetero_cli.py`
- `artifacts/thc/T3_hetero_runbook.md`
- `artifacts/thc/src/run.py`
- `artifacts/thc/src/overhead_report.py`

This path already supports:

- fixed 3-shard execution
- explicit `C1/C2/C3` checkpoint capture
- `torch+mps` on Mac
- `torch+cuda` on Linux
- reproducible `THC/TSTC` replay on captured bundles

### 2.2 What EXO is still allowed to do

EXO is now secondary, not primary.

Allowed roles:

- keeping the paper's prototype narrative consistent
- providing already measured deployment-path reference numbers
- optionally serving as a Mac-only control-plane side experiment for `E5`

Not allowed as the blocking dependency for:

- `E1` real paired capture
- `E2` ablation
- `E4` overhead
- Linux-participating `E5`

## 3. Shared Experimental Baseline

### 3.1 Hardware baseline

Recommended baseline, matching the current repository:

- `jlmini_3`: Mac mini M4, `torch+mps`, first shard, `C1`
- `linux124`: Linux + RTX3090, `torch+cuda`, middle shard, `C2`
- `jlmini_2`: Mac mini M4, `torch+mps`, last shard, `C3`

Default cluster file:

- `artifacts/thc/config/hetero_qwen_cluster.json`

### 3.2 Shared model and shard plan

Use one fixed execution plan for all four experiments unless a run explicitly studies placement variation:

- model family: `Qwen/Qwen3-0.6B`
- shard 1: layers `0-7`, checkpoint `C1`
- shard 2: layers `8-15`, checkpoint `C2`
- shard 3: layers `16-23`, checkpoint `C3`

If shard boundaries change, all of the following must be updated together:

- cluster JSON
- notes
- pairwise comparison table labels
- overhead table labels
- paper text

### 3.3 Split discipline

This project must enforce a hard split between calibration and evaluation:

- `calibration` is only for estimating `delta_map`
- `evaluation` is only for final reported verifier results

Never reuse the same prompts or the same capture roots across these two roles.

### 3.4 Shared output layout

Recommended layout:

- `paper1_veriedge/E1/logs/`
- `paper1_veriedge/E1/tables/`
- `paper1_veriedge/E1/notes/`
- `paper1_veriedge/E2/logs/`
- `paper1_veriedge/E4/logs/`
- `paper1_veriedge/E5/logs/`
- raw capture roots outside git, e.g. `workspace/captures/E1/` or `/tmp/thc_t3/...`

Do not commit large `.npz` capture bundles into the paper workspace.

## 4. EXO-Free Plan for Each Missing Experiment

## 4.1 E1: Real heterogeneous honest-honest paired capture

### Goal

Show that `TSTC` reduces false positives on real heterogeneous honest executions, not only on synthetic heterogeneity.

### EXO-free route

Do not use EXO distributed runtime.

Use:

- `artifacts/thc/scripts/run_t3_hetero_server.sh`
- `artifacts/thc/scripts/run_t3_hetero_capture.sh`
- `artifacts/thc/scripts/run_t3_delta_calibration.sh`
- `artifacts/thc/scripts/run_t5_from_capture.sh`

Core idea:

1. run real shard execution through the HTTP-based Torch chain
2. capture `C1/C2/C3` on all prompts
3. build a real `delta_map` from calibration roots
4. run evaluation on held-out roots
5. compare matched honest traces pairwise under both `THC` and `TSTC`

### Inputs

- real calibration capture roots
- real evaluation capture roots
- one fixed shard plan
- one fixed prompt split file

### Outputs

- `exp_e1_<date>_<owner>_summary.csv`
- `exp_e1_<date>_<owner>_pairwise_details.csv`
- `notes/e1_run_notes.md`

### Key reporting fields

- device/backend pair
- prompt id
- checkpoint
- THC detected or not
- TSTC detected or not
- mismatch stage/checkpoint
- honest-honest localization: `N/A`

## 4.2 E2: TSTC ablation

### Goal

Show that sampling and tolerance are interpretable operating-point choices, not ad hoc tuning.

### EXO-free route

Reuse outputs from `E1`.

No EXO runtime is needed. This is an offline verifier experiment.

Recommended sources:

- real evaluation capture roots from `E1`
- real `delta_map.json` from `T3`
- optional synthetic tamper traces generated by `run.py`
- optional controlled perturbation sweep via `artifacts/TSTC/run_noise_sweep.py`

### Minimal sweep set

- sample size: `4, 8, 16, 32, 64`
- tolerance scale: `0.5x, 1x, 1.5x, 2x`
- checkpoint-specific tolerance vs one global tolerance

### Outputs

- `exp_e2_<date>_<owner>_samplesweep.csv`
- `exp_e2_<date>_<owner>_tolerancesweep.csv`
- `exp_e2_<date>_<owner>_runtime.csv`
- `notes/e2_ablation_notes.md`

## 4.3 E4: verifier operational overhead

### Goal

Turn the verifier from "detects attacks" into "is operationally discussable in a systems paper".

### EXO-free route

Reuse real capture roots from `E1`.

Run:

- `artifacts/thc/src/overhead_report.py`

This already computes structured size, runtime, and storage rows from capture bundles and replayed traces.

### Minimum trace classes

- honest trace
- challenged honest trace
- tamper trace or failed challenge trace

### Outputs

- `exp_e4_<date>_<owner>_size_breakdown.csv`
- `exp_e4_<date>_<owner>_latency_breakdown.csv`
- `exp_e4_<date>_<owner>_storage_breakdown.csv`
- `exp_e4_<date>_<owner>_summary.csv`

## 4.4 E5: verification-aware placement comparison

### Goal

Show that VeriEdge is an orchestration paper, not only a verifier paper.

### EXO-free route

Treat `E5` as a policy comparison over measured traces, not as a dependence on live EXO scheduling.

The recommended route is:

1. use already measured deployment-path observations from Section 6.1 as base cost signals
2. import heterogeneity-risk signals from `E1`
3. import verifier workload and challenge cost from `E4`
4. run a trace-driven policy replay or simulator

EXO may still be kept as:

- an optional Mac-only side experiment
- a source of existing deployment reference numbers

But the primary `E5` claim should no longer depend on EXO being stable on all platforms.

### Minimum policy set

- `random`
- `cost_only`
- `reputation_aware`
- `network_aware`
- `verification_aware`

### Minimum metrics

- task latency
- success rate
- challenge rate
- verifier workload
- goodput

### Outputs

- `exp_e5_<date>_<owner>_policy_compare.csv`
- `exp_e5_<date>_<owner>_policy_config.json`
- `notes/e5_policy_notes.md`

## 5. Detailed E1 Execution Method

This is the most important section of this runbook.

## 5.1 E1 Claim and Scope

`E1` is not trying to prove full semantic equivalence of all outputs.

It only needs to support the paper's verification claim:

- under matched honest executions on real heterogeneous devices and backends,
- `THC` is too brittle,
- `TSTC` materially lowers false alarms.

Therefore `E1` should be organized as a checkpoint-trace comparison study, not as an end-to-end product benchmark.

## 5.2 E1 Required Evidence Chain

`E1` should produce the following chain:

1. real heterogeneous shard execution runs successfully without EXO
2. the same prompts can be replayed under multiple honest backend/device combinations
3. the resulting checkpoint traces can be aligned prompt-by-prompt and checkpoint-by-checkpoint
4. `THC` and `TSTC` are both run on the exact same paired traces
5. the final table reports `THC FPR` vs `TSTC FPR` for each real pair

If any one of these links is missing, the experiment is incomplete.

## 5.3 E1 Recommended Pair Design

At least three real pairs should be reported.

Recommended pair labels, matching the draft's current table slots:

- `M4/Metal-int8 vs M4/BF16`
- `M4/Metal-int8 vs RTX3090/BF16`
- `M4/BF16 vs RTX3090/FP32`

Practical rule:

- keep the shard plan fixed
- change only the backend/device realization used to produce the matched trace
- keep prompt IDs, split, and run order aligned

If exact BF16 or FP32 support differs on your machines, record the actual backend precisely in notes and use that exact wording in the table.

## 5.4 E1 Phase A: Prepare the environment

On all three machines:

1. sync the same repository revision
2. keep the same relative path layout
3. confirm Python environment
4. confirm model availability
5. confirm network reachability between shard servers

Use the existing environment checker:

```bash
LOCAL_NODE=jlmini_2 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/check_t3_hetero_env.sh
```

Run the same command with:

- `LOCAL_NODE=jlmini_2`
- `LOCAL_NODE=jlmini_3`
- `LOCAL_NODE=linux124`

Exit criteria:

- all nodes pass import checks
- Mac nodes expose `mps`
- Linux node exposes `cuda`

## 5.5 E1 Phase B: Start the real shard chain

On the three machines, start one shard server each:

```bash
LOCAL_NODE=jlmini_2 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/run_t3_hetero_server.sh
```

```bash
LOCAL_NODE=jlmini_3 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/run_t3_hetero_server.sh
```

```bash
LOCAL_NODE=linux124 \
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
bash artifacts/thc/scripts/run_t3_hetero_server.sh
```

Do not close these terminals before capture finishes.

Record in notes:

- node name
- device
- dtype
- quantization
- host:port

## 5.6 E1 Phase C: Build calibration roots

On the coordinator:

```bash
CLUSTER_FILE=artifacts/thc/config/hetero_qwen_cluster.json \
OUTPUT_DIR=/tmp/thc_t3/e1_calib_run_a \
SPLIT=calibration \
LIMIT_PROMPTS=0 \
bash artifacts/thc/scripts/run_t3_hetero_capture.sh
```

Repeat at least three times:

- `/tmp/thc_t3/e1_calib_run_a`
- `/tmp/thc_t3/e1_calib_run_b`
- `/tmp/thc_t3/e1_calib_run_c`

Each root should contain:

- `captures/<prompt_id>.npz`
- `checkpoint_metadata.jsonl`
- `capture_summary.json`

## 5.7 E1 Phase D: Calibrate the real delta map

Use only calibration roots:

```bash
bash artifacts/thc/scripts/run_t3_delta_calibration.sh \
  /tmp/thc_t3/e1_delta_main \
  /tmp/thc_t3/e1_calib_run_a \
  /tmp/thc_t3/e1_calib_run_b \
  /tmp/thc_t3/e1_calib_run_c
```

Core output:

- `/tmp/thc_t3/e1_delta_main/delta_map.json`

This file is the only delta source allowed in final `E1/E2/E4`.

## 5.8 E1 Phase E: Build evaluation roots

Now switch to held-out prompts.

For each real backend/device variant you want to compare, run one or more evaluation capture roots with:

```bash
CLUSTER_FILE=<variant_cluster_file.json> \
OUTPUT_DIR=/tmp/thc_t3/e1_eval_<variant_name>_run_a \
SPLIT=evaluation \
LIMIT_PROMPTS=0 \
bash artifacts/thc/scripts/run_t3_hetero_capture.sh
```

Important rule:

- each variant must use the same prompt IDs
- each variant must use the same shard boundaries
- only backend/device realization should differ

Recommended naming:

- `e1_eval_m4metal_vs_m4bf16_side_a_run_a`
- `e1_eval_m4metal_vs_m4bf16_side_b_run_a`
- `e1_eval_m4metal_vs_rtxbf16_side_a_run_a`
- `e1_eval_m4metal_vs_rtxbf16_side_b_run_a`

The exact names can differ, but the pair structure must be obvious from directory names alone.

## 5.9 E1 Phase F: Construct pairwise comparisons

This is the key analytical step.

For each pair:

1. align the two evaluation roots by `prompt_id`
2. load the paired bundles for the same prompt
3. compare the two bundles under `THC`
4. compare the same two bundles under `TSTC`, using `e1_delta_main/delta_map.json`
5. record whether the pair is flagged as mismatch

What counts as one trial:

- one `prompt_id`
- one pair label
- one verifier mode

What counts as one summary row:

- one pair label
- one verifier mode
- aggregated honest-honest FPR over all matched prompts

If the current repository lacks a one-shot pairwise driver for this exact `E1` table, implement the comparison as a small offline evaluator on top of the existing bundle loader and hash-chain utilities, rather than trying to force EXO back into the pipeline.

Existing modules to reuse:

- `artifacts/thc/src/checkpoint_qwen.py`
- `artifacts/thc/src/hash_chain.py`
- `artifacts/thc/src/calibrate_delta.py`

## 5.10 E1 Phase G: Produce the two deliverables

### Summary table

`exp_e1_<date>_<owner>_summary.csv`

Recommended columns:

- `pair_label`
- `pair_side_a`
- `pair_side_b`
- `prompt_count`
- `thc_fpr`
- `tstc_fpr`
- `dominant_mismatch_checkpoint`
- `notes`

### Pairwise detail table

`exp_e1_<date>_<owner>_pairwise_details.csv`

Recommended columns:

- `pair_label`
- `prompt_id`
- `checkpoint_scope`
- `thc_detected`
- `tstc_detected`
- `thc_first_mismatch_checkpoint`
- `tstc_first_mismatch_checkpoint`
- `localization_label`
- `side_a_capture_root`
- `side_b_capture_root`

For honest-honest rows:

- `localization_label = N/A`

## 5.11 E1 Phase H: Write-back to the draft

The paper only needs a compact final statement:

- `THC` collapses on real heterogeneous honest-honest pairs
- `TSTC` preserves a usable false-positive operating point
- the effect is observed on real backend/device combinations, not only synthetic perturbation

Do not overload the main text with raw operational details.

Put those details in:

- notes
- appendix
- artifact description

## 5.12 E1 Failure checklist

Stop and rerun if any of the following happens:

- calibration and evaluation prompts are mixed
- shard plan differs across pair sides
- capture roots are overwritten or mixed
- pair labels hide the real backend difference
- only `TSTC` is reported but `THC` baseline is missing
- results are presented only as screenshots without raw CSV

## 6. Fast Mapping From Experiment To Existing Repository Tools

| Experiment | Primary route | Existing code |
| --- | --- | --- |
| `E1` | real hetero capture + pairwise offline compare | `artifacts/thc/scripts/t3_hetero_cli.py`, `artifacts/thc/src/hash_chain.py` |
| `E2` | offline ablation on real capture roots | `artifacts/thc/src/run.py`, `artifacts/TSTC/run_noise_sweep.py` |
| `E4` | offline overhead extraction on capture roots | `artifacts/thc/src/overhead_report.py` |
| `E5` | trace-driven policy replay / simulator | reuse `Section 6.1` numbers + `E1/E4` outputs |

## 7. Bottom Line

Given the current repository state, the most realistic path is:

1. finish `E1` on the non-EXO Torch shard chain
2. let `E2` and `E4` reuse `E1` artifacts
3. let `E5` consume measured traces instead of waiting for EXO to become stable

That path is narrower than the original prototype story, but it is much stronger for the actual missing claims in the paper.
