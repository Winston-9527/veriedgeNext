# Optional Data Collection Scripts

This directory contains anonymized, reviewer-facing data-collection scripts.
They are provided to show how verifier-profile CSVs can be collected from model
checkpoint captures. The included artifact figures still use the measured CSVs
under `data/`; reviewers do not need to rerun model inference to reproduce the
paper figures.

## Hugging Face Model Collection

Install optional dependencies in a separate environment:

```bash
pip install -r data_collection/requirements-hf.txt
```

Then run a small collection job. The model ID is configurable. For a compact
Qwen-family smoke run, one possible command is:

```bash
python data_collection/collect_hf_verifier_profiles.py \
  --backend hf \
  --model-id Qwen/Qwen3-0.6B \
  --out-dir data_collection/out_hf_smoke \
  --max-prompts 6 \
  --max-length 64
```

The first run downloads the model through Hugging Face's normal cache. If the
chosen model is gated or unavailable in the reviewer's region, replace
`--model-id` with another small causal language model.

## Fast Schema Smoke Test

To verify the collection pipeline without downloading model weights:

```bash
python data_collection/collect_hf_verifier_profiles.py \
  --backend synthetic \
  --out-dir data_collection/out_synthetic_smoke
```

Both modes write:

- `captures.npz`: compact checkpoint tensors for the smoke collection.
- `verifier_profiles_collected.csv`: profile-like FPR/TPR/sketch rows.
- `collection_summary.json`: run metadata and output paths.

## Scope

This is not the original multi-node hardware deployment. It is an anonymized
single-machine collection harness that mirrors the checkpoint-capture,
sketching, tolerance calibration, and held-out FPR/TPR reporting path. Hardware
heterogeneity, device placement, network latency, and production orchestration
are represented in the artifact by the measured CSVs and replay logs under
`data/`.

