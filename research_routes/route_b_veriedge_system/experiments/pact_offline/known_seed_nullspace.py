#!/usr/bin/env python3
"""PACT-G negative control: attack after the realized projection seed is known."""

from __future__ import annotations

import argparse
import csv
import json
import sys
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

from pcra_offline import load_pairs, normalized_residual, stable_seed  # noqa: E402


def load_thresholds(path: Path) -> dict[tuple[str, int], float]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            (row["checkpoint"], int(row["K"])): float(row["threshold"])
            for row in csv.DictReader(handle)
        }


def nullspace_attack(
    matrix: np.ndarray,
    residual: np.ndarray,
    rho: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, float, float, float]:
    """Return a K+2-sparse delta in ker(A) and orthogonal to residual."""
    k, n = matrix.shape
    support = rng.choice(n, size=k + 2, replace=False)
    # K projection constraints plus one harm-preservation constraint leave a
    # nonzero null direction in K+2 variables with probability one.
    constraints = np.vstack((matrix[:, support], residual[support][None, :]))
    _, _, vh = np.linalg.svd(constraints, full_matrices=True)
    values = vh[-1]
    values *= rho * np.sqrt(n) / np.linalg.norm(values)
    projected = matrix[:, support] @ values
    residual_dot = float(np.dot(residual[support], values))
    relative_l2 = float(np.linalg.norm(values) / np.sqrt(n))
    null_relative = float(np.linalg.norm(projected) / max(np.linalg.norm(values), 1e-30))
    cosine = residual_dot / (np.linalg.norm(residual) * np.linalg.norm(values))
    return support, values, relative_l2, null_relative, float(cosine)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=HERE / "results" / "gaussian_p0" / "thresholds.csv",
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "known_seed")
    parser.add_argument("--draws", type=int, default=64)
    args = parser.parse_args()

    thresholds = load_thresholds(args.thresholds)
    pairs = [
        pair
        for pair in load_pairs(args.data_root, "eval")
        if pair.prompt_id in {"eval_001", "eval_005"}
    ]
    rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    for pair in pairs:
        residual, _ = normalized_residual(pair)
        n = residual.size
        for k in (8, 32, 64):
            threshold = thresholds[(pair.checkpoint, k)]
            honest_hits = 0
            attack_hits = {rho: 0 for rho in (0.01, 0.02, 0.05)}
            audit = {
                rho: {"max_l2_error": 0.0, "max_null_relative": 0.0, "max_abs_cosine": 0.0}
                for rho in attack_hits
            }
            rng = np.random.default_rng(
                stable_seed("PACT-G", "known-seed", pair.prompt_id, pair.checkpoint, k)
            )
            for _ in range(args.draws):
                matrix = rng.standard_normal((k, n), dtype=np.float64)
                honest_projection = matrix @ residual
                honest_statistic = float(np.mean(np.square(honest_projection)) / n)
                honest_hits += int(honest_statistic > threshold)
                for rho in attack_hits:
                    support, values, relative_l2, null_relative, cosine = nullspace_attack(
                        matrix, residual, rho, rng
                    )
                    attacked_projection = honest_projection + matrix[:, support] @ values
                    attacked_statistic = float(np.mean(np.square(attacked_projection)) / n)
                    attack_hits[rho] += int(attacked_statistic > threshold)
                    audit[rho]["max_l2_error"] = max(
                        audit[rho]["max_l2_error"], abs(relative_l2 - rho)
                    )
                    audit[rho]["max_null_relative"] = max(
                        audit[rho]["max_null_relative"], null_relative
                    )
                    audit[rho]["max_abs_cosine"] = max(
                        audit[rho]["max_abs_cosine"], abs(cosine)
                    )

            honest_rate = honest_hits / args.draws
            for rho, hits in attack_hits.items():
                rows.append(
                    {
                        "prompt_id": pair.prompt_id,
                        "checkpoint": pair.checkpoint,
                        "N": n,
                        "K": k,
                        "rho": rho,
                        "attack_support": k + 2,
                        "draws": args.draws,
                        "threshold": threshold,
                        "honest_detection_rate": honest_rate,
                        "known_seed_attack_detection_rate": hits / args.draws,
                        "rate_difference": hits / args.draws - honest_rate,
                    }
                )
                audit_rows.append(
                    {
                        "prompt_id": pair.prompt_id,
                        "checkpoint": pair.checkpoint,
                        "K": k,
                        "rho": rho,
                        **audit[rho],
                    }
                )

    aggregate_rows: list[dict[str, object]] = []
    for k in (8, 32, 64):
        for rho in (0.01, 0.02, 0.05):
            group = [row for row in rows if int(row["K"]) == k and float(row["rho"]) == rho]
            aggregate_rows.append(
                {
                    "K": k,
                    "rho": rho,
                    "pair_checkpoints": len(group),
                    "mean_honest_detection_rate": float(
                        np.mean([float(row["honest_detection_rate"]) for row in group])
                    ),
                    "mean_known_seed_attack_detection_rate": float(
                        np.mean([float(row["known_seed_attack_detection_rate"]) for row in group])
                    ),
                    "max_abs_pair_rate_difference": float(
                        np.max(np.abs([float(row["rate_difference"]) for row in group]))
                    ),
                }
            )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "known_seed_by_pair.csv", rows)
    write_csv(args.output / "known_seed_aggregate.csv", aggregate_rows)
    write_csv(args.output / "constraint_audit.csv", audit_rows)
    summary = {
        "status": "negative control outside the commit-before-seed threat model",
        "projection_family": "gaussian",
        "attack_timing": "realized seed known before attack construction",
        "construction": "(K+2)-sparse nullspace vector orthogonal to honest residual",
        "draws_per_pair_K": args.draws,
        "max_l2_error": max(float(row["max_l2_error"]) for row in audit_rows),
        "max_null_relative": max(float(row["max_null_relative"]) for row in audit_rows),
        "max_abs_residual_cosine": max(float(row["max_abs_cosine"]) for row in audit_rows),
        "max_abs_pair_detection_rate_difference": max(
            float(row["max_abs_pair_rate_difference"]) for row in aggregate_rows
        ),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
