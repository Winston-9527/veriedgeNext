#!/usr/bin/env python3
"""Re-organize the 720-prompt capture pool into the PACT-offline data layout.

The ``pact_offline`` stack loaders (``pcra_offline.load_pairs`` /
``calibration_audit.load_stack_pair``) expect a specific layout: two stacks whose
directory names start with ``stack_01_`` (reference) and ``stack_02_`` (candidate),
``calib_<seq>.npz`` / ``eval_<seq>.npz`` file prefixes, and *identical* filenames
on both sides.  The raw 720 pool uses ``stack_a_720`` / ``stack_b_720`` with
``<prompt_id>.npz`` filenames and an external split file, so it cannot be fed in
directly.

This script performs the rename-only re-organization (no change to tensor
contents).  Honest naming: directory names carry the split, not the sample count
(``stack_01_calib`` not ``stack_01_calib_200``).

Input  (--src):   <captures_720>/{stack_a_720,stack_b_720}/captures/<prompt_id>.npz
                  <prompts.jsonl>  (200 calibration / 520 evaluation)
Output (--out):   <captures_720_pact>/stack_01_calib/captures/calib_001.npz … calib_200.npz
                  <captures_720_pact>/stack_02_calib/captures/calib_001.npz … calib_200.npz
                  <captures_720_pact>/stack_01_eval/captures/eval_001.npz  … eval_520.npz
                  <captures_720_pact>/stack_02_eval/captures/eval_001.npz  … eval_520.npz
                  <captures_720_pact>/PROMPT_ID_MAP.csv        (split,seq,prompt_id)
                  <captures_720_pact>/manifest.json            (bytes,file,sha256,stack)
                  per-stack capture_summary.json + captures/checkpoint_metadata.jsonl

Usage:
    python3 build_pact_calibration_subset.py \
        --src <captures_720> --prompts <qwen_prompt_splits...jsonl> \
        --out <captures_720_pact> [--rerun <stack_b_rerun_dir>]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np


CHECKPOINTS = ("C1", "C2", "C3")
NPZ_KEYS = ("prefill__C1", "prefill__C2", "prefill__C3")
PROVIDER_PLAN = ["provider_c1", "provider_c2", "provider_c3"]
RUNTIME = "heterogeneous_checkpoint_capture"
# (split name in jsonl, file/label prefix)
SPLITS = (("calibration", "calib"), ("evaluation", "eval"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_split_ids(prompts_path: Path) -> dict[str, list[str]]:
    """Return {jsonl split -> [prompt_id, ...]} in file order."""
    ids: dict[str, list[str]] = {}
    for line in prompts_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ids.setdefault(row["split"], []).append(row["prompt_id"])
    return ids


def _validate_npz(path: Path) -> list[int]:
    with np.load(path) as capture:
        if tuple(sorted(capture.files)) != tuple(sorted(NPZ_KEYS)):
            raise ValueError(f"{path}: unexpected keys {sorted(capture.files)}")
        shape = list(capture[NPZ_KEYS[0]].shape)
        for key in NPZ_KEYS:
            if list(capture[key].shape) != shape:
                raise ValueError(f"{path}: key {key} shape mismatch")
    return shape


def copy_stack(
    src_stack: Path, out_root: Path, stack_dir: str, label: str, split: str,
    prompt_ids: list[str],
) -> tuple[list[dict], list[dict]]:
    """Copy one stack's capture files under the numbered naming. Returns (summary, meta)."""
    dst_stack = out_root / stack_dir
    (dst_stack / "captures").mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []
    meta: list[dict] = []
    for seq, prompt_id in enumerate(prompt_ids, start=1):
        src_npz = src_stack / "captures" / f"{prompt_id}.npz"
        if not src_npz.is_file():
            raise FileNotFoundError(src_npz)
        shape = _validate_npz(src_npz)
        new_id = f"{label}_{seq:03d}"
        dst_npz = dst_stack / "captures" / f"{new_id}.npz"
        shutil.copy2(src_npz, dst_npz)
        rel = dst_npz.relative_to(out_root.parent).as_posix()
        meta_path = f"{out_root.name}/{stack_dir}/captures/checkpoint_metadata.jsonl"
        for ckpt in CHECKPOINTS:
            meta.append(
                {
                    "checkpoint": ckpt,
                    "decode_step": 0,
                    "prompt_id": new_id,
                    "provider_plan": PROVIDER_PLAN,
                    "runtime": RUNTIME,
                    "shape": shape,
                    "split": split,
                    "stage": "prefill",
                    "stage_key": "prefill",
                    "tensor_dtype": "float32",
                }
            )
        summary.append(
            {
                "decode_steps": 0,
                "metadata_path": meta_path,
                "npz_path": rel,
                "prompt_id": new_id,
                "provider_plan": PROVIDER_PLAN,
                "runtime": RUNTIME,
                "split": split,
            }
        )
    (dst_stack / "capture_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (dst_stack / "captures" / "checkpoint_metadata.jsonl").open("w", encoding="utf-8") as fh:
        for row in meta:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return summary, meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, required=True, help="raw captures_720 dir")
    parser.add_argument("--prompts", type=Path, required=True, help="prompt split jsonl")
    parser.add_argument("--out", type=Path, required=True, help="output captures_720_pact dir")
    parser.add_argument("--ref-stack", default="stack_a_720")
    parser.add_argument("--cand-stack", default="stack_b_720")
    parser.add_argument("--rerun", type=Path, default=None,
                        help="optional same-stack re-capture dir (candidate side) for rerun")
    args = parser.parse_args()

    split_ids = load_split_ids(args.prompts)
    if args.out.exists():
        raise FileExistsError(f"{args.out} already exists; refusing to overwrite")

    for stack in (args.ref_stack, args.cand_stack):
        if not (args.src / stack / "captures").is_dir():
            raise FileNotFoundError(f"stack captures not found: {args.src / stack / 'captures'}")

    manifest_files: list[dict] = []
    id_map: list[dict] = []

    for split, label in SPLITS:
        prompt_ids = split_ids.get(split, [])
        if not prompt_ids:
            raise ValueError(f"no prompts for split {split!r} in {args.prompts}")
        for stack_no, stack_dir in ((1, args.ref_stack), (2, args.cand_stack)):
            dst = f"stack_{stack_no:02d}_{label}"
            summary, _ = copy_stack(args.src / stack_dir, args.out, dst, label, split, prompt_ids)
            for row in summary:
                path = args.out.parent / row["npz_path"]
                manifest_files.append(
                    {"bytes": path.stat().st_size, "file": row["npz_path"],
                     "sha256": sha256(path), "stack": dst}
                )
        for seq, prompt_id in enumerate(prompt_ids, start=1):
            id_map.append({"split": split, "seq": seq, "prompt_id": prompt_id})

    if args.rerun is not None:
        if not (args.rerun / "captures").is_dir():
            raise FileNotFoundError(f"rerun captures not found: {args.rerun / 'captures'}")
        rerun_ids = split_ids["evaluation"]
        copy_stack(args.rerun, args.out, "stack_02_rerun_eval", "eval", "evaluation", rerun_ids)

    with (args.out / "PROMPT_ID_MAP.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["split", "seq", "prompt_id"])
        writer.writeheader()
        writer.writerows(id_map)

    (args.out / "manifest.json").write_text(
        json.dumps({"files": manifest_files}, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(
        {"out": str(args.out), "n_files": len(manifest_files),
         "split_counts": {s: len(split_ids[s]) for s, _ in SPLITS}},
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
