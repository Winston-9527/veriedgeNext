#!/usr/bin/env python3
"""Validate the expanded 720-prompt heterogeneous capture pool.

Checks the raw capture layout produced for the 720-pool experiments:

    <root>/stack_a_720/captures/<prompt_id>.npz   # reference  (Apple MPS bf16)
    <root>/stack_b_720/captures/<prompt_id>.npz   # candidate  (RTX6000 CUDA fp32)
    <prompts.jsonl>                               # 200 calibration / 520 evaluation

Per file: exactly keys {prefill__C1, prefill__C2, prefill__C3}, each a 3D
``(1, T, 1024)`` float32 tensor.  Also records the prompt-file sha256 and the
calibration/evaluation split counts, so the run is a fingerprint check for the
720 pool rather than a shape-only smoke test.

Usage:
    python3 validate_raw_captures_720.py \
        --root <captures_720> --prompts <qwen_prompt_splits...jsonl>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


EXPECTED_KEYS = {"prefill__C1", "prefill__C2", "prefill__C3"}
STACKS = ("stack_a_720", "stack_b_720")
HIDDEN_DIM = 1024
EXPECTED_SPLITS = {"calibration": 200, "evaluation": 520}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_capture(path: Path) -> dict:
    with np.load(path) as capture:
        keys = set(capture.files)
        if keys != EXPECTED_KEYS:
            raise ValueError(f"{path}: keys {sorted(keys)} != {sorted(EXPECTED_KEYS)}")
        shapes = {}
        for key in sorted(keys):
            tensor = capture[key]
            if tensor.ndim != 3:
                raise ValueError(f"{path}:{key} expected 3D, got {tensor.shape}")
            if tensor.dtype != np.float32:
                raise ValueError(f"{path}:{key} dtype {tensor.dtype} != float32")
            if tensor.shape[0] != 1 or tensor.shape[2] != HIDDEN_DIM:
                raise ValueError(f"{path}:{key} shape {tensor.shape} != (1, T, {HIDDEN_DIM})")
            shapes[key] = list(tensor.shape)
    return shapes


def load_prompts(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="captures_720 directory")
    parser.add_argument("--prompts", type=Path, required=True, help="prompt split jsonl")
    parser.add_argument("--expected-per-stack", type=int, default=720)
    args = parser.parse_args()

    report: dict[str, object] = {"root": str(args.root), "stacks": {}, "prompts": {}}

    stack_ids: set[str] | None = None
    for stack in STACKS:
        cap_dir = args.root / stack / "captures"
        if not cap_dir.is_dir():
            raise FileNotFoundError(f"missing capture dir: {cap_dir}")
        files = sorted(cap_dir.glob("*.npz"))
        if len(files) != args.expected_per_stack:
            raise ValueError(
                f"{stack}: {len(files)} files, expected {args.expected_per_stack}"
            )
        ids = {path.stem for path in files}
        if stack_ids is None:
            stack_ids = ids
        elif ids != stack_ids:
            raise ValueError(f"{stack}: prompt-id set differs from {STACKS[0]}")
        for path in files:
            validate_capture(path)
        report["stacks"][stack] = {"n_files": len(files)}

    prompts = load_prompts(args.prompts)
    split_counts: dict[str, int] = {}
    for row in prompts:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
    prompt_ids = {row["prompt_id"] for row in prompts}

    ids_match = prompt_ids == stack_ids
    splits_ok = all(split_counts.get(name) == n for name, n in EXPECTED_SPLITS.items())
    report["prompts"] = {
        "sha256": sha256(args.prompts),
        "n": len(prompts),
        "split_counts": split_counts,
        "ids_match_stacks": ids_match,
    }
    report["verdict"] = "PASS" if (ids_match and splits_ok) else "FAIL"

    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
