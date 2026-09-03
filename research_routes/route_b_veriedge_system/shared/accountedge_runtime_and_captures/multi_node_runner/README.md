# Multi-Node Collection Runner

This directory contains anonymized runner templates for collecting checkpoint
captures on multiple devices. The templates are included for transparency and
for authors/reviewers who have comparable devices. They are not required to
reproduce the included figures, which are regenerated from measured CSVs under
`data/`.

## Files

- `env.example`: environment variables for a generic three-provider deployment.
- `device_matrix.example.yaml`: anonymous provider roles and backend classes.
- `run_remote_collection.py`: dry-run-first SSH/rsync coordinator template.

## Workflow

1. Copy `env.example` to `.env` and replace host placeholders with your own
   machines.
2. Ensure each machine can run Python, PyTorch, Transformers, and the selected
   Hugging Face model.
3. Run a dry-run plan:

```bash
python multi_node_runner/run_remote_collection.py --env .env --dry-run
```

4. If the commands look correct, run with `--execute`.

The runner intentionally uses placeholders and local paths such as
`/tmp/veriedge_remote_capture` to avoid embedding author-specific paths,
hostnames, or usernames in the repository.

## Model

The original experiments used a compact Qwen-family causal language model. A
reviewer can use a comparable Hugging Face model, for example:

```text
Qwen/Qwen3-0.6B
```

Model availability may depend on Hugging Face network access and local hardware.

