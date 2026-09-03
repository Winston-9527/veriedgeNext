#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "FILE_MANIFEST_SHA256.csv"

SKIP_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__MACOSX",
    "__pycache__",
    "tmp",
    "venv",
}
SKIP_NAMES = {".DS_Store", "Thumbs.db", OUTPUT.name}
SKIP_SUFFIXES = {
    ".aux",
    ".bbl",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".pyc",
    ".pyo",
    ".synctex.gz",
    ".toc",
}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in SKIP_DIRECTORIES for part in relative.parts[:-1]):
        return False
    if path.name in SKIP_NAMES or path.name.startswith("._"):
        return False
    return not any(path.name.endswith(suffix) for suffix in SKIP_SUFFIXES)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    files = sorted(
        (path for path in ROOT.rglob("*") if path.is_file() and included(path)),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["Path", "Bytes", "SHA256"])
        for path in files:
            writer.writerow(
                [path.relative_to(ROOT).as_posix(), path.stat().st_size, sha256(path)]
            )
    print(f"Wrote {OUTPUT} with {len(files)} files")


if __name__ == "__main__":
    main()
