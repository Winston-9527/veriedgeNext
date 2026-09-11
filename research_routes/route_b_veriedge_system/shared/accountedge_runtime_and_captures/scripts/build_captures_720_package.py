#!/usr/bin/env python3
"""Build the 720-pool distribution package (for W1/W2 download).

Layout (see docs/2026-09-10_ROUTE_B_NEXT_WORKTICKETS.md, "720 池压缩包约定"):

    captures_720/
      stack_a_720/captures/<prompt_id>.npz   # 720, Apple MPS bf16 (reference)
      stack_b_720/captures/<prompt_id>.npz   # 720, RTX6000 CUDA fp32 (candidate)
      qwen_prompt_splits_stratified_v2_200_500.jsonl
      PACKAGE_MANIFEST.csv                    # path,bytes,sha256 (every file)
      README.md                               # provenance / backends / fingerprints

Usage:
    python3 build_captures_720_package.py \
        --src <captures_720> --prompts <qwen_prompt_splits...jsonl> \
        --out <staging-dir> [--zip]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np


STACKS = ("stack_a_720", "stack_b_720")
PROMPT_NAME = "qwen_prompt_splits_stratified_v2_200_500.jsonl"
EXPECTED_PER_STACK = 720


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def name_list_fingerprint(names: list[str]) -> str:
    """sha256 over the newline-joined sorted capture filenames (first 16 hex)."""
    return hashlib.sha256("\n".join(sorted(names)).encode("utf-8")).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="staging dir (will hold captures_720/ and zip)")
    parser.add_argument("--zip", action="store_true", help="also produce captures_720.zip")
    args = parser.parse_args()

    pkg = args.out / "captures_720"
    if pkg.exists():
        raise FileExistsError(f"{pkg} exists; remove it first")
    pkg.mkdir(parents=True)

    manifest_rows: list[dict] = []
    fingerprints: dict[str, dict] = {}
    for stack in STACKS:
        src_caps = args.src / stack / "captures"
        dst_caps = pkg / stack / "captures"
        dst_caps.mkdir(parents=True)
        files = sorted(src_caps.glob("*.npz"))
        if len(files) != EXPECTED_PER_STACK:
            raise ValueError(f"{stack}: {len(files)} npz, expected {EXPECTED_PER_STACK}")
        for src in files:
            shutil.copy2(src, dst_caps / src.name)
            rel = f"{stack}/captures/{src.name}"
            manifest_rows.append(
                {"path": rel, "bytes": (dst_caps / src.name).stat().st_size,
                 "sha256": sha256(dst_caps / src.name)}
            )
        fingerprints[stack] = {
            "n_files": len(files),
            "name_list_sha16": name_list_fingerprint([p.name for p in files]),
        }

    shutil.copy2(args.prompts, pkg / PROMPT_NAME)
    prompt_sha = sha256(pkg / PROMPT_NAME)
    manifest_rows.append({"path": PROMPT_NAME, "bytes": (pkg / PROMPT_NAME).stat().st_size,
                          "sha256": prompt_sha})

    with (pkg / "PACKAGE_MANIFEST.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    # split counts
    splits: dict[str, int] = {}
    for line in (pkg / PROMPT_NAME).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            splits[row["split"]] = splits.get(row["split"], 0) + 1

    readme = f"""# captures_720 — heterogeneous checkpoint capture pool

Distribution package for the 720-prompt experimental pool (Route B W1/W2).

## Contents

```
captures_720/
  stack_a_720/captures/<prompt_id>.npz   # {fingerprints['stack_a_720']['n_files']} files, reference
  stack_b_720/captures/<prompt_id>.npz   # {fingerprints['stack_b_720']['n_files']} files, candidate
  {PROMPT_NAME}
  PACKAGE_MANIFEST.csv
  README.md
```

## Provenance

- **stack_a_720**: Apple M4 / MPS, **bf16** execution.
- **stack_b_720**: NVIDIA RTX 6000 (Blackwell) / CUDA, **fp32** execution.
- Real cross-stack heterogeneous capture (not a same-stack re-run).
- Tensor layout: each npz holds keys `prefill__C1`, `prefill__C2`, `prefill__C3`,
  each `(1, T, 1024)` **float32**, T in [10, 23] (median 14).

## Fingerprints

| item | value |
|---|---|
| prompt file sha256 | `{prompt_sha}` |
| split counts | {json.dumps(splits, sort_keys=True)} |
| stack_a_720 name-list sha16 | `{fingerprints['stack_a_720']['name_list_sha16']}` |
| stack_b_720 name-list sha16 | `{fingerprints['stack_b_720']['name_list_sha16']}` |
| n files | {len(manifest_rows)} (incl. prompt jsonl) |

> Per-file sha256 is in `PACKAGE_MANIFEST.csv`; verify with:
> `python -c "import csv,hashlib,pathlib; b=pathlib.Path('captures_720'); print('mismatch:', [r['path'] for r in csv.DictReader(open(b/'PACKAGE_MANIFEST.csv')) if hashlib.sha256((b/r['path']).read_bytes()).hexdigest()!=r['sha256']])"`

## How it was built

`shared/accountedge_runtime_and_captures/scripts/build_captures_720_package.py`
(rename-only copy of the captures; no tensor mutation). Validate with
`.../scripts/validate_raw_captures_720.py`.
"""
    (pkg / "README.md").write_text(readme, encoding="utf-8")

    if args.zip:
        zip_path = args.out / "captures_720.zip"
        subprocess.run(["zip", "-r", "-q", str(zip_path), "captures_720"], cwd=args.out, check=True)
        print(json.dumps({"zip": str(zip_path), "zip_bytes": zip_path.stat().st_size}, indent=2))

    print(json.dumps({"package": str(pkg), "n_files": len(manifest_rows),
                      "simple_fingerprints": {k: v["name_list_sha16"] for k, v in fingerprints.items()}},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
