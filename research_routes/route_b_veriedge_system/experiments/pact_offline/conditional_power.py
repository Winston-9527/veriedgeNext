#!/usr/bin/env python3
"""Exact conditional PACT-G power and projection-budget sizing."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2


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

from pcra_offline import CHECKPOINTS, load_pairs, normalized_residual  # noqa: E402


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def exact_power(honest_energy: float, attack_energy: float, k: np.ndarray, alpha: float) -> np.ndarray:
    threshold = honest_energy * chi2.ppf(1.0 - alpha, k) / k
    return chi2.sf(k * threshold / attack_energy, k)


def first_k(power: np.ndarray, k: np.ndarray, target: float) -> int | None:
    positions = np.flatnonzero(power >= target)
    return int(k[positions[0]]) if positions.size else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "conditional_power")
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--max-k", type=int, default=4096)
    args = parser.parse_args()

    k_grid = np.arange(1, args.max_k + 1, dtype=np.int64)
    reported_k = (8, 16, 32, 64, 128, 256, 512, 1024)
    sizing_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []
    for pair in load_pairs(args.data_root, "eval"):
        residual, _ = normalized_residual(pair)
        honest = float(np.mean(np.square(residual)))
        for rho in (0.01, 0.02, 0.05):
            attacked = honest + rho * rho
            power = exact_power(honest, attacked, k_grid, args.alpha)
            sizing_rows.append(
                {
                    "prompt_id": pair.prompt_id,
                    "checkpoint": pair.checkpoint,
                    "rho": rho,
                    "honest_energy": honest,
                    "attacked_energy": attacked,
                    "energy_ratio": attacked / honest,
                    "min_K_for_80pct_power": first_k(power, k_grid, 0.80),
                    "min_K_for_90pct_power": first_k(power, k_grid, 0.90),
                    "min_K_for_95pct_power": first_k(power, k_grid, 0.95),
                    "min_K_for_99pct_power": first_k(power, k_grid, 0.99),
                }
            )
            for k in reported_k:
                curve_rows.append(
                    {
                        "prompt_id": pair.prompt_id,
                        "checkpoint": pair.checkpoint,
                        "rho": rho,
                        "K": k,
                        "conditional_fpr": args.alpha,
                        "exact_detection_power": float(power[k - 1]),
                    }
                )

    aggregate_rows: list[dict[str, object]] = []
    for checkpoint in CHECKPOINTS:
        for rho in (0.01, 0.02, 0.05):
            group = [
                row
                for row in sizing_rows
                if row["checkpoint"] == checkpoint and float(row["rho"]) == rho
            ]
            aggregate_rows.append(
                {
                    "checkpoint": checkpoint,
                    "rho": rho,
                    "prompts": len(group),
                    "median_energy_ratio": float(
                        np.median([float(row["energy_ratio"]) for row in group])
                    ),
                    "median_K_for_90pct_power": float(
                        np.median([int(row["min_K_for_90pct_power"]) for row in group])
                    ),
                    "max_K_for_90pct_power": int(
                        np.max([int(row["min_K_for_90pct_power"]) for row in group])
                    ),
                    "median_K_for_95pct_power": float(
                        np.median([int(row["min_K_for_95pct_power"]) for row in group])
                    ),
                    "max_K_for_95pct_power": int(
                        np.max([int(row["min_K_for_95pct_power"]) for row in group])
                    ),
                }
            )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "power_by_prompt.csv", sizing_rows)
    write_csv(args.output / "power_curves.csv", curve_rows)
    write_csv(args.output / "power_aggregate.csv", aggregate_rows)
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": "exact projection-only conditional power; assumes prompt-specific honest energy",
                "projection_family": "gaussian",
                "conditional_fpr": args.alpha,
                "max_K_searched": args.max_k,
                "prompt_distribution_calibration_included": False,
                "support_dependence": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
