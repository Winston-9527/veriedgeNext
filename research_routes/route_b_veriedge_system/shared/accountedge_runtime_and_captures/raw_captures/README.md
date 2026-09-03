# Raw Capture Subset

This directory contains an anonymized subset of real checkpoint captures. The
subset is intentionally small enough to keep the review repository lightweight
while exposing the raw capture schema used by the verifier pipeline.

## Included Data

- `e2_live_subset/stack_01_calib_6/`: calibration captures for one anonymous
  heterogeneous stack.
- `e2_live_subset/stack_02_calib_6/`: calibration captures for a second
  anonymous heterogeneous stack.
- `e2_live_subset/stack_01_eval_12/`: evaluation captures for stack 1.
- `e2_live_subset/stack_02_eval_12/`: evaluation captures for stack 2.
- `e2_live_subset/stack_02_rerun_eval_12/`: same-stack rerun captures used to
  expose the replay/negative-control schema.

Each `.npz` file stores checkpoint tensors with keys:

- `prefill__C1`
- `prefill__C2`
- `prefill__C3`

The tensors are prefill checkpoint activations with shape
`batch x tokens x hidden`. The prompts are not included; only prompt IDs,
checkpoint metadata, tensor shapes, and activation tensors are included.

## Anonymization

The original host names, user paths, SSH identities, and machine labels were
removed. Provider labels are replaced by role-like anonymous labels such as
`provider_c1_mps_quant`, `provider_c2_mps_bf16`, and `provider_c3_cuda_fp32`.
Backend/device class labels are retained because they are part of the measured
heterogeneity setting.

## Validate

From the repository root:

```bash
python scripts/validate_raw_captures.py
```

This checks that every capture listed in `manifest.json` exists, has the
expected checkpoint keys, and contains numeric tensors.

## Scope

This is not the full raw-capture corpus. The full corpus is much larger and is
represented in the artifact by measured summary CSVs under `data/`. This subset
is included so reviewers can inspect the raw checkpoint-capture format and run
small verifier/debugging checks without downloading model weights.

