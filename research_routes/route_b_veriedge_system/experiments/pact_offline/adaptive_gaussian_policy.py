#!/usr/bin/env python3
"""Simulate PACT-G adaptive K with exact chi-square confidence intervals."""

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

from pcra_offline import CHECKPOINTS, normalized_residual, stable_seed  # noqa: E402
from calibration_audit import load_stack_pair  # noqa: E402


def exact_energy(pair) -> float:
    residual, _ = normalized_residual(pair)
    return float(np.mean(np.square(residual)))


def simulate(
    f2: float,
    threshold: float,
    k_values: list[int],
    beta: float,
    draws: int,
    seed_parts: tuple[object, ...],
) -> dict[str, float]:
    rng = np.random.default_rng(stable_seed("PACT-G-adaptive", *seed_parts))
    looks = len(k_values)
    # Bonferroni allocation makes simultaneous interval failure at most beta.
    per_tail = beta / (2.0 * looks)
    lower_quantiles = {k: float(chi2.ppf(per_tail, k)) for k in k_values}
    upper_quantiles = {k: float(chi2.ppf(1.0 - per_tail, k)) for k in k_values}

    verdict = np.zeros(draws, dtype=np.int8)  # 0 unresolved, 1 pass, 2 fail
    stopping_k = np.full(draws, k_values[-1], dtype=np.int32)
    cumulative = np.zeros(draws, dtype=np.float64)
    previous = 0
    for k in k_values:
        increment = k - previous
        cumulative += rng.chisquare(increment, size=draws)
        statistic = f2 * cumulative / k
        lower = k * statistic / upper_quantiles[k]
        upper = k * statistic / lower_quantiles[k]
        active = verdict == 0
        passes = active & (upper <= threshold)
        fails = active & (lower > threshold)
        verdict[passes] = 1
        verdict[fails] = 2
        stopping_k[passes | fails] = k
        previous = k

    return {
        "pass_rate": float(np.mean(verdict == 1)),
        "fail_rate": float(np.mean(verdict == 2)),
        "inconclusive_rate": float(np.mean(verdict == 0)),
        "mean_stopping_K": float(np.mean(stopping_k)),
        "median_stopping_K": float(np.median(stopping_k)),
        "p90_stopping_K": float(np.quantile(stopping_k, 0.90)),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for checkpoint in CHECKPOINTS:
        for rho in sorted({float(row["rho"]) for row in rows}):
            group = [
                row
                for row in rows
                if row["checkpoint"] == checkpoint and float(row["rho"]) == rho
            ]
            output.append(
                {
                    "checkpoint": checkpoint,
                    "rho": rho,
                    "prompts": len(group),
                    "mean_pass_rate": float(np.mean([float(row["pass_rate"]) for row in group])),
                    "mean_fail_rate": float(np.mean([float(row["fail_rate"]) for row in group])),
                    "mean_inconclusive_rate": float(
                        np.mean([float(row["inconclusive_rate"]) for row in group])
                    ),
                    "mean_stopping_K": float(
                        np.mean([float(row["mean_stopping_K"]) for row in group])
                    ),
                    "median_prompt_energy": float(
                        np.median([float(row["full_energy"]) for row in group])
                    ),
                    "smoke_threshold": float(group[0]["threshold"]),
                }
            )
    return output


def plot_aggregate(rows: list[dict[str, object]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.4), sharey=True)
    colors = {"pass": "#d9d9d9", "inconclusive": "#969696", "fail": "#363636"}
    for axis, checkpoint in zip(axes, CHECKPOINTS):
        group = [row for row in rows if row["checkpoint"] == checkpoint]
        group.sort(key=lambda row: float(row["rho"]))
        x = np.arange(len(group))
        bottom = np.zeros(len(group))
        for verdict in ("pass", "inconclusive", "fail"):
            values = np.asarray([float(row[f"mean_{verdict}_rate"]) for row in group])
            axis.bar(
                x,
                values,
                bottom=bottom,
                color=colors[verdict],
                edgecolor="white",
                linewidth=0.5,
                label=verdict.upper(),
            )
            bottom += values
        for position, row in zip(x, group):
            axis.text(
                position,
                1.025,
                f"K={float(row['mean_stopping_K']):.0f}",
                ha="center",
                va="bottom",
                fontsize=7,
            )
        axis.set_xticks(x, ["honest" if float(row["rho"]) == 0 else f"rho={row['rho']}" for row in group])
        axis.tick_params(axis="x", labelrotation=25)
        axis.set_ylim(0.0, 1.12)
        axis.set_title(checkpoint.replace("prefill__", ""))
        axis.grid(True, axis="y", color="#dddddd", linewidth=0.6)
    axes[0].set_ylabel("Verdict rate")
    axes[-1].legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "adaptive_gaussian")
    parser.add_argument("--draws", type=int, default=50_000)
    parser.add_argument("--beta", type=float, default=0.01)
    args = parser.parse_args()

    k_values = [8, 16, 32, 64, 128, 256]
    calibration = load_stack_pair(
        args.data_root, "stack_01_calib", "stack_02_calib", "calib"
    )
    evaluation = load_stack_pair(
        args.data_root, "stack_01_eval", "stack_02_eval", "eval"
    )
    thresholds = {
        checkpoint: max(
            exact_energy(pair) for pair in calibration if pair.checkpoint == checkpoint
        )
        for checkpoint in CHECKPOINTS
    }

    rows: list[dict[str, object]] = []
    for pair in evaluation:
        honest_energy = exact_energy(pair)
        for rho in (0.0, 0.01, 0.02, 0.05):
            full_energy = honest_energy + rho * rho
            result = simulate(
                full_energy,
                thresholds[pair.checkpoint],
                k_values,
                args.beta,
                args.draws,
                (pair.prompt_id, pair.checkpoint, rho),
            )
            rows.append(
                {
                    "prompt_id": pair.prompt_id,
                    "checkpoint": pair.checkpoint,
                    "rho": rho,
                    "honest_energy": honest_energy,
                    "full_energy": full_energy,
                    "threshold": thresholds[pair.checkpoint],
                    **result,
                }
            )

    aggregate_rows = aggregate(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "adaptive_by_prompt.csv", rows)
    write_csv(args.output / "adaptive_aggregate.csv", aggregate_rows)
    plot_aggregate(aggregate_rows, args.output / "adaptive_verdicts.png")
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": "projection-policy simulation with six-prompt smoke thresholds",
                "projection_family": "gaussian",
                "exact_law": "K*T_K/F2 ~ chi-square(K)",
                "K_sequence": k_values,
                "simultaneous_interval_beta": args.beta,
                "allocation": "two-sided Bonferroni across six looks",
                "draws_per_prompt_setting": args.draws,
                "strict_1pct_calibration_claim": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
