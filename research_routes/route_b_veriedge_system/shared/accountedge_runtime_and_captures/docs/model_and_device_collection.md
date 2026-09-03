# Model and Device Collection Notes

This document describes how the raw checkpoint captures and measured verifier
profiles relate to a reviewer-run collection.

## Model

Use a compact causal language model available from Hugging Face. The artifact
examples use the following configurable default:

```text
Qwen/Qwen3-0.6B
```

The exact model download is not bundled in this repository. Reviewers should
download it through the standard Hugging Face cache used by Transformers.

## Device Roles

The capture schema is based on three checkpoint roles:

- `C1`: first checkpoint role;
- `C2`: second checkpoint role;
- `C3`: third checkpoint role.

The anonymized raw subset retains backend/device classes such as MPS-like,
quantized MPS-like, and CUDA-like execution because those classes are
scientifically relevant. It removes author-specific hostnames, IP addresses,
SSH users, and local paths.

## Captures

The raw subset under `raw_captures/e2_live_subset/` contains real `.npz`
checkpoint tensors with keys `prefill__C1`, `prefill__C2`, and `prefill__C3`.
The full internal raw corpus is larger; the artifact uses measured summary CSVs
for the paper figures and includes this subset to expose the raw schema.

## Recollection Path

For single-machine recollection, use:

```bash
python data_collection/collect_hf_verifier_profiles.py --backend hf --model-id Qwen/Qwen3-0.6B
```

For multi-device recollection, use the template runner:

```bash
cp multi_node_runner/env.example .env
python multi_node_runner/run_remote_collection.py --env .env --dry-run
```

After replacing placeholders with reviewer-local machines, use `--execute`.

