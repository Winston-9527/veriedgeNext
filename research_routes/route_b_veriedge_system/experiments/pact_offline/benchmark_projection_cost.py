#!/usr/bin/env python3
"""Local CPU microbenchmark for materialized PACT projection families."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROUTE_ROOT = HERE.parents[1]
PCRA_DIR = HERE.parent / "pcra_offline_retired"
DEFAULT_DATA_ROOT = (
    ROUTE_ROOT
    / "shared"
    / "accountedge_runtime_and_captures"
    / "raw_captures"
    / "e2_live_subset"
)
sys.path.insert(0, str(PCRA_DIR))

from pcra_offline import load_pairs, normalized_residual  # noqa: E402
from quantized_gaussian import coefficients as quantized_coefficients  # noqa: E402


def percentile(values: list[float], probability: float) -> float:
    return float(np.quantile(np.asarray(values), probability))


def generate(rng: np.random.Generator, family: str, shape: tuple[int, int]) -> np.ndarray:
    if family == "gaussian":
        return rng.standard_normal(shape, dtype=np.float32)
    if family in {"lut8", "lut16"}:
        return quantized_coefficients(rng, family, shape)
    bits = rng.integers(0, 2, size=shape, dtype=np.int8)
    matrix = bits.astype(np.float32)
    matrix *= 2.0
    matrix -= 1.0
    return matrix


def benchmark(
    vector: np.ndarray, family: str, k: int, repeats: int, seed: int
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    shape = (k, vector.size)
    generation_ms: list[float] = []
    matvec_ms: list[float] = []
    end_to_end_ms: list[float] = []
    checksum = 0.0

    for _ in range(3):
        warm = generate(rng, family, shape)
        checksum += float(np.sum(warm @ vector))

    for _ in range(repeats):
        start = time.perf_counter_ns()
        matrix = generate(rng, family, shape)
        generated = time.perf_counter_ns()
        projected = matrix @ vector
        finished = time.perf_counter_ns()
        checksum += float(np.sum(projected))
        generation_ms.append((generated - start) / 1e6)
        matvec_ms.append((finished - generated) / 1e6)
        end_to_end_ms.append((finished - start) / 1e6)

    return {
        "family": family,
        "K": k,
        "N": vector.size,
        "repeats": repeats,
        "coefficient_buffer_bytes": k * vector.size * 4,
        "one_sketch_float32_bytes": k * 4,
        "actual_plus_reference_sketch_bytes": k * 8,
        "median_generation_ms": float(np.median(generation_ms)),
        "p90_generation_ms": percentile(generation_ms, 0.90),
        "median_matvec_ms": float(np.median(matvec_ms)),
        "p90_matvec_ms": percentile(matvec_ms, 0.90),
        "median_end_to_end_ms": float(np.median(end_to_end_ms)),
        "p90_end_to_end_ms": percentile(end_to_end_ms, 0.90),
        "checksum": checksum,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "projection_benchmark")
    parser.add_argument("--repeats", type=int, default=30)
    args = parser.parse_args()

    pair = next(
        pair
        for pair in load_pairs(args.data_root, "eval")
        if pair.prompt_id == "eval_001" and pair.checkpoint == "prefill__C1"
    )
    residual, _ = normalized_residual(pair)
    vector = np.asarray(residual, dtype=np.float32)
    rows = [
        benchmark(vector, family, k, args.repeats, 20260824 + k + 1000 * family_id)
        for family_id, family in enumerate(("rademacher", "lut8", "lut16", "gaussian"))
        for k in (8, 16, 32, 64)
    ]

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "projection_cost.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": "local NumPy CPU microbenchmark, not deployment overhead",
                "pair": f"{pair.prompt_id}:{pair.checkpoint}",
                "N": vector.size,
                "dtype": "float32",
                "coefficient_materialization": True,
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
