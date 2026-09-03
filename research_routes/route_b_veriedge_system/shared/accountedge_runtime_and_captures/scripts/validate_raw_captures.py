#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


EXPECTED_KEYS = {"prefill__C1", "prefill__C2", "prefill__C3"}
ARTIFACT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ARTIFACT_ROOT / "raw_captures" / "e2_live_subset" / "manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_file(path: Path, expected_hash: str | None) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    if expected_hash and sha256(path) != expected_hash:
        raise ValueError(f"sha256 mismatch for {path}")
    with np.load(path) as capture:
        keys = set(capture.files)
        if keys != EXPECTED_KEYS:
            raise ValueError(f"{path} has keys {sorted(keys)}, expected {sorted(EXPECTED_KEYS)}")
        shapes = {}
        for key in sorted(keys):
            tensor = capture[key]
            if tensor.ndim != 3:
                raise ValueError(f"{path}:{key} expected 3D tensor, got shape {tensor.shape}")
            if not np.issubdtype(tensor.dtype, np.number):
                raise TypeError(f"{path}:{key} is not numeric")
            shapes[key] = list(tensor.shape)
    return {"path": str(path), "shapes": shapes}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate included raw checkpoint capture subset.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parents[2]
    validated = []
    for row in manifest["files"]:
        validated.append(validate_file(root / row["file"], row.get("sha256")))
    print(json.dumps({"validated_files": len(validated), "example": validated[:2]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
