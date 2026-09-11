#!/usr/bin/env python3
"""Sample size vs attainable FPR for the exact-energy (max-of-calibration) detector.

Given the per-prompt residual energies emitted by ``calibration_audit.py``
(``energy_by_prompt.csv``), this asks: how large a calibration corpus do we need
before the *evaluation* false-positive rate is reliably below the target alpha?

For each checkpoint (C1/C2/C3) and each calibration size n, we resample n
calibration prompts, set the threshold to their max energy, and measure the
evaluation exceedance rate (FPR). We report the mean FPR and a one-sided 95%
upper bound (Clopper-Pearson on the evaluation count). The C1 hypothesis under
test is whether the C3 tail is non-stationary -- i.e. whether the C3 FPR keeps
exceeding alpha even as n grows.

Usage:
    python3 sample_size_vs_fpr.py \
        --energy-csv <calibration_audit results>/energy_by_prompt.csv \
        --out <dir> [--resamples 200] [--alpha 0.01]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta

# candidate calibration sizes; capped to the available calibration count.
N_GRID = (30, 50, 100, 200, 399, 519)


def clopper_pearson_upper(k: int, n: int, confidence: float = 0.95) -> float:
    """One-sided upper bound on a binomial rate (k successes / n trials)."""
    if n == 0:
        return float("nan")
    if k >= n:
        return 1.0
    return float(beta.ppf(confidence, k + 1, n - k))


def load_energies(csv_path: Path) -> dict[str, dict[str, np.ndarray]]:
    """Return {checkpoint: {"calibration": energies, "evaluation": energies}}."""
    buckets: dict[str, dict[str, list[float]]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("candidate_run", "original") != "original":
                continue
            split = row["split"]
            if split not in ("calibration", "evaluation"):
                continue
            buckets.setdefault(row["checkpoint"], {"calibration": [], "evaluation": []})
            buckets[row["checkpoint"]][split].append(float(row["full_residual_energy"]))
    return {
        ckpt: {"calibration": np.asarray(v["calibration"]), "evaluation": np.asarray(v["evaluation"])}
        for ckpt, v in buckets.items()
    }


def evaluate_size(
    calibration: np.ndarray, evaluation: np.ndarray, n: int, resamples: int, alpha: float,
    rng: np.random.Generator,
) -> dict:
    if n >= calibration.size:
        sample = calibration
        k = int(np.sum(evaluation > float(np.max(sample))))
        return {
            "n_calib": int(sample.size),
            "fpr_mean": k / evaluation.size,
            "fpr_upper95": clopper_pearson_upper(k, evaluation.size, 1 - alpha),
            "n_resamples": 1,
        }
    fprs, uppers = [], []
    for _ in range(resamples):
        sample = rng.choice(calibration, size=n, replace=False)
        threshold = float(np.max(sample))
        k = int(np.sum(evaluation > threshold))
        fprs.append(k / evaluation.size)
        uppers.append(clopper_pearson_upper(k, evaluation.size, 1 - alpha))
    return {
        "n_calib": n,
        "fpr_mean": float(np.mean(fprs)),
        "fpr_upper95": float(np.mean(uppers)),
        "n_resamples": resamples,
    }


def classify(rows: list[dict], alpha: float) -> str:
    full = rows[-1]  # largest n
    if full["fpr_upper95"] <= alpha:
        return "PASS"          # reaches alpha within the one-sided bound
    if full["fpr_mean"] > alpha:
        return "FAIL"          # cannot reach alpha even at the largest n
    return "INCONCLUSIVE"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--energy-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resamples", type=int, default=200)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=20260910)
    args = parser.parse_args()

    energies = load_energies(args.energy_csv)
    if not energies:
        raise ValueError(f"no energy rows in {args.energy_csv}")
    args.out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    all_rows: list[dict] = []
    verdicts: dict[str, str] = {}
    curves: dict[str, list[dict]] = {}
    for checkpoint in sorted(energies):
        calibration = energies[checkpoint]["calibration"]
        evaluation = energies[checkpoint]["evaluation"]
        n_grid = [n for n in N_GRID if n <= calibration.size]
        if calibration.size not in n_grid:
            n_grid.append(int(calibration.size))
        rows = [
            {"checkpoint": checkpoint, **evaluate_size(calibration, evaluation, n, args.resamples, args.alpha, rng)}
            for n in n_grid
        ]
        all_rows.extend(rows)
        curves[checkpoint] = rows
        verdicts[checkpoint] = classify(rows, args.alpha)

    with (args.out / "sample_size_vs_fpr.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["checkpoint", "n_calib", "fpr_mean", "fpr_upper95", "n_resamples"]
        )
        writer.writeheader()
        writer.writerows(all_rows)

    report = {
        "alpha": args.alpha,
        "resamples": args.resamples,
        "seed": args.seed,
        "calibration_sizes": {c: int(v["calibration"].size) for c, v in energies.items()},
        "evaluation_sizes": {c: int(v["evaluation"].size) for c, v in energies.items()},
        "verdict_by_checkpoint": verdicts,
        "curves": curves,
    }
    (args.out / "sample_size_vs_fpr.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6.4, 3.6))
        for checkpoint, rows in curves.items():
            xs = [r["n_calib"] for r in rows]
            ax.plot(xs, [r["fpr_mean"] for r in rows], marker="o", label=f"{checkpoint} FPR")
            ax.plot(xs, [r["fpr_upper95"] for r in rows], linestyle="--", alpha=0.6,
                    label=f"{checkpoint} upper95")
        ax.axhline(args.alpha, color="red", linestyle=":", label=f"alpha={args.alpha}")
        ax.set_xlabel("calibration prompts n")
        ax.set_ylabel("evaluation FPR")
        ax.set_xscale("log")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(args.out / "sample_size_vs_fpr.png", dpi=200)
        plt.close(fig)
    except Exception as exc:  # plotting is best-effort
        print(f"[warn] plot skipped: {exc}")

    print(json.dumps({"verdict_by_checkpoint": verdicts,
                      "out": str(args.out)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
